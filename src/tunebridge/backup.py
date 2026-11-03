"""Sicherung & Wiederherstellung.

Ein Backup ist eine einzelne Datei `tunebridge-<rechner>-<datum>.tbbackup` (ZIP):
  manifest.json   – Format, Datum, Rechner, Schema-Version, Zahlen
  tunebridge.db   – konsistenter Schnappschuss der SQLite-DB (Backup-API, auch während die App läuft)
  exports/*.json  – Plattform-Exporte
  config.env      – nur wenn gewünscht: API-Keys (Datei ist dann nur für dich lesbar)

Wiederherstellen:
  replace – Datenbank komplett durch das Backup ersetzen (neuer Rechner)
  merge   – Backup zu den vorhandenen Daten hinzufügen (z.B. zwei Rechner zusammenführen)
Vor jeder Wiederherstellung wird automatisch eine Sicherung des aktuellen Stands angelegt.
"""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import time
import zipfile
from datetime import datetime
from pathlib import Path

from . import __version__, config, store

FORMAT = 1
SUFFIX = ".tbbackup"
AUTO_KEEP = 14          # so viele automatische Backups bleiben liegen
AUTO_INTERVAL = 86400   # einmal pro Tag
# Diese Einträge sind rechnerspezifisch und werden nie übernommen
_MACHINE_KEYS = {"TUNEBRIDGE_DATA", "TUNEBRIDGE_BACKUP_DIR"}


def backup_dir() -> Path:
    d = Path(config.opt("TUNEBRIDGE_BACKUP_DIR") or config.DATA / "backups")
    d.mkdir(parents=True, exist_ok=True)
    return d


def _snapshot_db(dest: Path) -> None:
    with store._conn():  # sorgt dafür, dass die DB existiert und migriert ist
        pass
    src = sqlite3.connect(store.DB)
    dst = sqlite3.connect(dest)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()


def create(include_keys: bool = False, kind: str = "manuell", dest_dir: Path | None = None) -> Path:
    dest_dir = dest_dir or backup_dir()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    suffix = "" if kind == "manuell" else f"-{kind}"
    out = dest_dir / f"tunebridge-{store.HOST}-{stamp}{suffix}{SUFFIX}"
    tmp_out = out.with_suffix(".part")
    with tempfile.TemporaryDirectory() as td:
        snap = Path(td) / "tunebridge.db"
        _snapshot_db(snap)
        manifest = {
            "format": FORMAT, "app_version": __version__, "created": time.time(), "host": store.HOST,
            "kind": kind, "schema": store.SCHEMA_VERSION, "stats": store.stats(),
            "includes_keys": bool(include_keys and config.CONFIG_FILE.exists()),
        }
        with zipfile.ZipFile(tmp_out, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))
            z.write(snap, "tunebridge.db")
            for f in sorted((config.DATA / "exports").glob("*.json")):
                z.write(f, f"exports/{f.name}")
            if manifest["includes_keys"]:
                z.write(config.CONFIG_FILE, "config.env")
    os.chmod(tmp_out, 0o600)
    tmp_out.rename(out)  # erst am Ende umbenennen: nie halbe Backups im Ordner
    return out


def inspect(path: Path) -> dict:
    try:
        with zipfile.ZipFile(path) as z:
            m = json.loads(z.read("manifest.json"))
            if "tunebridge.db" not in z.namelist():
                raise ValueError("Datenbank fehlt im Backup")
    except (zipfile.BadZipFile, KeyError, json.JSONDecodeError) as e:
        raise ValueError(f"Keine gültige tunebridge-Sicherung: {e}") from e
    if m.get("format", 0) > FORMAT:
        raise ValueError("Backup stammt von einer neueren tunebridge-Version")
    return m


def list_backups() -> list[dict]:
    out = []
    for f in sorted(backup_dir().glob(f"*{SUFFIX}"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            m = inspect(f)
        except ValueError:
            continue
        out.append({"name": f.name, "path": str(f), "size": f.stat().st_size, **m})
    return out


def _check_db(path: Path) -> None:
    c = sqlite3.connect(path)
    try:
        if c.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Datenbank im Backup ist beschädigt")
    finally:
        c.close()


def restore(path: Path, mode: str = "replace", restore_keys: bool = False) -> dict:
    if mode not in ("replace", "merge"):
        raise ValueError("mode muss 'replace' oder 'merge' sein")
    manifest = inspect(path)
    safety = create(kind="vor-wiederherstellung")
    store.ram_clear()

    with tempfile.TemporaryDirectory() as td, zipfile.ZipFile(path) as z:
        tmp_db = Path(td) / "restore.db"
        tmp_db.write_bytes(z.read("tunebridge.db"))
        _check_db(tmp_db)
        with store._conn(tmp_db):  # ältere Backups aufs aktuelle Schema heben
            pass

        if mode == "replace":
            src, dst = sqlite3.connect(tmp_db), sqlite3.connect(store.DB)
            try:
                src.backup(dst)  # ersetzt den Inhalt atomar, offene Verbindungen bleiben gültig
            finally:
                src.close()
                dst.close()
        else:
            with store._conn() as c:
                c.execute("ATTACH DATABASE ? AS b", (str(tmp_db),))
                c.execute("""INSERT OR IGNORE INTO recognitions(uid,ts,host,source,engine,agreement,track,extra)
                             SELECT uid,ts,host,source,engine,agreement,track,extra FROM b.recognitions""")
                c.execute("INSERT OR IGNORE INTO playlists(name,created,description) SELECT name,created,description FROM b.playlists")
                c.execute("""INSERT OR IGNORE INTO entries(playlist,track,key,ts,host,pushed)
                             SELECT playlist,track,key,ts,host,pushed FROM b.entries""")
                c.execute("INSERT OR IGNORE INTO cache(ns,key,value,ts) SELECT ns,key,value,ts FROM b.cache")
                c.execute("INSERT OR IGNORE INTO genre_terms SELECT * FROM b.genre_terms")
                c.execute("INSERT OR IGNORE INTO songs SELECT * FROM b.songs")
                c.execute("""INSERT OR IGNORE INTO misses(uid,ts,host,kind,source,level_db,player,song,details,note,sent)
                             SELECT uid,ts,host,kind,source,level_db,player,song,details,note,sent FROM b.misses""")

        exports = config.DATA / "exports"
        for n in z.namelist():
            if n.startswith("exports/") and n.endswith(".json"):
                target = exports / Path(n).name
                if mode == "replace" or not target.exists():
                    exports.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(z.read(n))

        keys_restored = 0
        if restore_keys and "config.env" in z.namelist():
            for line in z.read("config.env").decode().splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = (x.strip() for x in line.split("=", 1))
                if v and k not in _MACHINE_KEYS and (mode == "replace" or not config.opt(k)):
                    config.set_value(k, v)
                    keys_restored += 1

    store.ram_clear()            # Datenbank wurde ersetzt -> RAM-Kopien verwerfen
    return {"mode": mode, "from": manifest, "safety_backup": safety.name,
            "keys_restored": keys_restored, "stats": store.stats()}


def auto_backup() -> Path | None:
    """Einmal pro Tag automatisch sichern (ohne Keys) und alte Auto-Backups aufräumen."""
    last = float(store.meta_get("last_auto_backup") or 0)
    if time.time() - last < AUTO_INTERVAL or store.stats()["recognitions"] == 0:
        return None
    out = create(kind="auto")
    store.meta_set("last_auto_backup", str(time.time()))
    autos = sorted(backup_dir().glob(f"*-auto{SUFFIX}"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in autos[AUTO_KEEP:]:
        old.unlink(missing_ok=True)
    return out

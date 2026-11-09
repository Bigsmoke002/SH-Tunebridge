"""Lokale Datenbank (SQLite): Erkennungs-Verlauf + eigene Ziel-Playlists.

Die Ziel-Playlists sammeln Songs, bis sie per Provider auf eine Plattform
übertragen werden (Spalte `pushed`). Jeder Eintrag merkt sich den Rechner (host).
"""

from __future__ import annotations

import json
import socket
import sqlite3
import os
import threading
import time
import uuid
from collections import OrderedDict
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path

from . import config
from .models import Library, Playlist, Track

DB = config.DATA / "tunebridge.db"
HOST = socket.gethostname()

# Schema-Migrationen: Index = Zielversion - 1. Nur anhängen, nie ändern!
MIGRATIONS: list[str] = [
    # v1 – Grundschema
    """
    CREATE TABLE IF NOT EXISTS recognitions(
      id INTEGER PRIMARY KEY, ts REAL, host TEXT, source TEXT, engine TEXT,
      agreement INTEGER, track TEXT, extra TEXT);
    CREATE TABLE IF NOT EXISTS playlists(
      name TEXT PRIMARY KEY, created REAL, description TEXT DEFAULT '');
    CREATE TABLE IF NOT EXISTS entries(
      id INTEGER PRIMARY KEY, playlist TEXT REFERENCES playlists(name) ON DELETE CASCADE,
      track TEXT, key TEXT, ts REAL, host TEXT, pushed INTEGER DEFAULT 0,
      UNIQUE(playlist, key));
    """,
    # v2 – eindeutige IDs (für Zusammenführen von Backups), Cache, Meta
    """
    ALTER TABLE recognitions ADD COLUMN uid TEXT;
    UPDATE recognitions SET uid = host || '-' || CAST(ts AS TEXT) || '-' || id WHERE uid IS NULL;
    CREATE UNIQUE INDEX IF NOT EXISTS recognitions_uid ON recognitions(uid);
    CREATE INDEX IF NOT EXISTS recognitions_ts ON recognitions(ts);
    CREATE INDEX IF NOT EXISTS entries_key ON entries(key);
    CREATE TABLE IF NOT EXISTS cache(ns TEXT, key TEXT, value TEXT, ts REAL, PRIMARY KEY(ns, key));
    CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
    """,
    # v3 – selbst gelernte Genres (aus Last.fm-Tags, die auf kein bekanntes Genre passen)
    """
    CREATE TABLE IF NOT EXISTS genre_terms(
      tag TEXT PRIMARY KEY,          -- normalisierter Tag, z. B. "sigilkore"
      label TEXT,                    -- Anzeigename
      state TEXT,                    -- candidate | learned | confirmed | rejected
      main TEXT, sub TEXT, niche TEXT,
      how TEXT,                      -- auto | manuell | llm-nein
      songs TEXT,                    -- JSON: Song-Schlüssel, bei denen der Tag vorkam (max. 30)
      cooc TEXT,                     -- JSON: {Hauptgenre: Anzahl} dieser Songs
      llm TEXT,                      -- JSON: letzte LLM-Einschätzung
      updated REAL);
    """,
    # v4 – Song-Speicher (bekannte Songs ohne neue Online-Abfragen) + lokale Fingerabdrücke
    """
    CREATE TABLE IF NOT EXISTS songs(
      key TEXT PRIMARY KEY,          -- ISRC oder „künstler|titel“ (ein Song hat ggf. 2 Zeilen)
      track TEXT, extra TEXT,        -- angereicherte Daten (Genre, Cover, Hörprobe, Links …)
      ts REAL,                       -- wann online nachgeschlagen
      used REAL, hits INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS fingerprints(
      hash INTEGER NOT NULL,         -- Frequenz-Paar + Abstand (aus Audio nicht rückrechenbar)
      ref TEXT NOT NULL,             -- Song-Schlüssel@Tempo
      t INTEGER NOT NULL);           -- Zeitpunkt im Song (Frames)
    CREATE INDEX IF NOT EXISTS fingerprints_hash ON fingerprints(hash);
    CREATE INDEX IF NOT EXISTS fingerprints_ref ON fingerprints(ref);
    CREATE TABLE IF NOT EXISTS misses(
      id INTEGER PRIMARY KEY, uid TEXT UNIQUE, ts REAL, host TEXT,
      kind TEXT,                     -- unerkannt | genre (Song erkannt, Genre unbekannt)
      source TEXT, level_db REAL,
      player TEXT,                   -- JSON: was der Player laut System gerade spielt (Titel/Künstler/Adresse)
      song TEXT,                     -- JSON: erkannter Song (nur bei kind=genre)
      details TEXT,                  -- JSON: Dienste, Fehler, Beinahe-Treffer, Tags …
      note TEXT DEFAULT '', sent REAL);
    CREATE INDEX IF NOT EXISTS misses_ts ON misses(ts);
    """,
]
SCHEMA_VERSION = len(MIGRATIONS)


def migrate(c: sqlite3.Connection) -> None:
    v = c.execute("PRAGMA user_version").fetchone()[0]
    if v > SCHEMA_VERSION:
        raise RuntimeError(f"Datenbank ist neuer (v{v}) als dieses Programm (v{SCHEMA_VERSION}) – bitte tunebridge aktualisieren.")
    for target in range(v + 1, SCHEMA_VERSION + 1):
        c.executescript("BEGIN;" + MIGRATIONS[target - 1] + f"PRAGMA user_version={target}; COMMIT;")


_migrated: set[str] = set()


@contextmanager
def _conn(path: Path | None = None):
    path = path or DB
    c = sqlite3.connect(path, timeout=15)
    c.row_factory = sqlite3.Row
    try:
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA foreign_keys=ON")
        if str(path) not in _migrated:
            migrate(c)
            _migrated.add(str(path))
            for f in (path, Path(f"{path}-wal"), Path(f"{path}-shm")):
                config.private(f)   # Datenbank nur für den eigenen Benutzer lesbar
        with c:  # Transaktion: commit bei Erfolg, rollback bei Fehler
            yield c
    finally:
        try:
            if c.total_changes:          # in diesem Prozess geschrieben → gemerkte Auswertungen ungültig
                global _GEN
                _GEN += 1
        except sqlite3.Error:
            pass
        c.close()


# ------------------------------------------------------------ Cache & Meta
# ------------------------------------------------------------------ RAM-Zwischenspeicher
# Häufig gelesene Einträge (Cache, Einstellungen) zusätzlich im Arbeitsspeicher – spart SQLite-Zugriffe.
# Gespeichert wird der JSON-Text (jeder Aufrufer bekommt eine eigene Kopie). Schreiben/Löschen geht
# immer zuerst in die Datenbank und aktualisiert bzw. leert dann den RAM – nie umgekehrt.
_RAM: OrderedDict = OrderedDict()
_RAM_MAX = 5000
_RAM_BIG = 256_000            # größere Einträge nicht im RAM halten
_ram_lock = threading.Lock()
_MISS = object()


def _ram_get(k):
    with _ram_lock:
        v = _RAM.get(k, _MISS)
        if v is not _MISS:
            _RAM.move_to_end(k)
        return v


def _ram_put(k, v) -> None:
    if isinstance(v, tuple) and isinstance(v[0], str) and len(v[0]) > _RAM_BIG:
        return
    with _ram_lock:
        _RAM[k] = v
        _RAM.move_to_end(k)
        while len(_RAM) > _RAM_MAX:
            _RAM.popitem(last=False)


def ram_clear() -> None:
    """Nach Löschen/Wiederherstellen: RAM-Kopien verwerfen."""
    with _ram_lock:
        _RAM.clear()
    memo_clear()


def cache_get(ns: str, key: str, max_age: float | None = None):
    k = ("c", str(DB), ns, key)
    hit = _ram_get(k)
    if hit is _MISS:
        with _conn() as c:
            r = c.execute("SELECT value, ts FROM cache WHERE ns=? AND key=?", (ns, key)).fetchone()
        hit = (r["value"], r["ts"]) if r else None
        _ram_put(k, hit)
    if not hit or (max_age and time.time() - hit[1] > max_age):
        return None
    return json.loads(hit[0])


def cache_set(ns: str, key: str, value) -> None:
    raw, ts = json.dumps(value, ensure_ascii=False), time.time()
    with _conn() as c:
        c.execute("INSERT OR REPLACE INTO cache(ns,key,value,ts) VALUES(?,?,?,?)", (ns, key, raw, ts))
    _ram_put(("c", str(DB), ns, key), (raw, ts))


def meta_get(key: str) -> str | None:
    k = ("m", str(DB), key)
    hit = _ram_get(k)
    if hit is _MISS:
        with _conn() as c:
            r = c.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        hit = r["value"] if r else None
        _ram_put(k, hit)
    return hit


def meta_set(key: str, value: str) -> None:
    with _conn() as c:
        c.execute("INSERT OR REPLACE INTO meta(key,value) VALUES(?,?)", (key, value))
    _ram_put(("m", str(DB), key), value)


# ------------------------------------------------------------------ Ergebnisse merken, bis sich die DB ändert
# Teure Auswertungen (Statistik, Playlist-Übersicht …) lesen zehntausende Songs. Jede Schreibung ändert die
# Datenbank- bzw. WAL-Datei (Größe/Zeit) – solange beide gleich sind, ist auch das Ergebnis gleich.
_GEN = 0      # Schreibzähler dieses Prozesses (Dateizeiten allein sind nur auf Millisekunden genau)


def db_stamp(*extra: Path) -> tuple:
    out = [_GEN]
    for f in (DB, Path(f"{DB}-wal"), *extra):
        try:
            st = os.stat(f)
            out.append((str(f), st.st_mtime_ns, st.st_size))
        except OSError:
            out.append((str(f), 0, 0))
    return tuple(out)


_MEMO: dict = {}
_memo_lock = threading.Lock()


def memo_db(*extra):
    """Dekorator: Ergebnis je Aufruf-Argumente merken, solange sich die Datenbank (und *extra – Pfade oder
    Funktionen, die Pfade liefern) nicht ändert. Jeder Aufrufer bekommt eine eigene Kopie."""
    import copy
    import functools

    def deco(fn):
        @functools.wraps(fn)
        def wrap(*a, **kw):
            paths = [Path(e() if callable(e) else e) for e in extra]
            stamp = db_stamp(*paths)
            k = (fn.__module__, fn.__qualname__, a, tuple(sorted(kw.items())))
            with _memo_lock:
                hit = _MEMO.get(k)
            if hit and hit[0] == stamp:
                return copy.deepcopy(hit[1])
            val = fn(*a, **kw)
            if db_stamp(*paths) == stamp:          # während der Berechnung nichts geschrieben → merken
                with _memo_lock:
                    _MEMO[k] = (stamp, val)
            return copy.deepcopy(val)
        wrap.uncached = fn
        return wrap
    return deco


def memo_clear() -> None:
    with _memo_lock:
        _MEMO.clear()


def track_key(t: Track) -> str:
    from .matching import normalize
    return t.isrc or f"{normalize(t.artist)}|{normalize(t.title)}"


def _t(raw: str) -> Track:
    return Track(**json.loads(raw))


# ------------------------------------------------------------ Verlauf
def add_recognition(source: str, engine: str, agreement: int, track: Track, extra: dict) -> int:
    with _conn() as c:
        cur = c.execute("INSERT INTO recognitions(uid,ts,host,source,engine,agreement,track,extra) VALUES(?,?,?,?,?,?,?,?)",
                        (uuid.uuid4().hex, time.time(), HOST, source, engine, agreement,
                         json.dumps(asdict(track), ensure_ascii=False), json.dumps(extra, ensure_ascii=False)))
        return cur.lastrowid


def recognitions_by_source(source: str, limit: int = 30_000) -> list[dict]:
    """Erkennungen einer Herkunft (z. B. „shazam-app“), neueste zuerst."""
    with _conn() as c:
        rows = c.execute("SELECT * FROM recognitions WHERE source=? ORDER BY ts DESC LIMIT ?", (source, limit)).fetchall()
    return [{**dict(r), "track": json.loads(r["track"]), "extra": json.loads(r["extra"])} for r in rows]


def history(limit: int = 50) -> list[dict]:
    with _conn() as c:
        rows = c.execute("SELECT * FROM recognitions ORDER BY ts DESC LIMIT ?", (limit,)).fetchall()
    return [{**dict(r), "track": json.loads(r["track"]), "extra": json.loads(r["extra"])} for r in rows]


def clear_history() -> int:
    """Erkennungsverlauf löschen (Playlists bleiben). -> Anzahl gelöschter Einträge."""
    with _conn() as c:
        return c.execute("DELETE FROM recognitions").rowcount


def clear_cache(ns_prefix: str | None = None) -> int:
    ram_clear()
    with _conn() as c:
        if ns_prefix:
            return c.execute("DELETE FROM cache WHERE ns LIKE ?", (ns_prefix + "%",)).rowcount
        return c.execute("DELETE FROM cache").rowcount


def delete_recognition(rid: int) -> bool:
    """Einen Eintrag aus dem Erkennungsverlauf löschen (z. B. „Falsch erkannt“). Playlists bleiben."""
    with _conn() as c:
        return c.execute("DELETE FROM recognitions WHERE id=?", (rid,)).rowcount > 0


def _rec(r) -> dict:
    return {**dict(r), "track": json.loads(r["track"]), "extra": json.loads(r["extra"] or "{}")}


def import_recognition(uid: str, ts: float, host: str, source: str, engine: str, agreement: int,
                       track: Track, extra: dict) -> bool:
    """Erkennung von einem anderen Gerät übernehmen (z. B. Handy). True = neu, False = gab es schon (gleiche uid)."""
    with _conn() as c:
        cur = c.execute("INSERT OR IGNORE INTO recognitions(uid,ts,host,source,engine,agreement,track,extra) "
                        "VALUES(?,?,?,?,?,?,?,?)",
                        (uid, ts, host, source, engine, agreement, json.dumps(asdict(track), ensure_ascii=False),
                         json.dumps(extra, ensure_ascii=False)))
        return cur.rowcount == 1


def update_recognition_extra_by_uid(uid: str, extra: dict) -> None:
    """Zusatzangaben ergänzen (z. B. „Stimmt“ am Handy) – Vorhandenes vom PC (Genre-Quelle, BPM …) bleibt."""
    with _conn() as c:
        r = c.execute("SELECT extra FROM recognitions WHERE uid=?", (uid,)).fetchone()
        if r:
            old = json.loads(r["extra"] or "{}")
            c.execute("UPDATE recognitions SET extra=? WHERE uid=?",
                      (json.dumps({**extra, **old, **{k: extra[k] for k in ("confirmed", "unsure") if k in extra}},
                                  ensure_ascii=False), uid))


def delete_recognition_uid(uid: str) -> bool:
    with _conn() as c:
        return c.execute("DELETE FROM recognitions WHERE uid=?", (uid,)).rowcount > 0


def recognitions_since(ts: float, limit: int = 500, exclude_prefix: str | None = None) -> list[dict]:
    """Erkennungen nach Zeitpunkt ts, älteste zuerst (zum portionsweisen Abgleichen)."""
    q, args = "SELECT * FROM recognitions WHERE ts > ?", [ts]
    if exclude_prefix:
        q += " AND uid NOT LIKE ?"
        args.append(exclude_prefix.replace("%", "") + "%")
    with _conn() as c:
        rows = c.execute(q + " ORDER BY ts LIMIT ?", (*args, limit)).fetchall()
    return [_rec(r) for r in rows]


def recognitions_by_uid(uids: list[str]) -> list[dict]:
    if not uids:
        return []
    with _conn() as c:
        rows = c.execute(f"SELECT * FROM recognitions WHERE uid IN ({','.join('?' * len(uids))})", uids).fetchall()
    return [_rec(r) for r in rows]


def playlist_names() -> list[str]:
    with _conn() as c:
        return [r[0] for r in c.execute("SELECT name FROM playlists ORDER BY name")]


def all_recognitions() -> list[dict]:
    with _conn() as c:
        rows = c.execute("SELECT id, track, extra FROM recognitions").fetchall()
    return [{"id": r["id"], "track": json.loads(r["track"]), "extra": json.loads(r["extra"])} for r in rows]


def update_recognition(rid: int, track: dict, extra: dict) -> None:
    with _conn() as c:
        c.execute("UPDATE recognitions SET track=?, extra=? WHERE id=?",
                  (json.dumps(track, ensure_ascii=False), json.dumps(extra, ensure_ascii=False), rid))


def all_entries() -> list[dict]:
    with _conn() as c:
        rows = c.execute("SELECT id, track FROM entries").fetchall()
    return [{"id": r["id"], "track": json.loads(r["track"])} for r in rows]


def update_entry(eid: int, track: dict) -> None:
    with _conn() as c:
        c.execute("UPDATE entries SET track=? WHERE id=?", (json.dumps(track, ensure_ascii=False), eid))


def get_recognition(rid: int) -> tuple[Track, dict] | None:
    with _conn() as c:
        r = c.execute("SELECT track, extra FROM recognitions WHERE id=?", (rid,)).fetchone()
    return (_t(r["track"]), json.loads(r["extra"])) if r else None


# ------------------------------------------------------------ Suche
def _like(q: str) -> str:
    return "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def _prefilter(words: list[str]) -> tuple[str, tuple]:
    """SQL-Vorfilter mit dem längsten ASCII-Wort (LIKE ignoriert Groß/klein nur bei ASCII) – Rest prüft _hit."""
    ascii_words = [w for w in words if w.isascii()]
    if not ascii_words:
        return "", ()
    return "WHERE track LIKE ? ESCAPE '\\'", (_like(max(ascii_words, key=len)),)


def _hit(d: dict, words: list[str]) -> bool:
    hay = " ".join([d.get("title") or "", *(d.get("artists") or []), d.get("album") or ""]).casefold()
    return all(w in hay for w in words)


def search_songs(q: str, limit: int = 30) -> list[dict]:
    """Songs in eigenen Playlists (je Song einmal, mit den Playlists, in denen er steckt)."""
    words = q.casefold().split()
    if not words:
        return []
    out: dict[str, dict] = {}
    with _conn() as c:
        where, args = _prefilter(words)
        # zeilenweise lesen statt alles auf einmal: bei vielen Treffern ist nach `limit` Songs Schluss
        for r in c.execute(f"SELECT playlist, track, key FROM entries {where} ORDER BY ts DESC LIMIT 20000", args):
            d = json.loads(r["track"])
            if not _hit(d, words):
                continue
            hit = out.setdefault(r["key"], {"key": r["key"], "title": d.get("title"), "artists": d.get("artists") or [],
                                             "cover": d.get("cover"), "preview_url": d.get("preview_url"), "isrc": d.get("isrc"),
                                             "ids": d.get("ids") or {}, "genre": d.get("genre"), "playlists": []})
            if r["playlist"] not in hit["playlists"]:
                hit["playlists"].append(r["playlist"])
            if len(out) >= limit:
                break
    return list(out.values())


def search_history(q: str, limit: int = 15) -> list[dict]:
    words = q.casefold().split()
    if not words:
        return []
    with _conn() as c:
        where, args = _prefilter(words)
        rows = c.execute(f"SELECT id, ts, track FROM recognitions {where} ORDER BY ts DESC LIMIT 5000", args).fetchall()
    out, seen = [], set()
    for r in rows:
        d = json.loads(r["track"])
        k = ((d.get("title") or "").casefold(), tuple(a.casefold() for a in d.get("artists") or []))
        if k in seen or not _hit(d, words):
            continue
        seen.add(k)
        out.append({"id": r["id"], "ts": r["ts"], "title": d.get("title"), "artists": d.get("artists") or [], "cover": d.get("cover")})
        if len(out) >= limit:
            break
    return out


def playlist_times() -> dict[str, tuple[float, float]]:
    """Name -> (angelegt, zuletzt geändert)."""
    with _conn() as c:
        rows = c.execute("SELECT p.name, p.created, MAX(e.ts) FROM playlists p LEFT JOIN entries e ON e.playlist = p.name GROUP BY p.name").fetchall()
    return {r[0]: (r[1] or 0, r[2] or r[1] or 0) for r in rows}


# ------------------------------------------------------------ Playlists
def local_playlists() -> list[Playlist]:
    with _conn() as c:
        pls = c.execute("SELECT name, description FROM playlists ORDER BY name").fetchall()
        out = []
        for p in pls:
            ts = c.execute("SELECT track FROM entries WHERE playlist=? ORDER BY ts", (p["name"],)).fetchall()
            out.append(Playlist(name=p["name"], description=p["description"], tracks=[_t(r["track"]) for r in ts]))
    return out


@memo_db()
def playlist_overview(top: int = 3, covers: int = 4) -> list[dict]:
    """Übersicht aller lokalen Playlists, ohne jeden Song in ein Track-Objekt zu entpacken (SQLite liest nur die
    drei Felder): name, count, covers (die letzten mit Bild, alt → neu), top = [(genre, subgenre, anzahl)]."""
    from collections import Counter
    with _conn() as c:
        names = [r[0] for r in c.execute("SELECT name FROM playlists ORDER BY name")]
        rows = c.execute("SELECT playlist, json_extract(track,'$.genre'), json_extract(track,'$.subgenre'),"
                         " json_extract(track,'$.cover') FROM entries ORDER BY playlist, ts").fetchall()
    dist: dict[str, Counter] = {}
    cov: dict[str, list] = {}
    for pl, g, sub, url in rows:
        dist.setdefault(pl, Counter())[(g, sub)] += 1          # Reihenfolge bei Gleichstand: zuerst gesehen
        if url:
            cov.setdefault(pl, []).append(url)
    out = []
    for n in names:
        d = dist.get(n, Counter())
        out.append({"name": n, "count": sum(d.values()), "covers": cov.get(n, [])[-covers:],
                    "top": [(g, sub, k) for (g, sub), k in d.most_common(top)]})
    return out


def add_to_playlist(name: str, track: Track) -> bool:
    """True = neu hinzugefügt, False = war schon drin."""
    with _conn() as c:
        c.execute("INSERT OR IGNORE INTO playlists(name, created) VALUES(?,?)", (name, time.time()))
        cur = c.execute("INSERT OR IGNORE INTO entries(playlist,track,key,ts,host) VALUES(?,?,?,?,?)",
                        (name, json.dumps(asdict(track), ensure_ascii=False), track_key(track), time.time(), HOST))
        return cur.rowcount == 1


def remove_from_playlist(name: str, key: str) -> None:
    with _conn() as c:
        c.execute("DELETE FROM entries WHERE playlist=? AND key=?", (name, key))


def exported_playlists() -> list[Playlist]:
    """Playlists aus Plattform-Exporten (data/exports/*.json) – für Vorschläge."""
    out = []
    for f in sorted((config.DATA / "exports").glob("*.json")):
        try:
            lib = Library.load(f)
        except (ValueError, KeyError):
            continue
        for p in lib.playlists:
            out.append(Playlist(name=f"{p.name}", tracks=p.tracks, ids={"source": lib.source, **p.ids}))
    return out


def delete_playlist(name: str) -> None:
    with _conn() as c:
        c.execute("DELETE FROM entries WHERE playlist=?", (name,))
        c.execute("DELETE FROM playlists WHERE name=?", (name,))


def rename_playlist(old: str, new: str) -> None:
    with _conn() as c:
        c.execute("INSERT OR IGNORE INTO playlists(name, created, description) "
                  "SELECT ?, created, description FROM playlists WHERE name=?", (new, old))
        c.execute("UPDATE OR IGNORE entries SET playlist=? WHERE playlist=?", (new, old))
        c.execute("DELETE FROM entries WHERE playlist=?", (old,))
        c.execute("DELETE FROM playlists WHERE name=?", (old,))


def playlist_entries(name: str) -> list[dict]:
    with _conn() as c:
        rows = c.execute("SELECT track, key, ts, host, pushed FROM entries WHERE playlist=? ORDER BY ts DESC",
                         (name,)).fetchall()
    return [{"track": json.loads(r["track"]), "key": r["key"], "ts": r["ts"], "host": r["host"],
             "pushed": bool(r["pushed"])} for r in rows]


def find_track(key: str) -> Track | None:
    with _conn() as c:
        r = c.execute("SELECT track FROM entries WHERE key=? LIMIT 1", (key,)).fetchone()
    return _t(r["track"]) if r else None


# ------------------------------------------------------------ Song-Speicher
def song_get(keys: list[str]) -> tuple[dict, dict, float] | None:
    keys = [k for k in keys if k]
    if not keys:
        return None
    with _conn() as c:
        r = c.execute(f"SELECT track, extra, ts FROM songs WHERE key IN ({','.join('?' * len(keys))}) "
                      "ORDER BY ts DESC LIMIT 1", keys).fetchone()
        if r:
            c.execute(f"UPDATE songs SET used=?, hits=hits+1 WHERE key IN ({','.join('?' * len(keys))})",
                      [time.time(), *keys])
    return (json.loads(r["track"]), json.loads(r["extra"]), r["ts"]) if r else None


def song_put(keys: list[str], track: dict, extra: dict) -> None:
    t, x, now = json.dumps(track, ensure_ascii=False), json.dumps(extra, ensure_ascii=False), time.time()
    with _conn() as c:
        for k in {k for k in keys if k}:
            c.execute("INSERT INTO songs(key,track,extra,ts,used,hits) VALUES(?,?,?,?,?,0) "
                      "ON CONFLICT(key) DO UPDATE SET track=excluded.track, extra=excluded.extra, ts=excluded.ts",
                      (k, t, x, now, now))


def tracks_by_genre(genre: str, sub: str | None = None, limit: int = 400) -> list[dict]:
    """Songs aus Song-Speicher und eigenen Playlists mit diesem Genre (und Subgenre) – nur lokal („Mix erstellen“)."""
    q = "json_extract(track,'$.genre') = ?" + (" AND json_extract(track,'$.subgenre') = ?" if sub else "")
    args = [genre, sub] if sub else [genre]
    with _conn() as c:
        rows = c.execute(f"SELECT track FROM entries WHERE {q} ORDER BY ts DESC LIMIT ?", [*args, limit]).fetchall()
        rows += c.execute(f"SELECT track FROM songs WHERE {q} ORDER BY used DESC LIMIT ?", [*args, limit]).fetchall()
    return [json.loads(r["track"]) for r in rows]


# ------------------------------------------------------------ Nicht erkannt / Genre unbekannt
def miss_add(kind: str, source: str, level_db: float | None, player: dict | None,
             song: dict | None, details: dict) -> int:
    now = time.time()
    with _conn() as c:
        if kind == "genre" and song:   # gleichen Song nicht mehrfach als „Genre unbekannt“ sammeln
            key = json.dumps(song, ensure_ascii=False)
            r = c.execute("SELECT id FROM misses WHERE kind='genre' AND song=?", (key,)).fetchone()
            if r:
                c.execute("UPDATE misses SET ts=?, details=? WHERE id=?",
                          (now, json.dumps(details, ensure_ascii=False), r["id"]))
                return r["id"]
        cur = c.execute("INSERT INTO misses(uid,ts,host,kind,source,level_db,player,song,details) VALUES(?,?,?,?,?,?,?,?,?)",
                        (uuid.uuid4().hex, now, HOST, kind, source, level_db,
                         json.dumps(player, ensure_ascii=False) if player else None,
                         json.dumps(song, ensure_ascii=False) if song else None,
                         json.dumps(details, ensure_ascii=False)))
        c.execute("DELETE FROM misses WHERE id NOT IN (SELECT id FROM misses ORDER BY ts DESC LIMIT 1000)")
        return cur.lastrowid


def misses(limit: int = 300) -> list[dict]:
    with _conn() as c:
        rows = c.execute("SELECT * FROM misses ORDER BY ts DESC LIMIT ?", (limit,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        for k in ("player", "song", "details"):
            d[k] = json.loads(d[k]) if d[k] else None
        out.append(d)
    return out


def miss_update(mid: int, note: str | None = None, sent: float | None = None) -> None:
    with _conn() as c:
        if note is not None:
            c.execute("UPDATE misses SET note=? WHERE id=?", (note[:500], mid))
        if sent is not None:
            c.execute("UPDATE misses SET sent=? WHERE id=?", (sent, mid))


def miss_delete(ids: list[int] | None = None) -> int:
    with _conn() as c:
        if ids is None:
            return c.execute("DELETE FROM misses").rowcount
        return c.execute(f"DELETE FROM misses WHERE id IN ({','.join('?' * len(ids))})", ids).rowcount


# ------------------------------------------------------------ Lokale Fingerabdrücke
FP_PER_REF = 40_000   # ~ 10 Aufnahmen je Song – ältere fallen raus


def fp_add(ref: str, hashes: list[tuple[int, int]]) -> None:
    if not hashes:
        return
    with _conn() as c:
        c.executemany("INSERT INTO fingerprints(hash,ref,t) VALUES(?,?,?)", [(h, ref, t) for h, t in hashes])
        n = c.execute("SELECT COUNT(*) FROM fingerprints WHERE ref=?", (ref,)).fetchone()[0]
        if n > FP_PER_REF:
            c.execute("DELETE FROM fingerprints WHERE rowid IN (SELECT rowid FROM fingerprints WHERE ref=? "
                      "ORDER BY rowid LIMIT ?)", (ref, n - FP_PER_REF))


def fp_lookup(hashes: list[int]) -> list[tuple[int, str, int]]:
    out = []
    uniq = list(set(hashes))
    with _conn() as c:
        for i in range(0, len(uniq), 900):
            part = uniq[i:i + 900]
            out += [tuple(r) for r in c.execute(
                f"SELECT hash, ref, t FROM fingerprints WHERE hash IN ({','.join('?' * len(part))})", part)]
    return out


# ------------------------------------------------------------ Speicherverbrauch
CACHE_GROUPS = {   # Präfix im Cache -> (Kennung, Anzeige)
    "lastfm_similar": ("similar", "Ähnliche Songs"),
    "lastfm": ("tags", "Genre-Tags (Last.fm)"),
    "links": ("links", "Plattform-Links"),
}


def storage() -> dict:
    """Wie viel liegt wo? (Zeilen + ungefähre Bytes je Bereich)"""
    with _conn() as c:
        q = lambda sql, *a: c.execute(sql, a).fetchone()  # noqa: E731
        songs = q("SELECT COUNT(DISTINCT track), COALESCE(SUM(LENGTH(track)+LENGTH(extra)),0) FROM songs")
        fps = q("SELECT COUNT(*), COUNT(DISTINCT ref) FROM fingerprints")
        rec = q("SELECT COUNT(*), COALESCE(SUM(LENGTH(track)+LENGTH(extra)),0) FROM recognitions")
        mis = q("SELECT COUNT(*), COALESCE(SUM(LENGTH(COALESCE(player,''))+LENGTH(COALESCE(song,''))+LENGTH(details)),0) FROM misses")
        gen = q("SELECT COUNT(*), COALESCE(SUM(LENGTH(songs)+LENGTH(cooc)+LENGTH(COALESCE(llm,''))),0) FROM genre_terms")
        cache: dict[str, list] = {}
        for ns, n, b in c.execute("SELECT ns, COUNT(*), COALESCE(SUM(LENGTH(value)),0) FROM cache GROUP BY ns"):
            gid = next((g[0] for p, g in CACHE_GROUPS.items() if ns.startswith(p)), "other")
            cur = cache.setdefault(gid, [0, 0])
            cur[0] += n
            cur[1] += b
    return {"songs": {"count": songs[0], "bytes": songs[1]},
            "fingerprints": {"count": fps[0], "songs": fps[1], "bytes": fps[0] * 24},
            "recognitions": {"count": rec[0], "bytes": rec[1]},
            "genre_terms": {"count": gen[0], "bytes": gen[1]},
            "misses": {"count": mis[0], "bytes": mis[1]},
            "cache": {k: {"count": v[0], "bytes": v[1]} for k, v in cache.items()},
            "db_bytes": sum(p.stat().st_size for p in DB.parent.glob(DB.name + "*") if p.is_file())}


def clear_table(name: str) -> int:
    assert name in ("songs", "fingerprints", "misses")
    with _conn() as c:
        return c.execute(f"DELETE FROM {name}").rowcount


def clear_cache_group(gid: str) -> int:
    ram_clear()
    with _conn() as c:
        if gid == "other":
            cond = " AND ".join("ns NOT LIKE ?" for _ in CACHE_GROUPS)
            return c.execute(f"DELETE FROM cache WHERE {cond}", [p + "%" for p in CACHE_GROUPS]).rowcount
        pre = [p for p, g in CACHE_GROUPS.items() if g[0] == gid]
        n = 0
        for p in pre:
            if gid == "tags":   # „lastfm“ ohne „lastfm_similar“
                n += c.execute("DELETE FROM cache WHERE ns LIKE ? AND ns NOT LIKE 'lastfm_similar%'", (p + "%",)).rowcount
            else:
                n += c.execute("DELETE FROM cache WHERE ns LIKE ?", (p + "%",)).rowcount
        return n


def vacuum() -> None:
    """Gelöschten Platz wirklich freigeben (Datei schrumpft)."""
    c = sqlite3.connect(DB, timeout=15)
    try:
        c.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        c.execute("VACUUM")
    finally:
        c.close()


def bump_saved(kind: str, n: int = 1) -> None:
    """Zähler: so viele Online-Abfragen hat der Speicher schon erspart."""
    with _conn() as c:
        r = c.execute("SELECT value FROM meta WHERE key='saved_calls'").fetchone()
        d = json.loads(r["value"]) if r else {}
        d[kind] = d.get(kind, 0) + n
        c.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('saved_calls',?)", (json.dumps(d),))
    _ram_put(("m", str(DB), "saved_calls"), json.dumps(d))


def saved_calls() -> dict:
    raw = meta_get("saved_calls")
    return json.loads(raw) if raw else {}


def stats() -> dict:
    with _conn() as c:
        return {
            "recognitions": c.execute("SELECT COUNT(*) FROM recognitions").fetchone()[0],
            "playlists": c.execute("SELECT COUNT(*) FROM playlists").fetchone()[0],
            "entries": c.execute("SELECT COUNT(*) FROM entries").fetchone()[0],
            "schema": c.execute("PRAGMA user_version").fetchone()[0],
        }

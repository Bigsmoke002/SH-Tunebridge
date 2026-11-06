"""Automatisches Senden an den Server des Entwicklers – NUR mit Einwilligung (siehe consent.py).

Kategorien (jede einzeln erlaubt oder nicht):
* misses  – Einträge der Liste „Nicht erkannt / Genre unbekannt“ (wie in der Vorschau)
* fehler  – kurze Fehlerberichte: Bereich, Meldung, Fehlertyp, Programmstelle (Datei:Zeile).
            Benutzername, Rechnername, Home-Pfad und Schlüssel werden geschwärzt.
* songs   – erkannte Songs mit Genre-Ergebnis (Künstler, Titel, ISRC, Genre, Sicherheit, Quelle)
* genres  – eigene Genre-Einordnungen für die Gemeinschafts-Datenbank (Künstler, Titel, ISRC, Genre, Subgenre,
            Herkunft playlist/app/ki/korrektur – nie der Playlist-Name)
* genredb – (kein Senden) die signierte Gemeinschafts-Datenbank laden
Nie gesendet: Ton, Rechner-/Gerätenamen, Konten, Playlists, IP-Speicherung beim Server.
Zeitangaben nur als Datum (kein Uhrzeit-Profil).
"""

from __future__ import annotations

import asyncio
import json
import threading
import time
import traceback
import uuid

from . import config, consent, store
from . import debuglog as dbg

QUEUE = config.DATA / "fehler-warteschlange.json"
MAX_ERRORS = 50
INTERVAL_S = 6 * 3600
_lock = threading.Lock()


def _day(ts: float) -> str:
    return time.strftime("%Y-%m-%d", time.localtime(ts))


# ------------------------------------------------------------------ Fehler sammeln
def _load() -> list[dict]:
    try:
        return json.loads(QUEUE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def note_error(area: str, msg: str, exc: BaseException | None) -> None:
    """Wird von debuglog.error aufgerufen. Tut nichts ohne Einwilligung „fehler“."""
    try:
        if not consent.server("fehler"):
            return
        where = []
        if exc is not None and exc.__traceback__:
            where = [f"{f.filename.rsplit('/tunebridge/', 1)[-1]}:{f.lineno} {f.name}"
                     for f in traceback.extract_tb(exc.__traceback__)[-4:]]
        e = {"uid": uuid.uuid4().hex, "zeit": _day(time.time()), "art": "fehler",
             "details": {"bereich": area[:40], "meldung": dbg._redact(msg)[:300],
                         "fehler": dbg._redact(f"{type(exc).__name__}: {exc}")[:500] if exc else None,
                         "stelle": [dbg._redact(w) for w in where]}}
        with _lock:
            q = _load()
            # gleiche Meldung an gleicher Stelle nur einmal
            sig = (e["details"]["bereich"], e["details"]["meldung"], tuple(e["details"]["stelle"]))
            if any((x["details"]["bereich"], x["details"]["meldung"], tuple(x["details"]["stelle"])) == sig for x in q):
                return
            q = (q + [e])[-MAX_ERRORS:]
            QUEUE.write_text(json.dumps(q, ensure_ascii=False), encoding="utf-8")
            QUEUE.chmod(0o600)
    except Exception:
        pass        # Fehlerbericht darf nie selbst Fehler auslösen


def pending_errors() -> list[dict]:
    return _load()


def clear_errors() -> None:
    QUEUE.unlink(missing_ok=True)


# ------------------------------------------------------------------ Songs (Genre-Analyse)
_SONGS_SINCE = "outbox:songs_since"
_MISSES_SINCE = "outbox:misses_since"


def song_entries(limit: int = 200) -> list[dict]:
    since = float(store.meta_get(_SONGS_SINCE) or 0)
    out = []
    for r in reversed(store.history(1000)):
        if r["ts"] <= since:
            continue
        t, x = r["track"], r["extra"]
        out.append({"uid": r["uid"], "zeit": _day(r["ts"]), "art": "erkannt", "_ts": r["ts"],
                    "song": {"artist": ", ".join(t.get("artists") or []), "title": t.get("title"), "isrc": t.get("isrc")},
                    "details": {"genre": t.get("genre"), "subgenre": t.get("subgenre"), "nische": t.get("niche"),
                                "sicherheit": x.get("confidence"), "genre_quelle": x.get("genre_source"),
                                "dienst": r["engine"], "tempo": x.get("speed"),
                                "ki_hinweis": (x.get("ai") or {}).get("status")}})
        if len(out) >= limit:
            break
    return out


def _vote_ts(e: dict) -> float:
    return float(e.get("_ts") or 0)


# ------------------------------------------------------------------ Senden
def _package(entries: list[dict]) -> dict:
    from . import __version__
    return {"app": "SH-Tunebridge", "version": __version__, "format": 1,
            "eintraege": [{k: v for k, v in e.items() if not k.startswith("_")} for e in entries]}


def flush(auto: bool = False) -> dict:
    """Alles senden, was erlaubt ist und noch nicht gesendet wurde. -> {kategorie: anzahl}
    auto=True: Hintergrund-Abgleich (Gemeinschafts-Teil nur im Modus „auto“)."""
    from . import upload
    from .web.app import _miss_export
    done: dict = {}
    if consent.server("misses"):
        since = float(store.meta_get(_MISSES_SINCE) or 0)
        ids = [m["id"] for m in store.misses(1000) if not m.get("sent") and m["ts"] >= since]
        if ids:
            data = _miss_export(ids)
            upload.send(data)
            now = time.time()
            for i in ids:
                store.miss_update(i, sent=now)
            done["misses"] = len(ids)
    if consent.server("fehler") and (q := pending_errors()):
        upload.send(_package(q))
        with _lock:
            rest = [e for e in _load() if e["uid"] not in {x["uid"] for x in q}]
            QUEUE.write_text(json.dumps(rest), encoding="utf-8") if rest else clear_errors()
        done["fehler"] = len(q)
    from . import community
    if not auto or community.mode() == "auto":   # Gemeinschaft: bei „manuell“ nur über den Knopf
        community.send_part(done)
    if consent.server("songs") and (s := song_entries()):
        upload.send(_package(s))
        store.meta_set(_SONGS_SINCE, str(max(e["_ts"] for e in s)))
        done["songs"] = len(s)
    if done:
        dbg.event("senden", "Automatisch gesendet", **done)
    return done


async def loop() -> None:
    """Hintergrund: 2 Minuten nach Start, danach alle 6 Stunden – nur wenn etwas erlaubt ist."""
    await asyncio.sleep(120)
    while True:
        if consent.server_any() or consent.server("genredb"):   # Senden bzw. Genre-Datei laden
            try:
                await asyncio.to_thread(flush, True)
            except Exception as e:     # Server nicht erreichbar o. Ä. – beim nächsten Mal wieder
                dbg.problem("senden", f"Automatisches Senden fehlgeschlagen: {e}")
        await asyncio.sleep(INTERVAL_S)

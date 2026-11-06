"""Abgleich mit der Gemeinschafts-Genre-Datenbank (Einstellungen › Gemeinschaft).

Drei Einwilligungen (alle AUS, bis der Nutzer sie erlaubt – siehe consent.py):
* genres      – eigene Einordnungen (von dir festgelegt / aus Playlist-Namen / beim Sortieren gelernt)
* bibliothek  – Song → Genre für die Songs in deinem Song-Speicher. WICHTIG: Das Genre wird dafür NEU und NUR aus
                freien Quellen abgeleitet – MusicBrainz-Tags (CC0, schon im Zwischenspeicher) und Genre-Angaben im Titel.
                Last.fm-, Deezer-, Apple-Daten fließen NICHT in die Gemeinschafts-Datenbank (Nutzungsbedingungen,
                Datenbankschutz § 87b UrhG) – sie dienen nur der Einordnung auf dem eigenen Rechner.
* genredb     – die fertige, signierte Gemeinschafts-Datenbank laden

Modus: „auto“ = beim Hintergrund-Abgleich alle 6 Std. mit, „manuell“ = nur per Knopf „Jetzt abgleichen“.

Gesendet wird je Song nur: Künstler, Titel, ISRC, Genre, Subgenre, Herkunft, Sicherheit – nie Playlist-Namen,
Playlists, Konten, Hörzeiten. Grenzen: höchstens LIB_PER_SYNC Bibliotheks-Songs pro Abgleich und LIB_MAX insgesamt
(der Server nimmt pro Installation 5000 Einträge aller Arten an – es soll Platz für den Rest bleiben).
"""
from __future__ import annotations

import json
import time
import uuid

from . import consent, store
from . import debuglog as dbg

MODES = ("auto", "manuell")
_MODE = "community:mode"
_LAST = "community:last"
LIB_PER_SYNC = 400          # 2 Sendungen à 200
LIB_MAX = 2000              # insgesamt pro Installation
MIN_CONF = 0.5              # unsichere Genres nicht beitragen
_SCHEMA = "CREATE TABLE IF NOT EXISTS community_sent(key TEXT PRIMARY KEY, uid TEXT, ts REAL)"


def mode() -> str:
    m = store.meta_get(_MODE) or "auto"
    return m if m in MODES else "auto"


def set_mode(m: str) -> str:
    if m not in MODES:
        raise ValueError("Unbekannter Modus")
    store.meta_set(_MODE, m)
    return m


def _sent_keys(c) -> set[str]:
    c.execute(_SCHEMA)
    return {r[0] for r in c.execute("SELECT key FROM community_sent")}


def lib_sent_count() -> int:
    with store._conn() as c:
        c.execute(_SCHEMA)
        return c.execute("SELECT COUNT(*) FROM community_sent").fetchone()[0]


def free_genre(t: dict) -> dict | None:
    """Genre nur aus freien Quellen: MusicBrainz-Tags (CC0, aus dem Zwischenspeicher – keine neue Anfrage) und
    Genre-Angaben im Titel. Unsicher (< MIN_CONF) oder nichts gefunden -> None."""
    from .enrich import title_tags
    from .genres import classify
    from .genres.sources import musicbrainz
    from .models import Track
    tr = Track(title=t["title"], artists=list(t["artists"]), isrc=t.get("isrc"))
    mb = musicbrainz.tags_cached(tr) or {}
    tt = title_tags(tr) or {}
    if not mb and not tt:
        return None
    tags = dict(mb)
    for k, v in tt.items():
        tags[k] = max(tags.get(k, 0), v)
    c = classify(tags)
    if not c.genre or c.confidence < MIN_CONF:
        return None
    return {"genre": c.genre, "subgenre": c.subgenre, "confidence": round(float(c.confidence), 2),
            "quelle": "+".join(q for q, d in (("musicbrainz", mb), ("titel", tt)) if d)}


def lib_entries(limit: int = LIB_PER_SYNC) -> list[dict]:
    """Noch nicht beigetragene Songs aus dem Song-Speicher (ein Eintrag je Song, nicht je Schlüssel)."""
    from . import genredb
    with store._conn() as c:
        sent = _sent_keys(c)
        rows = c.execute("SELECT key, track FROM songs ORDER BY ts").fetchall()
    with genredb._conn() as c:
        genredb._ensure(c)
        own = {r[0] for r in c.execute("SELECT key FROM genre_votes")} | \
              {r[0] for r in c.execute("SELECT alt FROM genre_votes WHERE alt IS NOT NULL")}
    room = max(0, LIB_MAX - len(sent))
    out, seen = [], set()
    for r in rows:
        if len(out) >= min(limit, room):
            break
        try:
            t = json.loads(r["track"])
        except ValueError:
            continue
        if not t.get("genre") or not t.get("title") or not t.get("artists"):
            continue
        keys = genredb.keys_of(t["artists"], t["title"], t.get("isrc"))
        if keys[0] in seen or keys[0] in sent or any(k in own for k in keys):   # eigene Einordnung geht vor
            continue
        seen.add(keys[0])
        free = free_genre(t)
        if not free or free["genre"] != t["genre"]:   # Gegenprobe: nur, wenn die App auf dasselbe Genre kommt
            continue
        out.append({"uid": uuid.uuid4().hex, "zeit": time.strftime("%Y-%m-%d"), "art": "genre",
                    "song": {"artist": ", ".join(t["artists"]), "title": t["title"], "isrc": t.get("isrc")},
                    "details": {"genre": free["genre"], "subgenre": free["subgenre"], "herkunft": "bibliothek",
                                "sicherheit": free["confidence"], "quelle": free["quelle"], "schluessel": keys},
                    "_key": keys[0]})
    return out


def _mark_lib(entries: list[dict]) -> None:
    now = time.time()
    with store._conn() as c:
        c.execute(_SCHEMA)
        c.executemany("INSERT OR IGNORE INTO community_sent(key, uid, ts) VALUES(?,?,?)",
                      [(e["_key"], e["uid"], now) for e in entries])


def send_part(done: dict, force_db: bool = False) -> None:
    """Gemeinschafts-Teil des Abgleichs (wird von outbox.flush und vom Knopf genutzt)."""
    from . import genredb, outbox, upload
    if consent.server("genres"):
        since = float(store.meta_get("outbox:genres_since") or 0)
        g = [e for e in genredb.upload_entries(1000) if outbox._vote_ts(e) >= since][:200]
        if g:
            upload.send(outbox._package(g))
            genredb.mark_sent([e["_key"] for e in g])
            done["genres"] = len(g)
    if consent.server("bibliothek") and (lib := lib_entries()):
        upload.send(outbox._package(lib))
        _mark_lib(lib)
        done["bibliothek"] = len(lib)
    if consent.server("genredb"):
        r = genredb.update(force=force_db)
        if r.get("updated"):
            done["genredb"] = r.get("songs")
    store.meta_set(_LAST, json.dumps({"ts": time.time(), **done}))


def sync() -> dict:
    """Knopf „Jetzt abgleichen“: senden, was erlaubt ist, und die Datenbank neu holen."""
    if not any(consent.server(k) for k in ("genres", "bibliothek", "genredb")):
        raise PermissionError("Nichts erlaubt – bitte erst auswählen, was du teilen bzw. laden möchtest")
    done: dict = {}
    send_part(done, force_db=True)
    dbg.event("gemeinschaft", "Abgleich von Hand", **done)
    return done


def status() -> dict:
    from . import genredb
    try:
        last = json.loads(store.meta_get(_LAST) or "null")
    except ValueError:
        last = None
    sent = lib_sent_count()
    return {"mode": mode(), "last": last,
            "consent": {k: consent.server(k) for k in ("genres", "bibliothek", "genredb")},
            "privacy": bool(consent.get()["privacy_at"]), "domain": consent.get()["server"]["domain"],
            "votes_pending": len(genredb.upload_entries(1000)), "votes": genredb.counts(),
            "lib_pending": len(lib_entries(LIB_MAX)), "lib_sent": sent, "lib_max": LIB_MAX,
            "lib_per_sync": LIB_PER_SYNC, "community": genredb.community_info(),
            "checked": float(store.meta_get("genredb:checked") or 0) or None}

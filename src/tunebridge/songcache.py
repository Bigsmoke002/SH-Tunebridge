"""Song-Speicher: bekannte Songs nicht jedes Mal neu online nachschlagen.

Erkennt Shazam (oder der lokale Wiedererkenner) einen Song, den die App schon kennt, kommen
Genre, Cover, Hörprobe, BPM und Links aus der lokalen Datenbank – 0 Anfragen an Deezer,
Last.fm und iTunes. Das Genre wird dabei offline neu berechnet, damit dazugelernte Genres greifen.

Frisch nachgeschlagen wird nur, wenn der Eintrag älter als MAX_AGE ist, etwas Wichtiges fehlt
(dann höchstens einmal pro Tag) oder der Nutzer „Neu laden“ drückt.
"""

from __future__ import annotations

import time

from . import debuglog as dbg
from . import store
from .matching import normalize
from .models import Track
from .recognize.engines import Recognition

MAX_AGE = 30 * 86400
RETRY_INCOMPLETE = 86400
GENRE_CHECK = 4      # 2 = geprüfter Künstler + Titel (Namensvettern), 3 = Genre aus dem Titel (Tekk), 4 = Schranz. Ältere Einträge einmal neu.


def keys(rec: Recognition | Track) -> list[str]:
    artists = rec.artists
    out = []
    if rec.isrc:
        out.append(rec.isrc.upper())
    out.append(f"{normalize(artists[0] if artists else '')}|{normalize(rec.title)}")
    return out


def primary_key(rec: Recognition | Track) -> str:
    return keys(rec)[0]


def _complete(track: dict, extra: dict) -> bool:
    return bool(track.get("genre") and (extra.get("cover") or extra.get("preview_url")))


def lookup(rec: Recognition) -> tuple[Track, dict] | None:
    got = store.song_get(keys(rec))
    if not got:
        return None
    track, extra, ts = got
    age = time.time() - ts
    if extra.get("gcheck", 0) < GENRE_CHECK:
        return None
    if age > MAX_AGE or (not _complete(track, extra) and age > RETRY_INCOMPLETE):
        dbg.event("speicher", "Bekannt, aber veraltet/unvollständig – neu nachschlagen",
                  song=f"{rec.artists} – {rec.title}", alter_tage=round(age / 86400, 1))
        return None
    from .genres.learn import reapply
    reapply(track, extra)
    t = Track(**{k: v for k, v in track.items() if k in Track.__dataclass_fields__})
    extra = {**extra, "cached": ts, "speed": rec.speed}
    # Version/Tempo gehören zur gerade gehörten Aufnahme, nicht zum gespeicherten Song
    from .versions import speed_label, split_version
    _, _, version = split_version(rec.title, rec.artists)
    if not version and rec.speed and abs(rec.speed - 1) > 0.03:
        version = speed_label(rec.speed)
    extra["version"] = version
    extra["links"] = {**(extra.get("links") or {}), **rec.links}
    store.bump_saved("lookups")
    dbg.event("speicher", "Aus dem Song-Speicher – keine Online-Abfrage", song=f"{t.artist} – {t.title}",
              genre=f"{t.genre}/{t.subgenre}/{t.niche}", alter_tage=round(age / 86400, 1))
    return t, extra


def save(rec: Recognition, track: Track, extra: dict) -> None:
    from dataclasses import asdict
    keep = {k: v for k, v in extra.items() if k not in ("cached", "speed", "version", "engines",
                                                          "agreement", "alternatives")}
    keep["gcheck"] = GENRE_CHECK
    store.song_put(keys(rec) + keys(track), asdict(track), keep)


def lookup_key(key: str) -> tuple[Track, dict] | None:
    """Für den lokalen Wiedererkenner: Song direkt über seinen Schlüssel holen (ohne Altersprüfung)."""
    got = store.song_get([key])
    if not got:
        return None
    track, extra, ts = got
    from .genres.learn import reapply
    reapply(track, extra)
    return Track(**{k: v for k, v in track.items() if k in Track.__dataclass_fields__}), {**extra, "cached": ts}


def backfill() -> int:
    """Einmalig: bisher erkannte Songs aus dem Verlauf in den Song-Speicher übernehmen."""
    if store.meta_get("songcache_backfill"):
        return 0
    n = 0
    for r in sorted(store.all_recognitions(), key=lambda r: r["id"]):   # neuere überschreiben ältere
        t, x = r["track"], r["extra"]
        if not t.get("title"):
            continue
        tr = Track(**{k: v for k, v in t.items() if k in Track.__dataclass_fields__})
        keep = {k: v for k, v in x.items() if k not in ("cached", "speed", "version", "engines",
                                                        "agreement", "alternatives", "local")}
        store.song_put(keys(tr), t, keep)
        n += 1
    store.meta_set("songcache_backfill", "1")
    dbg.event("speicher", "Song-Speicher aus Verlauf gefüllt", songs=n)
    return n

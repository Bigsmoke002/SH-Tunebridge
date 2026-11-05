"""Statistik & Jahresrückblick – nur aus der eigenen Datenbank, nichts verlässt den Rechner.

Quellen: „erkannt“ (Verlauf der Erkennungen) und „playlists“ (Songs in deinen lokalen Playlists, Datum = wann
hinzugefügt); „alle“ = beides, jeder Song einmal (frühestes Datum zählt).
Tempo kommt aus der Erkennung (Deezer) oder aus schon gemessenen Hörproben – es wird nichts nachgeladen.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime

from . import store
from .matching import normalize
from .versions import main_artist

SOURCES = ("alle", "erkannt", "playlists")
MONTHS = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]


def _events(source: str) -> list[dict]:
    ev: list[dict] = []
    if source in ("alle", "erkannt"):
        with store._conn() as c:
            for r in c.execute("SELECT ts, track, extra FROM recognitions").fetchall():
                t, x = json.loads(r["track"]), json.loads(r["extra"] or "{}")
                ev.append({"ts": r["ts"], "t": t, "bpm": x.get("bpm"), "src": "erkannt"})
    if source in ("alle", "playlists"):
        with store._conn() as c:
            for r in c.execute("SELECT ts, track FROM entries").fetchall():
                ev.append({"ts": r["ts"], "t": json.loads(r["track"]), "bpm": None, "src": "playlists"})
    if source == "alle":                         # jeder Song einmal – frühestes Datum
        first: dict[str, dict] = {}
        for e in sorted(ev, key=lambda e: e["ts"] or 0):
            first.setdefault(_song(e["t"]), e)
        ev = list(first.values())
    return [e for e in ev if e["ts"]]


def _song(t: dict) -> str:
    arts = t.get("artists") or [""]
    return t.get("isrc") or f"{normalize(arts[0])}|{normalize(t.get('title') or '')}"


def _artist(t: dict) -> tuple[str, str]:
    arts = t.get("artists") or []
    name = main_artist(arts[0]).strip() if arts else ""
    return normalize(name), name


def _bpm(e: dict) -> float | None:
    if e["bpm"]:
        return float(e["bpm"])
    t = e["t"]
    key = t.get("isrc") or f"{normalize(', '.join(t.get('artists') or []))}|{normalize(t.get('title') or '')}"
    f = store.cache_get("audiofeat", key)
    return float(f["bpm"]) if f and f.get("bpm") else None


def years(source: str = "alle") -> list[int]:
    return sorted({datetime.fromtimestamp(e["ts"]).year for e in _events(source)}, reverse=True)


def overview(year: int | None = None, source: str = "alle") -> dict:
    source = source if source in SOURCES else "alle"
    allev = _events(source)
    first_artist: dict[str, float] = {}
    for e in sorted(allev, key=lambda e: e["ts"]):
        k, _ = _artist(e["t"])
        if k:
            first_artist.setdefault(k, e["ts"])
    ev = [e for e in allev if year is None or datetime.fromtimestamp(e["ts"]).year == year]

    genres, subs, artists, names = Counter(), Counter(), Counter(), {}
    per_month, new_month = [0] * 12, [0] * 12
    bpm_bins: Counter = Counter()
    songs, bpm_known = set(), 0
    for e in ev:
        t = e["t"]
        songs.add(_song(t))
        if t.get("genre"):
            genres[t["genre"]] += 1
            if t.get("subgenre"):
                subs[(t["genre"], t["subgenre"])] += 1
        k, name = _artist(t)
        if k:
            artists[k] += 1
            names.setdefault(k, name)
        per_month[datetime.fromtimestamp(e["ts"]).month - 1] += 1
        if (b := _bpm(e)) and 50 <= b <= 220:
            bpm_bins[int(b // 10 * 10)] += 1
            bpm_known += 1
    new_artists = [k for k, ts in first_artist.items() if year is None or datetime.fromtimestamp(ts).year == year]
    for k in new_artists:
        new_month[datetime.fromtimestamp(first_artist[k]).month - 1] += 1
    lo, hi = (min(bpm_bins), max(bpm_bins)) if bpm_bins else (0, -10)
    return {
        "year": year, "source": source, "years": sorted({datetime.fromtimestamp(e["ts"]).year for e in allev}, reverse=True),
        "zahlen": {"eintraege": len(ev), "songs": len(songs), "kuenstler": len(artists), "neue_kuenstler": len(new_artists),
                   "genres": len(genres), "mit_tempo": bpm_known},
        "genres": [{"genre": g, "n": n} for g, n in genres.most_common(10)],
        "subgenres": [{"genre": g, "subgenre": s, "n": n} for (g, s), n in subs.most_common(10)],
        "kuenstler": [{"name": names[k], "n": n} for k, n in artists.most_common(10)],
        "monate": [{"monat": MONTHS[m], "n": per_month[m], "neu": new_month[m]} for m in range(12)] if year else None,
        "tempo": [{"von": b, "n": bpm_bins.get(b, 0)} for b in range(lo, hi + 10, 10)],
        "unsortiert": len(ev) - sum(genres.values()),
    }

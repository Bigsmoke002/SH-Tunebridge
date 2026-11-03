"""Mikro-Genre-Prüfstand, Stufe 1: Metadaten sammeln (Deezer, Apple, Last.fm, MusicBrainz). Kein Audio.
Aufruf: TUNEBRIDGE_DATA=$(mktemp -d) uv run python scripts/genre_bench/micro_collect.py out.json"""
import json
import os
import sys
import time

import httpx

sys.path.insert(0, os.path.dirname(__file__))
from micro import MICRO  # noqa: E402

from tunebridge import enrich  # noqa: E402
from tunebridge.links import itunes_song  # noqa: E402
from tunebridge.matching import normalize  # noqa: E402
from tunebridge.models import Track  # noqa: E402
from tunebridge.recognize.engines import Recognition  # noqa: E402

enrich.llm_genre = lambda t: None
enrich.llm_subgenre = lambda t, g, provider=None: None

MB = "https://musicbrainz.org/ws/2"
mb = httpx.Client(timeout=20, headers={"User-Agent": "SH-Tunebridge-genretest/0.4 (https://github.com/Bigsmoke002/SH-Tunebridge)"})
_last = [0.0]
_artist_cache: dict = {}


def mb_get(path, **params):
    wait = 1.1 - (time.time() - _last[0])
    if wait > 0:
        time.sleep(wait)
    _last[0] = time.time()
    for _ in range(3):
        r = mb.get(f"{MB}/{path}", params={"fmt": "json", **params})
        if r.status_code == 503:
            time.sleep(2)
            continue
        return r.json()
    return {}


def _tags(obj):
    out = {}
    for t in (obj.get("tags") or []) + (obj.get("genres") or []):
        if t.get("count", 0) > 0:
            out[t["name"].lower()] = max(out.get(t["name"].lower(), 0), t["count"])
    return out


def musicbrainz(artist, title):
    """-> {recording, release_group, artist} Tag-Dicts (Zählungen = Stimmen)."""
    q = f'recording:"{title}" AND artist:"{artist}"'
    recs = mb_get("recording", query=q, limit=5).get("recordings") or []
    na = normalize(artist)
    rec = next((r for r in recs if r.get("score", 0) >= 85 and any(
        normalize(c.get("name", "")) in na or na in normalize(c.get("name", ""))
        for c in r.get("artist-credit", []) if isinstance(c, dict))), None)
    if not rec:
        return {}
    out = {"recording": {}, "release_group": {}, "artist": {}}
    full = mb_get(f"recording/{rec['id']}", inc="tags+genres+releases+release-groups")
    out["recording"] = _tags(full)
    rgs = [rl.get("release-group", {}).get("id") for rl in full.get("releases", []) if rl.get("release-group")]
    if rgs:
        out["release_group"] = _tags(mb_get(f"release-group/{rgs[0]}", inc="tags+genres"))
    aid = (rec.get("artist-credit") or [{}])[0].get("artist", {}).get("id")
    if aid:
        if aid not in _artist_cache:
            _artist_cache[aid] = _tags(mb_get(f"artist/{aid}", inc="tags+genres"))
        out["artist"] = _artist_cache[aid]
    return out


rows = []
out_path = sys.argv[1]
for main, sub, songs in MICRO:
    for artist, title in songs:
        rec = Recognition(engine="link", title=title, artists=[artist])
        dz = enrich.deezer(rec)
        apple = (itunes_song(Track(title=title, artists=[artist])) or {}).get("genre")
        time.sleep(3.0)                       # iTunes ~20/min
        rec.genres = [apple] if apple else []
        tr, extra = enrich._enrich_online(rec)
        try:
            mbt = musicbrainz(artist, title)
        except Exception as e:  # noqa: BLE001
            mbt = {"error": str(e)}
        row = dict(main=main, sub=sub, artist=artist, title=title, apple=apple,
                   deezer_found=bool(dz.get("id")), preview=dz.get("preview"),
                   deezer_genres=enrich.deezer_genres(dz) if dz.get("id") else [],
                   lastfm_tags=tr.tags, m1=[tr.genre, tr.subgenre, tr.niche], mb=mbt)
        rows.append(row)
        ok = "✓" if tr.subgenre == sub else "✗"
        print(f"{ok} {sub:24} {artist} – {title}: {tr.genre}/{tr.subgenre}  mb={sum(len(v) for v in mbt.values() if isinstance(v, dict))}",
              flush=True)
        json.dump(rows, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

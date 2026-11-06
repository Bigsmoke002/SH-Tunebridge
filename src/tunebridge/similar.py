"""Ähnliche Songs aus zwei Quellen.

1. Last.fm (track.getSimilar, sonst artist.getSimilar) – braucht einen Last.fm-Key.
2. Deezer (ohne Key): Künstler-Radio + Top-Song ähnlicher Künstler. Springt ein, wenn Last.fm zu wenig liefert.
   Seit etwa Oktober 2026 kommen Last.fms Ähnlichkeitsabfragen oft komplett leer zurück (auch bei sehr
   bekannten Songs) – ohne Ersatzquelle stand dann nur noch „Keine ähnlichen Songs gefunden“ da.

Leere Ergebnisse werden NICHT zwischengespeichert (sonst bliebe eine kurze Störung 7 Tage lang hängen).
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from . import config, store
from .models import Track

TTL = 7 * 86400
PER_ARTIST = 2          # Vielfalt: höchstens 2 Songs pro Künstler


def _key(t: Track) -> tuple[str, str]:
    return ((t.artists[0] if t.artists else "").lower().strip(), t.title.lower().strip())


def deezer_similar(track: Track, limit: int = 15) -> list[tuple[Track, float]]:
    from .enrich import _dz, deezer
    from .recognize.engines import Recognition

    ck = f"{track.artist.lower()}|{track.title.lower()}|{limit}"
    if hit := store.cache_get("deezer_similar", ck, max_age=TTL):
        return [(Track(**t), m) for t, m in hit]
    seed = deezer(Recognition("similar", track.title, list(track.artists), isrc=track.isrc))
    aid = ((seed or {}).get("artist") or {}).get("id")
    if not aid:
        return []
    seed_key = _key(track)
    out: list[tuple[Track, float]] = []
    seen, per = {seed_key}, {}

    def add(t: Track, m: float) -> None:
        k = _key(t)
        if k in seen or per.get(k[0], 0) >= PER_ARTIST or len(out) >= limit:
            return
        seen.add(k)
        per[k[0]] = per.get(k[0], 0) + 1
        out.append((t, m))

    def dz_track(h: dict) -> Track:
        return Track(title=h["title"], artists=[h["artist"]["name"]], duration_ms=(h.get("duration") or 0) * 1000 or None,
                     isrc=h.get("isrc"), ids={"deezer": str(h["id"])})

    # 1) Top-Song ähnlicher Künstler (bessere Vielfalt), 2) Künstler-Radio auffüllen
    related = (_dz(f"https://api.deezer.com/artist/{aid}/related", params={"limit": limit}).get("data") or [])[:limit]

    def top(i_a):
        i, a = i_a
        ts = _dz(f"https://api.deezer.com/artist/{a['id']}/top", params={"limit": 1}).get("data") or []
        return (dz_track(ts[0]), round(0.85 - i * 0.03, 3)) if ts else None

    with ThreadPoolExecutor(4) as ex:
        for r in ex.map(top, enumerate(related[:10])):
            if r:
                add(*r)
    if len(out) < limit:
        radio = _dz(f"https://api.deezer.com/artist/{aid}/radio", params={"limit": 40}).get("data") or []
        for i, h in enumerate(radio):
            if h.get("artist", {}).get("id") == aid:
                continue                       # nicht nur derselbe Künstler
            add(dz_track(h), round(max(0.3, 0.7 - i * 0.01), 3))
    out.sort(key=lambda x: -x[1])
    if out:
        from dataclasses import asdict
        store.cache_set("deezer_similar", ck, [(asdict(t), m) for t, m in out])
    return out


def find(track: Track, limit: int = 15) -> list[tuple[Track, float]]:
    """Last.fm zuerst (wenn Key da), dann mit Deezer auffüllen."""
    from . import debuglog as dbg
    from .ratelimit import LimitReached

    out: list[tuple[Track, float]] = []
    lf_err = None
    if config.opt("LASTFM_API_KEY"):
        from .genres.sources.lastfm import LastFM
        try:
            out = LastFM().similar(track, limit=limit)
        except LimitReached as e:
            lf_err = e
        except Exception as e:  # noqa: BLE001 – Last.fm-Störung: Deezer übernimmt
            dbg.problem("ähnlich", f"Last.fm fehlgeschlagen: {e}")
    if len(out) < min(limit, 8):
        have = {_key(t) for t, _ in out}
        try:
            for t, m in deezer_similar(track, limit):
                if _key(t) not in have and len(out) < limit:
                    out.append((t, m))
                    have.add(_key(t))
        except LimitReached:
            if not out and lf_err:
                raise lf_err
            if not out:
                raise
    return out

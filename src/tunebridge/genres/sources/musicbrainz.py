"""MusicBrainz: offene Musikdatenbank – Tags/Genres von Aufnahme, Album und Künstler.

Warum: liefert oft das *Mikro-Genre* („neurofunk“, „drift phonk“), wo Last.fm nur grobe Tags hat.
Rechtliches: Die MusicBrainz-Kerndaten (inkl. Tags/Genres) sind CC0 – frei nutzbar. Die API ist kostenlos,
verlangt aber höchstens 1 Anfrage/Sekunde und einen aussagekräftigen User-Agent.
Gesendet werden nur Künstler + Titel. Ergebnisse werden 30 Tage gespeichert -> pro Song höchstens einmal.
"""

from __future__ import annotations

import httpx

from ... import ratelimit, store
from ...matching import normalize
from ...models import Track
from ...versions import main_artist, split_version

API = "https://musicbrainz.org/ws/2"
_TTL = 30 * 86400
_UA = "SH-Tunebridge/0.4 (https://github.com/Bigsmoke002/SH-Tunebridge)"
_http = httpx.Client(timeout=15, headers={"User-Agent": _UA, "Accept": "application/json"},
                     event_hooks=ratelimit.httpx_hooks("musicbrainz", max_wait=4))
# Gewicht je Ebene: die Aufnahme selbst zählt am meisten, der Künstler am wenigsten (Namensvettern, Stilwechsel)
WEIGHTS = {"recording": 100.0, "release_group": 70.0, "artist": 40.0}


def _get(path: str, **params) -> dict:
    r = _http.get(f"{API}/{path}", params={"fmt": "json", **params})
    if r.status_code == 503:
        ratelimit.blocked("musicbrainz", 5, "HTTP 503")
        raise ratelimit.LimitReached("musicbrainz", 5, "MusicBrainz ausgelastet")
    if r.status_code == 404:
        return {}
    r.raise_for_status()
    return r.json()


def _tags(obj: dict) -> dict[str, float]:
    out: dict[str, float] = {}
    for t in (obj.get("tags") or []) + (obj.get("genres") or []):
        if t.get("count", 0) > 0 and t.get("name"):
            k = t["name"].lower()
            out[k] = max(out.get(k, 0), float(t["count"]))
    return out


def _norm(d: dict[str, float], top: float) -> dict[str, float]:
    m = max(d.values(), default=0)
    return {k: round(v / m * top, 1) for k, v in d.items()} if m else {}


def _artist_ok(credit: list, artist: str) -> bool:
    na = normalize(artist)
    for c in credit or []:
        n = normalize((c or {}).get("name", "")) if isinstance(c, dict) else ""
        if n and (n in na or na in n):
            return True
    return False


def lookup(track: Track) -> dict[str, dict[str, float]]:
    """-> {"recording": {...}, "release_group": {...}, "artist": {...}} (rohe Stimmenzahlen) oder {}."""
    title, artists, _ = split_version(track.title, track.artists)
    artist = main_artist(artists[0]) if artists else ""
    if not title or not artist:
        return {}
    key = f"{normalize(artist)}|{normalize(title)}"
    if (hit := store.cache_get("musicbrainz", key, max_age=_TTL)) is not None:
        return hit
    out: dict = {}
    rec = None
    if track.isrc:
        recs = _get(f"isrc/{track.isrc}", inc="artist-credits").get("recordings") or []
        rec = next((r for r in recs if _artist_ok(r.get("artist-credit"), artist)), None)
    if not rec:
        q = f'recording:"{title}" AND artist:"{artist}"'
        recs = _get("recording", query=q, limit=5).get("recordings") or []
        rec = next((r for r in recs if r.get("score", 0) >= 85 and _artist_ok(r.get("artist-credit"), artist)), None)
    if rec:
        full = _get(f"recording/{rec['id']}", inc="tags+genres+releases+release-groups+artist-credits")
        out["recording"] = _tags(full)
        rgs = [rl["release-group"]["id"] for rl in full.get("releases") or [] if rl.get("release-group")]
        if rgs:
            out["release_group"] = _tags(_get(f"release-group/{rgs[0]}", inc="tags+genres"))
        aid = ((full.get("artist-credit") or rec.get("artist-credit") or [{}])[0].get("artist") or {}).get("id")
        if aid:
            akey = f"artist:{aid}"
            a = store.cache_get("musicbrainz", akey, max_age=_TTL)
            if a is None:
                a = _tags(_get(f"artist/{aid}", inc="tags+genres"))
                store.cache_set("musicbrainz", akey, a)
            out["artist"] = a
    store.cache_set("musicbrainz", key, out)
    return out


def tags(track: Track) -> dict[str, float]:
    """Zusammengeführte, auf 0–100 skalierte Tags (Aufnahme > Album > Künstler)."""
    out: dict[str, float] = {}
    for part, d in lookup(track).items():
        for k, v in _norm(d, WEIGHTS.get(part, 40.0)).items():
            out[k] = max(out.get(k, 0), v)
    return out

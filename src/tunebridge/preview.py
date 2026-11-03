"""Hörproben: nur streamen – nie herunterladen, umwandeln oder auf der Platte speichern.

Warum so (Bedingungen der Anbieter, geprüft 2026-11-03):
  * Apple (iTunes-API, „Promo Content“): Hörproben dürfen nur gestreamt werden – „not downloaded, saved,
    cached“, mit Hinweis „provided courtesy of iTunes“ und Link in den Store.
  * Deezer (API-Bedingungen §IV/§V): nur nicht-kommerziell, Inhalte nicht herunterladen.
Deshalb holt die App nur die *aktuelle Adresse* der offiziellen 30-s-Hörprobe (Deezer-Links sind signiert und
laufen ab) und der Player streamt direkt vom Anbieter. Im Arbeitsspeicher liegt nur diese Adresse, kurz.
Apple-Hörproben sind AAC – das kann das Linux-Fenster (Qt aus PyPI) nicht abspielen; dann nimmt die App die
gleiche Hörprobe bei Deezer. Ohne passende Quelle gibt es eben keine Hörprobe (statt sie umzuwandeln).
Keine öffentliche Wiedergabe, keine Weitergabe – deshalb keine GEMA-Pflicht.
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import httpx

from . import config, ratelimit

CACHE = config.DATA / "cache" / "previews"     # nur noch, um alte Dateien zu entfernen
_http = httpx.Client(timeout=20, follow_redirects=True, headers={"User-Agent": "tunebridge/0.1"},
                     event_hooks=ratelimit.httpx_hooks("deezer", max_wait=3))


def _key(url: str | None, isrc: str | None, deezer: str | None, artist: str, title: str) -> str:
    basis = isrc or (f"dz:{deezer}" if deezer else None) or f"{artist.lower()}|{title.lower()}" or url or ""
    return hashlib.sha1(basis.encode()).hexdigest()[:20]


def _fresh_deezer_urls(isrc: str | None, deezer: str | None, artist: str, title: str) -> list[str]:
    """Aktuelle (nicht abgelaufene) Deezer-Vorschau-Links."""
    out = []
    try:
        if deezer:
            d = _http.get(f"https://api.deezer.com/track/{deezer}").json()
            if d.get("preview"):
                out.append(d["preview"])
        if isrc and not out:
            d = _http.get(f"https://api.deezer.com/track/isrc:{isrc}").json()
            if d.get("preview"):
                out.append(d["preview"])
        if not out and artist and title:
            from .enrich import deezer as dz_lookup
            from .recognize.engines import Recognition
            d = dz_lookup(Recognition("preview", title, [artist], isrc=isrc))
            if d.get("preview"):
                out.append(d["preview"])
    except (httpx.HTTPError, ValueError, ratelimit.LimitReached):
        pass
    return out


def _download(url: str) -> bytes | None:
    try:
        r = _http.get(url)
        if r.status_code == 200 and len(r.content) > 10_000:
            return r.content
    except (httpx.HTTPError, ratelimit.LimitReached):
        pass
    return None


_RAM: dict[str, tuple[float, dict]] = {}     # Schlüssel -> (gültig bis, {url, source}) – nur Adressen
_RAM_MAX = 500


def _expires(url: str) -> float:
    """Deezer-Links tragen ihr Ablaufdatum (…hdnea=exp=1793…~…). Andere: 30 min gültig annehmen."""
    import re
    import time
    m = re.search(r"exp=(\d{9,11})", url)
    return float(m.group(1)) - 60 if m else time.time() + 1800


def source_of(url: str) -> str:
    u = url.lower()
    return ("deezer" if "dzcdn" in u or "deezer" in u else "apple" if "apple.com" in u or "mzstatic" in u
            else "spotify" if "scdn.co" in u or "spotify" in u else "andere")


def _prune() -> None:
    """Früher lagen umgewandelte Hörproben auf der Platte – die werden entfernt (nichts mehr speichern)."""
    if CACHE.exists():
        shutil.rmtree(CACHE, ignore_errors=True)


def resolve(url: str | None = None, isrc: str | None = None, deezer: str | None = None,
            artist: str = "", title: str = "", aac: bool = False) -> dict:
    """-> {url, source} einer direkt abspielbaren, offiziellen Hörprobe. aac=False: Player kann kein AAC
    (Linux-Fenster) -> Apple-Links überspringen. Wirft FileNotFoundError, wenn es keine gibt."""
    import time
    key = _key(url, isrc, deezer, artist, title) + (":aac" if aac else "")
    hit = _RAM.get(key)
    if hit and hit[0] > time.time():
        return hit[1]
    stored = url if url and url.startswith("http") else None
    found = None
    if stored and source_of(stored) == "deezer" and _expires(stored) > time.time():
        found = stored
    if not found and stored and source_of(stored) == "apple" and aac:
        found = stored
    if not found:
        fresh = _fresh_deezer_urls(isrc, deezer, artist, title)
        found = fresh[0] if fresh else None
    if not found and stored and source_of(stored) not in ("apple", "deezer"):
        found = stored
    if not found:
        raise FileNotFoundError("Keine abspielbare Hörprobe gefunden")
    out = {"url": found, "source": source_of(found)}
    if len(_RAM) >= _RAM_MAX:
        for k in sorted(_RAM, key=lambda k: _RAM[k][0])[: _RAM_MAX // 5]:
            _RAM.pop(k, None)
    _RAM[key] = (min(_expires(found), time.time() + 1800), out)
    return out

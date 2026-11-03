"""Song-Erkennung über mehrere Dienste parallel.

| Dienst   | Key nötig | Stärke |
|----------|-----------|--------|
| Shazam   | nein      | riesiger Katalog, sehr gut bei Mainstream & bekannten Releases |
| AudD     | ja        | eigener Katalog + liefert Spotify/Apple/Deezer-Links mit |
| ACRCloud | ja        | sehr robuster Fingerprint, auch bei Live-/Umgebungsgeräusch |

SoundHound/Midomi haben keine öffentliche Erkennungs-API – daher hier nicht dabei.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from .. import config
from ..matching import normalize


@dataclass
class Recognition:
    engine: str
    title: str
    artists: list[str]
    album: str | None = None
    isrc: str | None = None
    cover: str | None = None
    preview_url: str | None = None
    links: dict[str, str] = field(default_factory=dict)
    genres: list[str] = field(default_factory=list)
    label: str | None = None
    year: str | None = None
    duration_ms: int | None = None
    skew: float | None = None      # Shazam: Tempo-Abweichung des Treffers (0 = exakt diese Aufnahme)
    speed: float | None = None     # gesetzt, wenn erst eine Tempo-Korrektur den Song gefunden hat
    offset: float | None = None    # Shazam: an welcher Stelle im Song die Aufnahme beginnt (Sekunden)

    @property
    def key(self) -> str:
        return f"{normalize(self.artists[0] if self.artists else '')}|{normalize(self.title)}"

    def same_song(self, other: "Recognition") -> bool:
        if self.isrc and other.isrc and self.isrc.upper() == other.isrc.upper():
            return True
        return self.key == other.key


# ---------------------------------------------------------------- Shazam
class ShazamBusy(RuntimeError):
    """Shazam-Limit erreicht oder keine Antwort – nicht endlos warten."""


SHAZAM_TIMEOUT = 15.0     # Sekunden pro Anfrage, inkl. Wiederholungen


def shazam_paused() -> float:
    """Restliche Shazam-Pause in Sekunden (0 = frei)."""
    from .. import ratelimit
    return ratelimit.paused("shazam")


async def shazam(path: Path) -> Recognition | None:
    """shazamio wiederholt von sich aus bis zu 20× mit wachsender Pause (auch bei 429) – das konnte
    minutenlang hängen. Hier: eigenes Limit vorab (ratelimit.py), höchstens 2 Versuche bei
    Serverfehlern, bei Drosselung sofort Pause + Meldung."""
    from aiohttp_retry import ExponentialRetry
    from shazamio import Shazam
    from shazamio.client import HTTPClient

    from .. import ratelimit

    try:
        await ratelimit.wait_async("shazam", max_wait=8)
    except ratelimit.LimitReached as e:
        raise ShazamBusy(str(e)) from None
    client = HTTPClient(retry_options=ExponentialRetry(attempts=2, start_timeout=0.5, max_timeout=2,
                                                       statuses={500, 502, 503, 504}))
    sh = Shazam(http_client=client)
    try:
        r = await asyncio.wait_for(sh.recognize(str(path)), SHAZAM_TIMEOUT)
    except asyncio.TimeoutError:
        p = ratelimit.blocked("shazam", 45, "keine Antwort")
        raise ShazamBusy(f"Shazam antwortet nicht – Pause {round(p)} s") from None
    except Exception as e:
        if type(e).__name__ == "RateLimited" or "429" in str(e) or "rate limited" in str(e):
            p = ratelimit.blocked("shazam", None, "HTTP 429")
            raise ShazamBusy(f"Shazam-Limit erreicht (zu viele Anfragen) – Pause {round(p)} s") from e
        raise
    finally:
        try:
            await sh.close()
        finally:
            await client.close()
    t = r.get("track")
    if not t:
        return None
    meta = {m.get("title"): m.get("text") for s in t.get("sections", []) for m in s.get("metadata", []) or []}
    preview = next((a.get("uri") for a in (t.get("hub", {}).get("actions") or [])
                    if a.get("type") == "uri" and a.get("uri", "").startswith("http")), None)
    links = {"shazam": t["url"]} if t.get("url") else {}
    for p in t.get("hub", {}).get("providers", []) or []:
        for a in p.get("actions", []) or []:
            if a.get("uri", "").startswith(("spotify:", "https://")):
                links.setdefault(p.get("type", "").lower(), a["uri"])
    return Recognition(
        engine="shazam", title=t["title"], artists=[t.get("subtitle", "")],
        album=meta.get("Album"), isrc=t.get("isrc"), label=meta.get("Label"), year=meta.get("Released"),
        cover=(t.get("images") or {}).get("coverarthq") or (t.get("images") or {}).get("coverart"),
        preview_url=preview, links=links,
        genres=[g for g in (t.get("genres") or {}).values() if g],
        skew=max((abs(float(m.get("timeskew") or 0)) for m in (r.get("matches") or [])[:1]), default=None),
        offset=next((float(m["offset"]) for m in (r.get("matches") or [])[:1] if m.get("offset") is not None), None),
    )


# ---------------------------------------------------------------- AudD
async def audd(path: Path) -> Recognition | None:
    token = config.opt("AUDD_API_TOKEN")
    if not token:
        return None
    from .. import ratelimit
    await ratelimit.wait_async("audd", max_wait=8)
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post("https://api.audd.io/", data={"api_token": token, "return": "apple_music,spotify,deezer"},
                         files={"file": path.open("rb")})
    j = r.json() if r.status_code != 429 else {}
    if r.status_code == 429 or (j.get("error") or {}).get("error_code") in (901, 902):
        p = ratelimit.blocked("audd", ratelimit.retry_after(r.headers), "Limit/Kontingent erreicht")
        raise RuntimeError(f"AudD-Limit erreicht – Pause {round(p)} s")
    res = j.get("result")
    if not res:
        return None
    sp, am, dz = res.get("spotify") or {}, res.get("apple_music") or {}, res.get("deezer") or {}
    return Recognition(
        engine="audd", title=res["title"], artists=[res["artist"]], album=res.get("album"),
        label=res.get("label"), year=(res.get("release_date") or "")[:4] or None,
        isrc=(sp.get("external_ids") or {}).get("isrc") or am.get("isrc"),
        cover=((sp.get("album") or {}).get("images") or [{}])[0].get("url") or (dz.get("album") or {}).get("cover_xl"),
        preview_url=dz.get("preview") or ((am.get("previews") or [{}])[0].get("url")),
        links={k: v for k, v in {"song.link": res.get("song_link"),
                                 "spotify": (sp.get("external_urls") or {}).get("spotify"),
                                 "apple": am.get("url"), "deezer": dz.get("link")}.items() if v},
        genres=am.get("genreNames") or [],
        duration_ms=sp.get("duration_ms"),
    )


# ---------------------------------------------------------------- ACRCloud
async def acrcloud(path: Path) -> Recognition | None:
    host, key, secret = (config.opt(k) for k in ("ACRCLOUD_HOST", "ACRCLOUD_ACCESS_KEY", "ACRCLOUD_ACCESS_SECRET"))
    if not (host and key and secret):
        return None
    ts = str(int(time.time()))
    to_sign = "\n".join(["POST", "/v1/identify", key, "audio", "1", ts])
    sig = base64.b64encode(hmac.new(secret.encode(), to_sign.encode(), hashlib.sha1).digest()).decode()
    data = path.read_bytes()
    from .. import ratelimit
    await ratelimit.wait_async("acrcloud", max_wait=8)
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(f"https://{host}/v1/identify",
                         data={"access_key": key, "sample_bytes": str(len(data)), "timestamp": ts,
                               "signature": sig, "data_type": "audio", "signature_version": "1"},
                         files={"sample": ("sample.wav", data)})
    j = r.json() if r.status_code != 429 else {}
    if r.status_code == 429 or (j.get("status") or {}).get("code") in (3003, 3015):  # Limit / QpS-Limit
        p = ratelimit.blocked("acrcloud", ratelimit.retry_after(r.headers), "Limit/Kontingent erreicht")
        raise RuntimeError(f"ACRCloud-Limit erreicht – Pause {round(p)} s")
    music = (j.get("metadata") or {}).get("music") or []
    if not music:
        return None
    m = music[0]
    ext = m.get("external_metadata") or {}
    links = {}
    if (sp := (ext.get("spotify") or {}).get("track", {}).get("id")):
        links["spotify"] = f"https://open.spotify.com/track/{sp}"
    if (yt := (ext.get("youtube") or {}).get("vid")):
        links["youtube"] = f"https://youtu.be/{yt}"
    if (dz := (ext.get("deezer") or {}).get("track", {}).get("id")):
        links["deezer"] = f"https://www.deezer.com/track/{dz}"
    return Recognition(
        engine="acrcloud", title=m["title"], artists=[a["name"] for a in m.get("artists", [])],
        album=(m.get("album") or {}).get("name"), isrc=(m.get("external_ids") or {}).get("isrc"),
        label=m.get("label"), year=(m.get("release_date") or "")[:4] or None,
        genres=[g["name"] for g in m.get("genres", [])], duration_ms=m.get("duration_ms"), links=links,
    )


ENGINES = {"shazam": shazam, "audd": audd, "acrcloud": acrcloud}


def available() -> list[str]:
    out = ["shazam"]
    if config.opt("AUDD_API_TOKEN"):
        out.append("audd")
    if config.opt("ACRCLOUD_ACCESS_KEY"):
        out.append("acrcloud")
    return out


@dataclass
class Result:
    best: Recognition | None
    agreement: int  # wie viele Dienste das gleiche Ergebnis lieferten
    all: list[Recognition]
    errors: dict[str, str]


async def recognize(path: Path, engines: list[str] | None = None) -> Result:
    names = engines or available()
    outs = await asyncio.gather(*(ENGINES[n](path) for n in names), return_exceptions=True)
    hits, errors = [], {}
    for n, o in zip(names, outs):
        if isinstance(o, Exception):
            errors[n] = f"{type(o).__name__}: {o}"
        elif o:
            hits.append(o)
    if not hits:
        return Result(None, 0, [], errors)
    # Abstimmung: gleiches Ergebnis (ISRC oder Künstler|Titel) mehrerer Dienste gewinnt
    groups: list[list[Recognition]] = []
    for h in hits:
        for g in groups:
            if any(h.same_song(x) for x in g):
                g.append(h)
                break
        else:
            groups.append([h])
    best_group = max(groups, key=len)
    best = _merge(best_group)
    return Result(best, len(best_group), hits, errors)


def _merge(rs: list[Recognition]) -> Recognition:
    """Felder mehrerer Dienste zusammenführen (Shazam zuerst, dann die anderen)."""
    base = Recognition(**{**rs[0].__dict__, "links": dict(rs[0].links), "genres": list(rs[0].genres)})
    for r in rs[1:]:
        for f in ("album", "isrc", "cover", "preview_url", "label", "year", "duration_ms"):
            if not getattr(base, f) and getattr(r, f):
                setattr(base, f, getattr(r, f))
        for k, v in r.links.items():
            base.links.setdefault(k, v)
        base.genres += [g for g in r.genres if g not in base.genres]
    base.engine = "+".join(r.engine for r in rs)
    return base

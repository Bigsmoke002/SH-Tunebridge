"""„Mehr vom Künstler“: weitere Songs eines Künstlers – getrennt nach Solo und Zusammenarbeiten.

Quelle: Deezers öffentliche API (ohne Login). Der Künstler kommt immer aus dem schon geprüften Song
(Künstler + Titel stimmen) – so landet man nicht bei einem Namensvetter. Ergebnisse bleiben nur im
Arbeitsspeicher (1 Stunde); Hörproben werden beim Abspielen frisch bei Deezer geholt, nichts wird gespeichert.
"""

from __future__ import annotations

import re
import time

import httpx

_RAM: dict[str, tuple[float, object]] = {}
TTL = 3600
_http = httpx.Client(timeout=15, headers={"User-Agent": "tunebridge/0.1"})
_FEAT = re.compile(r"[\(\[]?\s*\b(?:feat\.?|ft\.?|featuring|with|w/)\s+([^\)\]]+)[\)\]]?", re.I)


def _get(url: str, **params) -> dict:
    from .enrich import _dz
    return _dz(url, params=params or None)


def _cached(key: str, fn):
    hit = _RAM.get(key)
    if hit and time.time() - hit[0] < TTL:
        return hit[1]
    val = fn()
    _RAM[key] = (time.time(), val)
    if len(_RAM) > 300:
        for k, _ in sorted(_RAM.items(), key=lambda kv: kv[1][0])[:100]:
            _RAM.pop(k, None)
    return val


def contributors(dz_track: str) -> list[dict]:
    """Alle Künstler eines (schon geprüften) Deezer-Songs."""
    def load():
        d = _get(f"https://api.deezer.com/track/{int(dz_track)}")
        if "error" in d:
            return []
        out, seen = [], set()
        for c in [d.get("artist") or {}] + (d.get("contributors") or []):
            if c.get("id") and c["id"] not in seen:
                seen.add(c["id"])
                out.append({"id": c["id"], "name": c.get("name") or "", "picture": c.get("picture_medium")})
        return out
    return _cached(f"c:{dz_track}", load)


def _item(t: dict, aid: int) -> dict:
    names = [c.get("name") for c in (t.get("contributors") or []) if c.get("name")] or [(t.get("artist") or {}).get("name", "")]
    others = [c.get("name") for c in (t.get("contributors") or []) if c.get("id") != aid and c.get("name")]
    m = _FEAT.search(t.get("title") or "")
    if m:
        for n in re.split(r"\s*(?:,|&| and | x )\s*", m.group(1)):
            if n.strip() and n.strip().lower() not in {o.lower() for o in others}:
                others.append(n.strip())
    if (t.get("artist") or {}).get("id") not in (None, aid):
        main = t["artist"].get("name")
        if main and main not in others:
            others.insert(0, main)
    alb = t.get("album") or {}
    return {"title": t.get("title_short") or t.get("title") or "", "version": t.get("title_version") or "",
            "artists": names, "with": others, "album": alb.get("title"), "cover": alb.get("cover_medium"),
            "duration_ms": (t.get("duration") or 0) * 1000, "rank": t.get("rank") or 0,
            "ids": {"deezer": str(t.get("id"))}, "preview_url": "deezer:" if t.get("preview") else None}


def tracks(aid: int, limit: int = 60) -> dict:
    """-> {artist, solo: [...], collab: [...]} – beliebteste zuerst."""
    def load():
        a = _get(f"https://api.deezer.com/artist/{int(aid)}")
        if "error" in a:
            raise LookupError("Künstler bei Deezer nicht gefunden")
        top = _get(f"https://api.deezer.com/artist/{int(aid)}/top", limit=limit).get("data") or []
        solo, collab, seen = [], [], set()
        for t in top:
            it = _item(t, int(aid))
            key = (it["title"].lower(), tuple(sorted(x.lower() for x in it["with"])))
            if key in seen:
                continue
            seen.add(key)
            (collab if it["with"] else solo).append(it)
        return {"artist": {"id": a.get("id"), "name": a.get("name"), "picture": a.get("picture_medium"),
                           "fans": a.get("nb_fan"), "albums": a.get("nb_album"), "link": a.get("link")},
                "solo": solo, "collab": collab}
    return _cached(f"a:{aid}:{limit}", load)

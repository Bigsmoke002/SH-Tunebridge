"""„Entdecken“: im Deezer-Katalog stöbern – Suche (Songs, Künstler, Alben), Künstler- und Albumseiten, Charts, Genres.

Quelle: Deezers öffentliche API (ohne Login, ohne Key). Gesendet wird nur, was du suchst bzw. anklickst (Suchbegriff
oder Deezer-Kennung); Deezer sieht dabei deine IP-Adresse. Ergebnisse bleiben nur im Arbeitsspeicher (1 Stunde),
Suchbegriffe werden nirgends gespeichert. Hörproben holt der Player beim Abspielen frisch über die Deezer-ID.
"""
from __future__ import annotations

import re
import time

from .artists import _item as _artist_item

TTL = 3600
_RAM: dict[str, tuple[float, object]] = {}
KINDS = ("track", "artist", "album")
NO_MUSIC = {457}                              # Hörbücher
RECORD = {"album": "Album", "single": "Single", "ep": "EP", "compile": "Zusammenstellung"}
_SPACE = re.compile(r"\s+")


def _get(url: str, **params) -> dict:
    from .enrich import _dz
    return _dz(url, params=params or None)


def _cached(key: str, fn):
    hit = _RAM.get(key)
    if hit and time.time() - hit[0] < TTL:
        return hit[1]
    val = fn()
    _RAM[key] = (time.time(), val)
    if len(_RAM) > 400:
        for k, _ in sorted(_RAM.items(), key=lambda kv: kv[1][0])[:150]:
            _RAM.pop(k, None)
    return val


def _id(x) -> int:
    s = "" if x is None else str(x).strip()
    if not s.isdigit() or len(s) > 15:
        raise ValueError("Ungültige Kennung")
    return int(s)


# ------------------------------------------------------------------ Einträge
def track(t: dict, album: dict | None = None) -> dict | None:
    """Deezer-Song -> Eintrag wie bei „Remixe & Versionen“ (title, artists, album, cover, ids, preview_url …)."""
    if not t.get("id") or not (t.get("title") or t.get("title_short")):
        return None
    alb = t.get("album") or album or {}
    art = t.get("artist") or {}
    people = [c for c in (t.get("contributors") or []) if c.get("name")] or ([art] if art.get("name") else [])
    names = [c["name"] for c in people]
    return {"title": t.get("title") or t.get("title_short") or "",      # mit Versionszusatz („… (VIP Mix)“)
            "artists": names, "artist_ids": [c.get("id") for c in people], "artist_id": art.get("id"), "album": alb.get("title"), "album_id": alb.get("id"),
            "cover": alb.get("cover_medium") or (album or {}).get("cover_medium"),
            "duration_ms": (t.get("duration") or 0) * 1000 or None, "rank": t.get("rank") or 0,
            "explicit": bool(t.get("explicit_lyrics")), "isrc": t.get("isrc"),
            "ids": {"deezer": str(t["id"])}, "preview_url": f"deezer:{t['id']}" if t.get("preview") else None}


def artist(a: dict) -> dict | None:
    if not a.get("id") or not a.get("name"):
        return None
    return {"id": a["id"], "name": a["name"], "picture": a.get("picture_medium"), "fans": a.get("nb_fan"),
            "albums": a.get("nb_album")}


def album(a: dict) -> dict | None:
    if not a.get("id") or not a.get("title"):
        return None
    art = a.get("artist") or {}
    return {"id": a["id"], "title": a["title"], "artist": art.get("name"), "artist_id": art.get("id"),
            "cover": a.get("cover_medium"), "year": (a.get("release_date") or "")[:4] or None,
            "type": RECORD.get(a.get("record_type") or "", ""), "tracks": a.get("nb_tracks"),
            "explicit": bool(a.get("explicit_lyrics"))}


def _clean(xs, fn) -> list:
    return [y for y in (fn(x) for x in xs or []) if y]


# ------------------------------------------------------------------ Abfragen
def search(q: str, kind: str = "track", limit: int = 40) -> dict:
    q = _SPACE.sub(" ", str(q or "")).strip()[:100]
    if not q:
        return {"q": "", "kind": kind, "items": []}
    if kind not in KINDS:
        raise ValueError("Unbekannte Suchart")
    limit = max(1, min(int(limit), 50))
    fn = {"track": track, "artist": artist, "album": album}[kind]
    data = _cached(f"s:{kind}:{q.lower()}:{limit}",
                   lambda: _get(f"https://api.deezer.com/search/{kind}", q=q, limit=limit).get("data") or [])
    return {"q": q, "kind": kind, "items": _clean(data, fn)}


def search_all(q: str) -> dict:
    """Kurzübersicht für die Suchleiste: die besten Songs, Künstler und Alben auf einmal."""
    return {"q": _SPACE.sub(" ", str(q or "")).strip()[:100],
            "tracks": search(q, "track", 20)["items"], "artists": search(q, "artist", 8)["items"],
            "albums": search(q, "album", 10)["items"]}


def artist_page(aid) -> dict:
    aid = _id(aid)

    def load():
        a = _get(f"https://api.deezer.com/artist/{aid}")
        if "error" in a or not a.get("id"):
            raise LookupError("Künstler bei Deezer nicht gefunden")
        top = _get(f"https://api.deezer.com/artist/{aid}/top", limit=50).get("data") or []
        albums = _get(f"https://api.deezer.com/artist/{aid}/albums", limit=100).get("data") or []
        rel = _get(f"https://api.deezer.com/artist/{aid}/related", limit=20).get("data") or []
        seen, tops = set(), []
        for t in top:
            it = track(t)
            if not it:
                continue
            k = (it["title"].lower(), tuple(a.lower() for a in it["artists"]))
            if k in seen:
                continue
            seen.add(k)
            it["with"] = _artist_item(t, aid)["with"]
            tops.append(it)
        alb = []
        for x in albums:
            if (it := album({**x, "artist": x.get("artist") or {"id": aid, "name": a.get("name")}})):
                alb.append(it)
        alb.sort(key=lambda x: x.get("year") or "", reverse=True)
        return {"artist": {**(artist(a) or {}), "picture_big": a.get("picture_xl") or a.get("picture_big"),
                           "link": a.get("link")},
                "top": tops, "albums": [x for x in alb if x["type"] in ("Album", "Zusammenstellung")],
                "singles": [x for x in alb if x["type"] in ("Single", "EP", "")],
                "related": _clean(rel, artist)}
    return _cached(f"a:{aid}", load)


def album_page(alid) -> dict:
    alid = _id(alid)

    def load():
        a = _get(f"https://api.deezer.com/album/{alid}")
        if "error" in a or not a.get("id"):
            raise LookupError("Album bei Deezer nicht gefunden")
        base = album(a) or {}
        tr = _clean((a.get("tracks") or {}).get("data"), lambda t: track(t, album=a))
        return {"album": {**base, "cover_big": a.get("cover_xl") or a.get("cover_big"), "label": a.get("label"),
                          "date": a.get("release_date"), "duration_ms": (a.get("duration") or 0) * 1000 or None,
                          "genres": [g.get("name") for g in ((a.get("genres") or {}).get("data") or []) if g.get("name")],
                          "artists": [c.get("name") for c in (a.get("contributors") or []) if c.get("name")]
                          or ([base["artist"]] if base.get("artist") else []), "link": a.get("link")},
                "tracks": tr}
    return _cached(f"al:{alid}", load)


def genres() -> list[dict]:
    def load():
        data = _get("https://api.deezer.com/genre").get("data") or []
        return [{"id": g["id"], "name": g.get("name") or "", "picture": g.get("picture_medium")}
                for g in data if isinstance(g.get("id"), int) and g["id"] not in NO_MUSIC]
    return _cached("genres", load)


def charts(genre=0) -> dict:
    gid = _id(genre if genre not in (None, "") else 0)

    def load():
        part = lambda what, n: _get(f"https://api.deezer.com/chart/{gid}/{what}", limit=n)  # noqa: E731
        t = part("tracks", 50)
        if "error" in t:
            raise LookupError("Charts bei Deezer nicht gefunden")
        return {"genre": gid, "tracks": _clean(t.get("data"), track),
                "artists": _clean(part("artists", 20).get("data"), artist),
                "albums": _clean(part("albums", 20).get("data"), album)}
    return _cached(f"c:{gid}", load)

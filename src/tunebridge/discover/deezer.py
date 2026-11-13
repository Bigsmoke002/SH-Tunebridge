"""Entdecken-Quelle Deezer: öffentliche API ohne Login und ohne Key. Liefert Hörproben, Charts nach Genre und
ähnliche Künstler. Gesendet wird nur der Suchbegriff bzw. die Deezer-Kennung; Deezer sieht deine IP-Adresse."""
from __future__ import annotations

from . import _common as c

SRC, P = "deezer", "dz"
NO_MUSIC = {457}                              # Hörbücher
RECORD = {"album": "Album", "single": "Single", "ep": "EP", "compile": "Zusammenstellung"}


def _get(url: str, **params) -> dict:
    from ..enrich import _dz
    return _dz(url, params=params or None)


def _num(x) -> str:
    s = "" if x is None else str(x).strip()
    if not s.isdigit() or len(s) > 15:
        raise ValueError("Ungültige Kennung")
    return s


def ref(x) -> str | None:
    return f"{P}:{x}" if x not in (None, "") else None


def track(t: dict, alb: dict | None = None, aid=None) -> dict | None:
    if not t.get("id"):
        return None
    a = t.get("album") or alb or {}
    art = t.get("artist") or {}
    people = [p for p in (t.get("contributors") or []) if p.get("name")] or ([art] if art.get("name") else [])
    return c.track(SRC, title=t.get("title") or t.get("title_short") or "", artists=[p["name"] for p in people],
                   artist_ids=[ref(p.get("id")) for p in people], album=a.get("title"), album_id=ref(a.get("id")),
                   cover=a.get("cover_medium") or (alb or {}).get("cover_medium"), duration_ms=(t.get("duration") or 0) * 1000,
                   isrc=t.get("isrc"), explicit=t.get("explicit_lyrics"), ids={"deezer": t["id"]},
                   preview_url=f"deezer:{t['id']}" if t.get("preview") else None, rank=t.get("rank") or 0,
                   link=t.get("link"),
                   with_=[p["name"] for p in people if aid is not None and str(p.get("id")) != str(aid)])


def artist(a: dict) -> dict | None:
    return c.artist(SRC, ref(a.get("id")), a.get("name"), picture=a.get("picture_medium"), fans=a.get("nb_fan"),
                    albums=a.get("nb_album"), link=a.get("link"))


def album(a: dict, owner: dict | None = None) -> dict | None:
    art = a.get("artist") or owner or {}
    return c.album(SRC, ref(a.get("id")), a.get("title"), artist_name=art.get("name"), artist_id=ref(art.get("id")),
                   cover=a.get("cover_medium"), year_=c.year(a.get("release_date")),
                   type_=RECORD.get(a.get("record_type") or "", ""), tracks=a.get("nb_tracks"),
                   explicit=a.get("explicit_lyrics"), link=a.get("link"))


def _clean(xs, fn) -> list:
    return [y for y in (fn(x) for x in xs or []) if y]


def search(q: str, kind: str, limit: int = 40) -> list:
    fn = {"track": track, "artist": artist, "album": album}[kind]
    data = c.cached(f"dz:s:{kind}:{q.lower()}:{limit}",
                    lambda: _get(f"https://api.deezer.com/search/{kind}", q=q, limit=limit).get("data") or [])
    return _clean(data, fn)


def search_all(q: str) -> dict:
    return {"tracks": search(q, "track", 20), "artists": search(q, "artist", 8), "albums": search(q, "album", 10)}


def find_artist(name: str) -> str | None:
    want = c.key(name)
    hits = [a for a in search(name, "artist", 10) if c.key(a["name"]) == want]
    return hits[0]["id"].split(":", 1)[1] if hits else None        # Deezer sortiert nach Bekanntheit


def artist_page(aid: str) -> dict:
    aid = _num(aid)

    def load():
        a = _get(f"https://api.deezer.com/artist/{aid}")
        if "error" in a or not a.get("id"):
            raise LookupError("Künstler bei Deezer nicht gefunden")
        top = _get(f"https://api.deezer.com/artist/{aid}/top", limit=50).get("data") or []
        albums = _get(f"https://api.deezer.com/artist/{aid}/albums", limit=100).get("data") or []
        rel = _get(f"https://api.deezer.com/artist/{aid}/related", limit=20).get("data") or []
        me = {"id": a["id"], "name": a.get("name")}
        return {"artist": {**(artist(a) or {}), "picture_big": a.get("picture_xl") or a.get("picture_big")},
                "top": _clean(top, lambda t: track(t, aid=aid)),
                "albums": _clean(albums, lambda x: album(x, me)), "related": _clean(rel, artist)}
    return c.cached(f"dz:a:{aid}", load)


def album_page(alid: str) -> dict:
    alid = _num(alid)

    def load():
        a = _get(f"https://api.deezer.com/album/{alid}")
        if "error" in a or not a.get("id"):
            raise LookupError("Album bei Deezer nicht gefunden")
        base = album(a) or {}
        return {"album": {**base, "cover_big": a.get("cover_xl") or a.get("cover_big"), "label": a.get("label"),
                          "date": a.get("release_date"), "duration_ms": (a.get("duration") or 0) * 1000 or None,
                          "genres": [g.get("name") for g in ((a.get("genres") or {}).get("data") or []) if g.get("name")],
                          "artists": [p.get("name") for p in (a.get("contributors") or []) if p.get("name")]
                          or ([base["artist"]] if base.get("artist") else [])},
                "tracks": _clean((a.get("tracks") or {}).get("data"), lambda t: track(t, alb=a))}
    return c.cached(f"dz:al:{alid}", load)


def genres() -> list[dict]:
    def load():
        data = _get("https://api.deezer.com/genre").get("data") or []
        return [{"id": str(g["id"]), "name": g.get("name") or "", "picture": g.get("picture_medium")}
                for g in data if isinstance(g.get("id"), int) and g["id"] not in NO_MUSIC]
    return c.cached("dz:genres", load)


def charts(genre: str) -> dict:
    gid = _num(genre or "0")

    def load():
        part = lambda what, n: _get(f"https://api.deezer.com/chart/{gid}/{what}", limit=n)  # noqa: E731
        t = part("tracks", 50)
        if "error" in t:
            raise LookupError("Charts bei Deezer nicht gefunden")
        return {"tracks": _clean(t.get("data"), track), "artists": _clean(part("artists", 20).get("data"), artist),
                "albums": _clean(part("albums", 20).get("data"), album)}
    return c.cached(f"dz:c:{gid}", load)

"""Entdecken-Quelle Apple: freie iTunes-Suche (ohne Login, ohne Key, Ländershop DE) und Apples öffentliche
Charts-Feeds. Liefert eigene 30-s-Hörproben (AAC). Gesendet wird nur der Suchbegriff bzw. die Apple-Kennung;
Apple sieht deine IP-Adresse. Apple erlaubt rund 20 Suchen pro Minute – darum eine Suche statt drei."""
from __future__ import annotations

import re

import httpx

from .. import ratelimit
from . import _common as c

SRC, P = "apple", "it"
COUNTRY = "DE"
_http = httpx.Client(timeout=12, headers={"User-Agent": "SH-Tunebridge"}, follow_redirects=True,
                     event_hooks=ratelimit.httpx_hooks("itunes", max_wait=4))
_rss = httpx.Client(timeout=12, headers={"User-Agent": "SH-Tunebridge"}, follow_redirects=True)
_KIND = re.compile(r"\s+-\s+(Single|EP)$")


def _num(x) -> str:
    s = "" if x is None else str(x).strip()
    if not s.isdigit() or len(s) > 15:
        raise ValueError("Ungültige Kennung")
    return s


def ref(x) -> str | None:
    return f"{P}:{x}" if x not in (None, "") else None


def _get(path: str, **params) -> list[dict]:
    r = _http.get(f"https://itunes.apple.com/{path}", params={"country": COUNTRY, **params})
    if r.status_code in (403, 429):
        ratelimit.blocked("itunes", None, f"HTTP {r.status_code}")
        raise ratelimit.LimitReached("itunes", 60, "Apple-Limit erreicht")
    r.raise_for_status()
    return r.json().get("results") or []


def _art(u: str | None, size: int = 250) -> str | None:
    return re.sub(r"/\d+x\d+bb\.", f"/{size}x{size}bb.", u) if u else None


def _album_title(name: str) -> tuple[str, str]:
    m = _KIND.search(name or "")
    return (name[: m.start()], m.group(1)) if m else (name or "", "Album")


def track(r: dict) -> dict | None:
    if r.get("kind") not in (None, "song") or not r.get("trackId"):
        return None
    alb, _ = _album_title(r.get("collectionName") or "")
    return c.track(SRC, title=r.get("trackName"), artists=[r.get("artistName")], artist_ids=[ref(r.get("artistId"))],
                   album=alb or None, album_id=ref(r.get("collectionId")), cover=_art(r.get("artworkUrl100")),
                   duration_ms=r.get("trackTimeMillis"), explicit=r.get("trackExplicitness") == "explicit",
                   ids={"apple": r["trackId"]}, preview_url=r.get("previewUrl"), link=(r.get("trackViewUrl") or "").split("&uo=")[0])


def artist(r: dict) -> dict | None:
    return c.artist(SRC, ref(r.get("artistId")), r.get("artistName"), note=r.get("primaryGenreName"),
                    link=(r.get("artistLinkUrl") or r.get("artistViewUrl") or "").split("?uo=")[0] or None)


def album(r: dict) -> dict | None:
    title, kind = _album_title(r.get("collectionName") or "")
    return c.album(SRC, ref(r.get("collectionId")), title, artist_name=r.get("artistName"), artist_id=ref(r.get("artistId")),
                   cover=_art(r.get("artworkUrl100")), year_=c.year(r.get("releaseDate")),
                   type_="Zusammenstellung" if r.get("collectionType") == "Compilation" else kind,
                   tracks=r.get("trackCount"), explicit=r.get("collectionExplicitness") == "explicit",
                   link=(r.get("collectionViewUrl") or "").split("?uo=")[0] or None)


def _uniq(items: list, n: int) -> list:
    seen, out = set(), []
    for x in items:
        if x and x["id"] not in seen:
            seen.add(x["id"])
            out.append(x)
    return out[:n]


def _songs(q: str) -> list[dict]:
    return c.cached(f"it:s:{q.lower()}", lambda: _get("search", term=q, media="music", entity="song", limit=50))


def search(q: str, kind: str, limit: int = 40) -> list:
    if kind == "track":
        return [x for x in map(track, _songs(q)) if x][:limit]
    ent = {"artist": "musicArtist", "album": "album"}[kind]
    rows = c.cached(f"it:s:{kind}:{q.lower()}", lambda: _get("search", term=q, media="music", entity=ent, limit=min(limit, 25)))
    return [x for x in map(artist if kind == "artist" else album, rows) if x]


def search_all(q: str) -> dict:
    """Eine einzige Song-Suche – Künstler und Alben ergeben sich aus den Treffern (schont Apples Limit)."""
    rows = _songs(q)
    return {"tracks": [x for x in map(track, rows) if x][:20], "artists": _uniq([artist(r) for r in rows], 6),
            "albums": _uniq([album(r) for r in rows], 10)}


def find_artist(name: str) -> str | None:
    want = c.key(name)
    rows = c.cached(f"it:fa:{want}", lambda: _get("search", term=name, media="music", entity="musicArtist", limit=10))
    hits = {str(r.get("artistId")) for r in rows if c.key(r.get("artistName")) == want and r.get("artistId")}
    return hits.pop() if len(hits) == 1 else None                  # Namensvettern: lieber nichts als den falschen


def artist_page(aid: str) -> dict:
    aid = _num(aid)

    def load():
        rows = _get("lookup", id=aid, entity="album", limit=200)
        head = next((r for r in rows if r.get("wrapperType") == "artist"), None)
        if not head:
            raise LookupError("Künstler bei Apple nicht gefunden")
        songs = _get("lookup", id=aid, entity="song", limit=50)
        return {"artist": artist(head) or {}, "top": [x for x in map(track, songs) if x],
                "albums": [x for x in (album(r) for r in rows if r.get("wrapperType") == "collection") if x], "related": []}
    return c.cached(f"it:a:{aid}", load)


def album_page(alid: str) -> dict:
    alid = _num(alid)

    def load():
        rows = _get("lookup", id=alid, entity="song", limit=200)
        head = next((r for r in rows if r.get("wrapperType") == "collection"), None)
        if not head:
            raise LookupError("Album bei Apple nicht gefunden")
        base = album(head) or {}
        tracks = sorted((r for r in rows if r.get("wrapperType") == "track"), key=lambda r: (r.get("discNumber") or 1, r.get("trackNumber") or 0))
        return {"album": {**base, "cover_big": _art(head.get("artworkUrl100"), 600), "label": None,
                          "date": (head.get("releaseDate") or "")[:10] or None, "duration_ms": sum(r.get("trackTimeMillis") or 0 for r in tracks) or None,
                          "genres": [head["primaryGenreName"]] if head.get("primaryGenreName") else [],
                          "artists": [base["artist"]] if base.get("artist") else [], "copyright": head.get("copyright")},
                "tracks": [x for x in map(track, tracks) if x]}
    return c.cached(f"it:al:{alid}", load)


def _feed(what: str, n: int) -> list[dict]:
    r = _rss.get(f"https://rss.marketingtools.apple.com/api/v2/{COUNTRY.lower()}/music/most-played/{n}/{what}.json")
    r.raise_for_status()
    return (r.json().get("feed") or {}).get("results") or []


def charts(genre: str = "") -> dict:
    """Apples meistgespielte Songs und Alben in Deutschland (öffentlicher Feed); Hörproben per Sammelabfrage."""
    def load():
        songs, albums = _feed("songs", 50), _feed("albums", 25)
        ids = [s["id"] for s in songs if str(s.get("id") or "").isdigit()]
        full = {str(r.get("trackId")): r for r in (_get("lookup", id=",".join(ids)) if ids else [])}
        tracks = []
        for s in songs:
            r = full.get(str(s.get("id")))
            tracks.append(track(r) if r else c.track(
                SRC, title=s.get("name"), artists=[s.get("artistName")], artist_ids=[ref(s.get("artistId"))],
                cover=_art(s.get("artworkUrl100")), ids={"apple": s.get("id")}, link=s.get("url")))
        tracks = [t for t in tracks if t]
        return {"tracks": tracks,
                "artists": _uniq([c.artist(SRC, ref(s.get("artistId")), s.get("artistName"), link=s.get("artistUrl"))
                                  for s in songs if s.get("artistId")], 20),
                "albums": [x for x in (c.album(SRC, ref(a.get("id")), a.get("name"), artist_name=a.get("artistName"),
                                               artist_id=ref(a.get("artistId")), cover=_art(a.get("artworkUrl100")),
                                               year_=c.year(a.get("releaseDate")), type_="Album", link=a.get("url"))
                                       for a in albums) if x]}
    return c.cached("it:c", load)

"""Entdecken-Quelle Last.fm – nur mit deinem eigenen API-Key. Stärke: Hörer-Daten, ähnliche Künstler und Stöbern
nach Genre-Tags bis ins Mikro-Genre („liquid funk“). Gesendet wird nur der Suchbegriff, Künstler-/Albumname bzw.
Tag – mit deinem Key; Last.fm sieht deine IP-Adresse."""
from __future__ import annotations

from . import _common as c

SRC, P = "lastfm", "lf"
_PLACEHOLDER = "2a96cbd8b46e442fc41c2b86b821562f"
COUNTRY = "germany"


def _call(method: str, **params) -> dict:
    from ..genres.sources.lastfm import LastFM
    d = LastFM()._call(method, **params)
    if isinstance(d, dict) and d.get("error") == 6:
        raise LookupError(d.get("message") or "Bei Last.fm nicht gefunden")
    if isinstance(d, dict) and d.get("error"):
        raise RuntimeError(f"Last.fm: {d.get('message') or d['error']}")
    return d


def _list(x) -> list:
    return x if isinstance(x, list) else [x] if isinstance(x, dict) else []


def _img(images, size: str = "extralarge") -> str | None:
    by = {i.get("size"): i.get("#text") for i in _list(images) if isinstance(i, dict)}
    u = by.get(size) or by.get("large") or by.get("extralarge")
    return u if u and _PLACEHOLDER not in u else None


def _text(x, n: int = 300) -> str:
    s = str(x or "").replace("\t", " ").replace("\n", " ").strip()
    if not s or len(s) > n:
        raise ValueError("Ungültige Angabe")
    return s


def ref(name: str | None) -> str | None:
    return f"{P}:{name}" if name else None


def album_ref(artist: str | None, title: str | None) -> str | None:
    return f"{P}:{artist}\t{title}" if artist and title else None


def _artist_name(a) -> str:
    return a.get("name") or a.get("#text") or "" if isinstance(a, dict) else str(a or "")


def track(t: dict) -> dict | None:
    name = _artist_name(t.get("artist"))
    return c.track(SRC, title=t.get("name"), artists=[name], artist_ids=[ref(name)], cover=_img(t.get("image")),
                   duration_ms=int(t.get("duration") or 0) * 1000,
                   ids={"musicbrainz": t.get("mbid")} if t.get("mbid") else {}, link=t.get("url"))


def artist(a: dict) -> dict | None:
    return c.artist(SRC, ref(a.get("name")), a.get("name"), fans=int(a.get("listeners") or 0) or None, link=a.get("url"),
                    note="Hörer bei Last.fm" if a.get("listeners") else None)


def album(a: dict) -> dict | None:
    name = _artist_name(a.get("artist"))
    if not a.get("name") or a.get("name") == "(null)":
        return None
    return c.album(SRC, album_ref(name, a.get("name")), a.get("name"), artist_name=name, artist_id=ref(name),
                   cover=_img(a.get("image")), link=a.get("url"))


def search(q: str, kind: str, limit: int = 30) -> list:
    method, outer, inner, fn = {"track": ("track.search", "trackmatches", "track", track),
                                "artist": ("artist.search", "artistmatches", "artist", artist),
                                "album": ("album.search", "albummatches", "album", album)}[kind]
    rows = c.cached(f"lf:s:{kind}:{q.lower()}:{limit}",
                    lambda: _list(((_call(method, **{kind: q, "limit": limit}).get("results") or {}).get(outer) or {}).get(inner)))
    return [x for x in map(fn, rows) if x]


def search_all(q: str) -> dict:
    return {"tracks": search(q, "track", 15), "artists": search(q, "artist", 6), "albums": search(q, "album", 8)}


def find_artist(name: str) -> str:
    return name                                      # Last.fm kennt Künstler über den Namen (mit Autokorrektur)


def artist_page(name: str) -> dict:
    name = _text(name)

    def load():
        a = _call("artist.getInfo", artist=name, lang="de").get("artist") or {}
        if not a.get("name"):
            raise LookupError("Künstler bei Last.fm nicht gefunden")
        top = _list((_call("artist.getTopTracks", artist=name, limit=50).get("toptracks") or {}).get("track"))
        alb = _list((_call("artist.getTopAlbums", artist=name, limit=30).get("topalbums") or {}).get("album"))
        stats = a.get("stats") or {}
        me = c.artist(SRC, ref(a["name"]), a["name"], fans=int(stats.get("listeners") or 0) or None, link=a.get("url"),
                      note="Hörer bei Last.fm") or {}
        return {"artist": {**me, "tags": [t["name"] for t in _list((a.get("tags") or {}).get("tag")) if t.get("name")][:8],
                           "plays": int(stats.get("playcount") or 0) or None},
                "top": [x for x in map(track, top) if x], "albums": [x for x in map(album, alb) if x],
                "related": [x for x in map(artist, _list((a.get("similar") or {}).get("artist"))) if x]}
    return c.cached(f"lf:a:{c.key(name)}", load)


def album_page(ident: str) -> dict:
    if "\t" not in str(ident or ""):
        raise ValueError("Ungültige Kennung")
    art, title = (_text(x) for x in str(ident).split("\t", 1))

    def load():
        a = _call("album.getInfo", artist=art, album=title, lang="de").get("album") or {}
        if not a.get("name"):
            raise LookupError("Album bei Last.fm nicht gefunden")
        base = album(a) or {}
        tracks = []
        for t in _list((a.get("tracks") or {}).get("track")):
            x = track({**t, "image": a.get("image")})
            if x:
                x.update(album=a["name"], album_id=base.get("id"))
                tracks.append(x)
        return {"album": {**base, "cover_big": _img(a.get("image"), "mega"), "label": None, "date": None,
                          "duration_ms": sum(t["duration_ms"] or 0 for t in tracks) or None,
                          "genres": [t["name"] for t in _list((a.get("tags") or {}).get("tag")) if t.get("name")][:6],
                          "artists": [base["artist"]] if base.get("artist") else []},
                "tracks": tracks}
    return c.cached(f"lf:al:{c.key(art)}:{c.key(title)}", load)


def genres() -> list[dict]:
    """Beliebte Tags als „Genres“; leer = Charts in Deutschland."""
    def load():
        tags = _list((_call("chart.getTopTags", limit=60).get("tags") or {}).get("tag"))
        return [{"id": "", "name": "Deutschland"}] + [{"id": t["name"], "name": t["name"]} for t in tags if t.get("name")]
    return c.cached("lf:genres", load)


def charts(tag: str = "") -> dict:
    tag = str(tag or "").strip()
    if len(tag) > 60 or "\n" in tag:
        raise ValueError("Ungültiger Tag")

    def load():
        if tag:
            tr = _list((_call("tag.getTopTracks", tag=tag, limit=50).get("tracks") or {}).get("track"))
            ar = _list((_call("tag.getTopArtists", tag=tag, limit=20).get("topartists") or {}).get("artist"))
            al = _list((_call("tag.getTopAlbums", tag=tag, limit=20).get("albums") or {}).get("album"))
        else:
            tr = _list((_call("geo.getTopTracks", country=COUNTRY, limit=50).get("tracks") or {}).get("track"))
            ar = _list((_call("geo.getTopArtists", country=COUNTRY, limit=20).get("topartists") or {}).get("artist"))
            al = []
        return {"tracks": [x for x in map(track, tr) if x], "artists": [x for x in map(artist, ar) if x],
                "albums": [x for x in map(album, al) if x]}
    return c.cached(f"lf:c:{tag.lower()}", load)

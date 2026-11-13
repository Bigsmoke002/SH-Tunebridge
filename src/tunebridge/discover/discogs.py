"""Entdecken-Quelle Discogs – nur mit deinem eigenen persönlichen Token (discogs.com › Einstellungen › Entwickler).
Stärke: Vinyl-, Label- und Underground-Veröffentlichungen mit Genres/Styles. Gesendet wird nur der Suchbegriff bzw.
die Discogs-Kennung – mit deinem Token; Discogs sieht deine IP-Adresse. Daten von Discogs (Quellenangabe Pflicht)."""
from __future__ import annotations

import re

import httpx

from .. import config, ratelimit
from . import _common as c

SRC, P = "discogs", "dg"
API = "https://api.discogs.com"
_ID = re.compile(r"^([amr])(\d{1,12})$")
_http = httpx.Client(timeout=12, follow_redirects=True,
                     headers={"User-Agent": "SH-Tunebridge/0.14 +https://github.com/Bigsmoke002/SH-Tunebridge"},
                     event_hooks=ratelimit.httpx_hooks("discogs", max_wait=4))


def available() -> bool:
    return bool(config.opt("DISCOGS_TOKEN"))


def _get(path: str, **params) -> dict:
    tok = config.opt("DISCOGS_TOKEN")
    if not tok:
        raise PermissionError("Kein Discogs-Token eingetragen")
    r = _http.get(f"{API}/{path}", params=params, headers={"Authorization": f"Discogs token={tok}"})
    if r.status_code == 429:
        ratelimit.blocked("discogs", None, "HTTP 429")
        raise ratelimit.LimitReached("discogs", 60, "Discogs-Limit erreicht")
    if r.status_code == 401:
        raise PermissionError("Discogs lehnt den Token ab")
    if r.status_code == 404:
        raise LookupError("Bei Discogs nicht gefunden")
    r.raise_for_status()
    return r.json()


def _parse(ident: str) -> tuple[str, str]:
    m = _ID.match(str(ident or "").strip())
    if not m:
        raise ValueError("Ungültige Kennung")
    return m.group(1), m.group(2)


def ref(kind: str, x) -> str | None:
    return f"{P}:{kind}{x}" if x else None


def _img(x: dict, big: bool = False) -> str | None:
    if big:
        imgs = x.get("images") or []
        pick = next((i for i in imgs if i.get("type") == "primary"), imgs[0] if imgs else {})
        return pick.get("uri") or pick.get("uri150")
    u = x.get("cover_image") or x.get("thumb")
    return None if not u or "spacer.gif" in u else u


def _ms(d: str) -> int | None:
    p = [int(x) for x in str(d or "").split(":") if x.isdigit()]
    return ((p[0] * 60 + p[1]) * 1000 if len(p) == 2 else (p[0] * 3600 + p[1] * 60 + p[2]) * 1000 if len(p) == 3 else None)


def _type(formats) -> str:
    f = " ".join(str(x) for x in formats or []).lower()
    return "Single" if "single" in f or '7"' in f else "EP" if re.search(r"\bep\b", f) else "Zusammenstellung" if "comp" in f else "Album"


def _split(title: str) -> tuple[str, str]:
    a, sep, t = str(title or "").partition(" - ")
    return (c.plain_name(a), t) if sep else ("", title)


def search(q: str, kind: str, limit: int = 20) -> list:
    if kind == "track":
        return []                                    # Discogs sucht Veröffentlichungen, keine einzelnen Songs
    typ = "artist" if kind == "artist" else "master"
    rows = c.cached(f"dg:s:{typ}:{q.lower()}:{limit}", lambda: _get("database/search", q=q, type=typ, per_page=min(limit, 25)).get("results") or [])
    out = []
    for r in rows:
        if kind == "artist":
            out.append(c.artist(SRC, ref("a", r.get("id")), r.get("title"), picture=_img(r), link=f"https://www.discogs.com/artist/{r.get('id')}"))
        else:
            art, title = _split(r.get("title"))
            out.append(c.album(SRC, ref("m", r.get("id")), title, artist_name=art or None, cover=_img(r), year_=c.year(r.get("year")),
                               type_=_type(r.get("format")), link=f"https://www.discogs.com/master/{r.get('id')}"))
    return [x for x in out if x]


def search_all(q: str) -> dict:
    return {"tracks": [], "artists": search(q, "artist", 6), "albums": search(q, "album", 10)}


def find_artist(name: str) -> str | None:
    want = c.key(name)
    hits = [a for a in search(name, "artist", 10) if c.key(a["name"]) == want]
    return hits[0]["id"].split(":", 1)[1] if hits else None     # Discogs hängt Namensvettern „(2)“ an – exakt = Hauptname


def artist_page(ident: str) -> dict:
    kind, num = _parse(ident)
    if kind != "a":
        raise ValueError("Ungültige Kennung")

    def load():
        a = _get(f"artists/{num}")
        rel = _get(f"artists/{num}/releases", sort="year", sort_order="desc", per_page=100).get("releases") or []
        albums = []
        for r in rel:
            if r.get("role") != "Main":
                continue                              # nur eigene Veröffentlichungen, keine Gastauftritte
            k = "m" if r.get("type") == "master" else "r"
            albums.append(c.album(SRC, ref(k, r.get("id")), r.get("title"), artist_name=r.get("artist") or a.get("name"),
                                  artist_id=ref("a", num), cover=_img(r), year_=c.year(r.get("year")),
                                  type_=_type([r.get("format")]) if r.get("format") else "Album",
                                  link=f"https://www.discogs.com/{'master' if k == 'm' else 'release'}/{r.get('id')}"))
        me = c.artist(SRC, ref("a", num), a.get("name"), picture=_img(a, True), link=a.get("uri")) or {}
        return {"artist": {**me, "picture_big": _img(a, True)}, "top": [], "albums": [x for x in albums if x], "related": []}
    return c.cached(f"dg:a:{num}", load)


def album_page(ident: str) -> dict:
    kind, num = _parse(ident)
    if kind == "a":
        raise ValueError("Ungültige Kennung")

    def load():
        a = _get(f"{'masters' if kind == 'm' else 'releases'}/{num}")
        people = [x for x in a.get("artists") or [] if x.get("name")]
        names, ids = [c.plain_name(x["name"]) for x in people], [ref("a", x.get("id")) for x in people]
        base = c.album(SRC, ref(kind, num), a.get("title"), artist_name=(names or [None])[0], artist_id=(ids or [None])[0],
                       cover=_img(a, True), year_=c.year(a.get("year") or a.get("released")),
                       type_=_type([f.get("name") for f in a.get("formats") or []] + [d for f in a.get("formats") or [] for d in f.get("descriptions") or []]),
                       link=a.get("uri")) or {}
        tracks = []
        for t in a.get("tracklist") or []:
            if t.get("type_") not in (None, "track"):
                continue
            tp = [x for x in t.get("artists") or [] if x.get("name")]
            x = c.track(SRC, title=t.get("title"), artists=[x["name"] for x in tp] or names,
                        artist_ids=[ref("a", x.get("id")) for x in tp] or ids, album=a.get("title"), album_id=base.get("id"),
                        cover=base.get("cover"), duration_ms=_ms(t.get("duration")))
            if x:
                tracks.append(x)
        return {"album": {**base, "cover_big": _img(a, True), "label": ", ".join(dict.fromkeys(l.get("name") for l in a.get("labels") or [] if l.get("name"))) or None,
                          "date": a.get("released") or (str(a["year"]) if a.get("year") else None),
                          "duration_ms": sum(t["duration_ms"] or 0 for t in tracks) or None,
                          "genres": list(dict.fromkeys((a.get("genres") or []) + (a.get("styles") or [])))[:8], "artists": names},
                "tracks": tracks}
    return c.cached(f"dg:al:{kind}{num}", load)

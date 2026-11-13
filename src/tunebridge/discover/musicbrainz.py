"""Entdecken-Quelle MusicBrainz: offene Musikdatenbank (Daten CC0, ohne Login). Stärke: vollständige Diskografien
mit allen Mitwirkenden, auch kleine Veröffentlichungen. Höchstens 1 Anfrage pro Sekunde. Cover kommen aus dem
Cover Art Archive (archive.org) – beim Anzeigen sieht das Internet Archive deine IP-Adresse."""
from __future__ import annotations

import re

from . import _common as c

SRC, P = "musicbrainz", "mb"
_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
PRIMARY = {"Album": "Album", "Single": "Single", "EP": "EP", "Broadcast": "Sendung", "Other": ""}
SECONDARY = {"Compilation": "Zusammenstellung", "Live": "Live", "Remix": "Remixe", "DJ-mix": "DJ-Mix",
             "Soundtrack": "Soundtrack", "Mixtape/Street": "Mixtape"}
SKIP = {"Interview", "Audiobook", "Audio drama", "Spokenword"}


def _get(path: str, **params) -> dict:
    from ..genres.sources import musicbrainz as mb
    return mb._get(path, **params)


def _uuid(x) -> str:
    s = str(x or "").strip().lower()
    if not _UUID.match(s):
        raise ValueError("Ungültige Kennung")
    return s


def ref(x) -> str | None:
    return f"{P}:{x}" if x else None


def _credit(ac: list) -> tuple[list[str], list]:
    people = [x for x in ac or [] if isinstance(x, dict) and (x.get("name") or (x.get("artist") or {}).get("name"))]
    return ([x.get("name") or x["artist"]["name"] for x in people], [ref((x.get("artist") or {}).get("id")) for x in people])


def cover(rgid: str | None, size: int = 250) -> str | None:
    return f"https://coverartarchive.org/release-group/{rgid}/front-{size}" if rgid else None


def _rg_type(rg: dict) -> str | None:
    sec = rg.get("secondary-types") or []
    if any(s in SKIP for s in sec):
        return None
    for s in sec:
        if s in SECONDARY:
            return SECONDARY[s]
    return PRIMARY.get(rg.get("primary-type") or "", "")


def artist(a: dict) -> dict | None:
    note = " · ".join(x for x in (a.get("disambiguation"), a.get("country")) if x)
    return c.artist(SRC, ref(a.get("id")), a.get("name"), note=note or None,
                    link=f"https://musicbrainz.org/artist/{a['id']}" if a.get("id") else None)


def album(rg: dict, owner: dict | None = None) -> dict | None:
    kind = _rg_type(rg)
    if kind is None:
        return None
    names, ids = _credit(rg.get("artist-credit"))
    return c.album(SRC, ref(rg.get("id")), rg.get("title"), artist_name=(names or [(owner or {}).get("name")])[0],
                   artist_id=(ids or [ref((owner or {}).get("id"))])[0], cover=cover(rg.get("id")),
                   year_=c.year(rg.get("first-release-date")), type_=kind,
                   link=f"https://musicbrainz.org/release-group/{rg['id']}" if rg.get("id") else None)


def recording(r: dict) -> dict | None:
    names, ids = _credit(r.get("artist-credit"))
    rel = (r.get("releases") or [{}])[0]
    rg = rel.get("release-group") or {}
    return c.track(SRC, title=r.get("title"), artists=names, artist_ids=ids, album=rel.get("title"),
                   album_id=ref(rg.get("id")), cover=cover(rg.get("id")), duration_ms=r.get("length"),
                   isrc=(r.get("isrcs") or [None])[0], ids={"musicbrainz": r.get("id")},
                   link=f"https://musicbrainz.org/recording/{r['id']}" if r.get("id") else None)


def search(q: str, kind: str, limit: int = 25) -> list:
    path, field, fn = {"track": ("recording", "recordings", recording), "artist": ("artist", "artists", artist),
                       "album": ("release-group", "release-groups", album)}[kind]
    rows = c.cached(f"mb:s:{kind}:{q.lower()}:{limit}", lambda: _get(path, query=q, limit=min(limit, 25)).get(field) or [])
    return [x for x in map(fn, rows) if x]


def search_all(q: str) -> dict:
    # Songs nur bei „Mehr Songs“ – bei 1 Anfrage/Sekunde bleibt die Übersicht so schnell
    return {"tracks": [], "artists": search(q, "artist", 8), "albums": search(q, "album", 10)}


def find_artist(name: str) -> str | None:
    want = c.key(name)
    rows = c.cached(f"mb:fa:{want}", lambda: _get("artist", query=f'artist:"{name}"', limit=10).get("artists") or [])
    hits = [a for a in rows if c.key(a.get("name")) == want and int(a.get("score") or 0) >= 90]
    return hits[0]["id"] if len(hits) == 1 else None                # Namensvettern: lieber nichts als den falschen


def artist_page(aid: str) -> dict:
    aid = _uuid(aid)

    def load():
        a = _get(f"artist/{aid}", inc="genres+tags+url-rels")
        if not a.get("id"):
            raise LookupError("Künstler bei MusicBrainz nicht gefunden")
        rgs = _get("release-group", artist=aid, limit=100).get("release-groups") or []
        owner = {"id": aid, "name": a.get("name")}
        tags = [g["name"] for g in sorted(a.get("genres") or [], key=lambda g: -(g.get("count") or 0)) if g.get("name")][:8]
        return {"artist": {**(artist(a) or {}), "tags": tags,
                           "life": " – ".join(x for x in ((a.get("life-span") or {}).get("begin"), (a.get("life-span") or {}).get("end")) if x) or None},
                "top": [], "albums": [x for x in (album(rg, owner) for rg in rgs) if x], "related": []}
    return c.cached(f"mb:a:{aid}", load)


def album_page(rgid: str) -> dict:
    rgid = _uuid(rgid)

    def load():
        rg = _get(f"release-group/{rgid}", inc="releases+artist-credits+genres")
        if not rg.get("id"):
            raise LookupError("Album bei MusicBrainz nicht gefunden")
        rels = sorted(rg.get("releases") or [], key=lambda r: (r.get("status") != "Official", r.get("date") or "9999"))
        rel = _get(f"release/{rels[0]['id']}", inc="recordings+artist-credits+labels+isrcs") if rels else {}
        base = album(rg) or c.album(SRC, ref(rgid), rg.get("title")) or {}
        names, _ = _credit(rg.get("artist-credit"))
        tracks = []
        for m in rel.get("media") or []:
            for t in m.get("tracks") or []:
                r = t.get("recording") or {}
                n, ids = _credit(t.get("artist-credit") or r.get("artist-credit"))
                x = c.track(SRC, title=t.get("title") or r.get("title"), artists=n or names, artist_ids=ids or None,
                            album=rg.get("title"), album_id=ref(rgid), cover=cover(rgid), duration_ms=t.get("length") or r.get("length"),
                            isrc=(r.get("isrcs") or [None])[0], ids={"musicbrainz": r.get("id")})
                if x:
                    tracks.append(x)
        labels = [li["label"]["name"] for li in rel.get("label-info") or []
                  if (li.get("label") or {}).get("name") and li["label"]["name"] != "[no label]"]
        return {"album": {**base, "cover_big": cover(rgid, 500), "label": ", ".join(dict.fromkeys(labels)) or None,
                          "date": rel.get("date") or rg.get("first-release-date"), "duration_ms": sum(t["duration_ms"] or 0 for t in tracks) or None,
                          "genres": [g["name"] for g in rg.get("genres") or [] if g.get("name")][:6], "artists": names},
                "tracks": tracks}
    return c.cached(f"mb:al:{rgid}", load)

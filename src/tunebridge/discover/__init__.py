"""„Entdecken“: im Katalog mehrerer Quellen stöbern – Suche (Songs, Künstler, Alben), Künstler- und Albumseiten,
Charts und Genres. Die eingeschalteten Quellen werden gleichzeitig gefragt, die Treffer zusammengeführt (gleicher Song
über ISRC bzw. Künstler + Titel, gleicher Künstler/gleiches Album über den Namen).

Quellen: Deezer, Apple (iTunes-Suche), MusicBrainz – ohne Login; Last.fm und Discogs nur mit deinem eigenen Key/Token.
Jede Quelle ist einzeln abschaltbar (Einstellungen › Datenschutz bzw. auf der Seite); die Prüfung passiert hier am
Server. Gesendet wird nur, was du suchst bzw. antippst (Suchbegriff, Name oder Kennung); Ergebnisse bleiben höchstens
eine Stunde im Arbeitsspeicher, Suchbegriffe werden nirgends gespeichert.
"""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, wait

from .. import config, store
from . import _common, apple, deezer, discogs, lastfm, musicbrainz
from ._common import clean_q, key

SOURCES = ("deezer", "apple", "musicbrainz", "discogs", "lastfm")          # Reihenfolge = Vorrang beim Zusammenführen
NAMES = {"deezer": "Deezer", "apple": "Apple Music", "musicbrainz": "MusicBrainz", "discogs": "Discogs", "lastfm": "Last.fm"}
MODS = {"deezer": deezer, "apple": apple, "musicbrainz": musicbrainz, "discogs": discogs, "lastfm": lastfm}
PREFIX = {"dz": "deezer", "it": "apple", "mb": "musicbrainz", "dg": "discogs", "lf": "lastfm"}
NEEDS = {"lastfm": ("LASTFM_API_KEY", "eigener Last.fm-API-Key"), "discogs": ("DISCOGS_TOKEN", "eigener Discogs-Token")}
CHARTS = ("deezer", "apple", "lastfm")
KINDS = ("track", "artist", "album")
_KEY = "discover_sources"
TIMEOUT = 15
_RAM = _common._RAM                                   # für Tests


class NoSource(ValueError):
    pass


# ------------------------------------------------------------------ Quellen ein/aus
def _stored() -> dict:
    try:
        raw = store.meta_get(_KEY)
        return json.loads(raw) if raw else {}
    except Exception:  # noqa: BLE001
        return {}


def available(src: str) -> bool:
    need = NEEDS.get(src)
    return not need or bool(config.opt(need[0]))


def settings() -> dict:
    s = _stored()
    return {"sources": [{"id": k, "name": NAMES[k], "on": bool(s.get(k, True)), "available": available(k),
                         "needs": NEEDS[k][1] if k in NEEDS else None} for k in SOURCES]}


def save_settings(data: dict) -> dict:
    s = _stored()
    for k in SOURCES:
        if k in (data or {}):
            s[k] = bool(data[k])
    store.meta_set(_KEY, json.dumps(s))
    return settings()


def active() -> list[str]:
    s = _stored()
    return [k for k in SOURCES if s.get(k, True) and available(k)]


def _need_active() -> list[str]:
    a = active()
    if not a:
        raise NoSource("Keine Quelle eingeschaltet – unter „Quellen“ mindestens eine wählen")
    return a


def parse(ref) -> tuple[str, str]:
    """„dz:123“ -> ("deezer", "123"); reine Zahl = Deezer (ältere Links)."""
    s = str(ref if ref is not None else "").strip()
    if s.isdigit():
        return "deezer", s
    p, sep, ident = s.partition(":")
    if not sep or p not in PREFIX or not ident or len(s) > 420:
        raise ValueError("Ungültige Kennung")
    return PREFIX[p], ident


def _check(src: str) -> None:
    if src not in active():
        raise LookupError(f"Die Quelle {NAMES[src]} ist ausgeschaltet oder nicht eingerichtet")


# ------------------------------------------------------------------ gleichzeitig fragen
def _parallel(jobs: dict) -> tuple[dict, dict]:
    """{name: fn} gleichzeitig ausführen -> (Ergebnisse, Fehler). Langsame Quellen fehlen nach TIMEOUT einfach."""
    if not jobs:
        return {}, {}
    ex = ThreadPoolExecutor(max_workers=len(jobs))
    futs = {ex.submit(fn): name for name, fn in jobs.items()}
    done, pending = wait(futs, timeout=TIMEOUT)
    ex.shutdown(wait=False, cancel_futures=True)
    ok, bad = {}, {}
    for f in done:
        try:
            ok[futs[f]] = f.result()
        except Exception as e:  # noqa: BLE001
            bad[futs[f]] = e
    for f in pending:
        bad[futs[f]] = TimeoutError(f"{NAMES.get(futs[f], futs[f])} antwortet zu langsam")
    return ok, bad


def _raise_if_all_failed(ok: dict, bad: dict) -> None:
    if ok or not bad:
        return
    errs = list(bad.values())
    for kind in (LookupError, ValueError):
        for e in errs:
            if isinstance(e, kind):
                raise e
    raise errs[0]


def _failed(bad: dict) -> dict:
    return {k: str(e) or type(e).__name__ for k, e in bad.items()}


# ------------------------------------------------------------------ zusammenführen
def _track_keys(t: dict) -> list[str]:
    ks = [f"t:{key((t.get('artists') or [''])[0])}|{key(t.get('title'))}"]
    if t.get("isrc"):
        ks.insert(0, f"i:{t['isrc'].upper()}")
    return ks


def _union(a: list, b: list) -> list:
    return a + [x for x in b if x not in a]


def merge_tracks(lists: list[list]) -> list:
    out, idx = [], {}
    for lst in lists:
        for t in lst or []:
            ks = _track_keys(t)
            hit = next((idx[k] for k in ks if k in idx), None)
            if hit is None:
                hit = {**t, "ids": dict(t.get("ids") or {}), "sources": list(t.get("sources") or [])}
                out.append(hit)
            else:
                for f in ("cover", "duration_ms", "isrc", "album", "album_id", "link"):
                    if not hit.get(f) and t.get(f):
                        hit[f] = t[f]
                hit["ids"] = {**(t.get("ids") or {}), **hit["ids"]}
                if str(hit.get("preview_url") or "").startswith("deezer:") and "|" in hit["preview_url"] and t.get("preview_url") \
                        and "|" not in t["preview_url"]:
                    hit["preview_url"] = t["preview_url"]          # echte Hörprobe statt „beim Abspielen suchen“
                ai = hit.get("artist_ids") or []
                if len(ai) == len(t.get("artist_ids") or []):
                    hit["artist_ids"] = [x or y for x, y in zip(ai, t["artist_ids"])]
                hit["sources"] = _union(hit["sources"], t.get("sources") or [])
            for k in ks:
                idx.setdefault(k, hit)
    return out


def _merge_named(lists: list[list], keyfn, fill: tuple) -> list:
    out, idx = [], {}
    for lst in lists:
        for x in lst or []:
            k = keyfn(x)
            hit = idx.get(k)
            src = (x.get("sources") or [""])[0]
            if hit is None or src in hit["refs"]:              # Namensvetter derselben Quelle bleibt eigener Eintrag
                hit = {**x, "refs": dict(x.get("refs") or {}), "sources": list(x.get("sources") or [])}
                out.append(hit)
                idx.setdefault(k, hit)
                continue
            for f in fill:
                if not hit.get(f) and x.get(f):
                    hit[f] = x[f]
            hit["refs"] = {**x.get("refs", {}), **hit["refs"]}
            hit["sources"] = _union(hit["sources"], x.get("sources") or [])
    return out


def merge_artists(lists: list[list]) -> list:
    return _merge_named(lists, lambda a: key(a.get("name")), ("picture", "fans", "albums", "note", "link"))


def merge_albums(lists: list[list]) -> list:
    return _merge_named(lists, lambda a: f"{key(a.get('artist'))}|{key(a.get('title'))}",
                        ("cover", "year", "type", "tracks", "artist_id", "link"))


# ------------------------------------------------------------------ Abfragen
def search(q: str, kind: str = "track", limit: int = 40) -> dict:
    q = clean_q(q)
    if kind not in KINDS:
        raise ValueError("Unbekannte Suchart")
    if not q:
        return {"q": "", "kind": kind, "items": [], "sources": []}
    srcs = _need_active()
    limit = max(1, min(int(limit), 50))
    ok, bad = _parallel({s: (lambda s=s: MODS[s].search(q, kind, limit)) for s in srcs})
    _raise_if_all_failed(ok, bad)
    lists = [ok[s] for s in SOURCES if s in ok]
    items = {"track": merge_tracks, "artist": merge_artists, "album": merge_albums}[kind](lists)
    return {"q": q, "kind": kind, "items": items[:80], "sources": [s for s in SOURCES if s in ok], "failed": _failed(bad)}


def search_all(q: str) -> dict:
    """Kurzübersicht für die Suchleiste: die besten Songs, Künstler und Alben aller Quellen auf einmal."""
    q = clean_q(q)
    if not q:
        return {"q": "", "tracks": [], "artists": [], "albums": [], "sources": [], "failed": {}}
    srcs = _need_active()
    ok, bad = _parallel({s: (lambda s=s: MODS[s].search_all(q)) for s in srcs})
    _raise_if_all_failed(ok, bad)
    got = [ok[s] for s in SOURCES if s in ok]
    return {"q": q, "tracks": merge_tracks([g["tracks"] for g in got])[:40],
            "artists": merge_artists([g["artists"] for g in got])[:16],
            "albums": merge_albums([g["albums"] for g in got])[:24],
            "sources": [s for s in SOURCES if s in ok], "failed": _failed(bad)}


def _bucket(albums: list) -> tuple[list, list]:
    albums = sorted(albums, key=lambda x: x.get("year") or "", reverse=True)
    small = ("Single", "EP", "Remixe")
    return [x for x in albums if x.get("type") not in small], [x for x in albums if x.get("type") in small]


def artist_page(ref, also=None) -> dict:
    """Künstlerseite: Grundlage aus der angetippten Quelle, dazu die anderen eingeschalteten Quellen – über
    mitgeschickte Kennungen ([also]) oder den exakt gleichen Namen (bei Namensvettern lieber gar nicht)."""
    src, ident = parse(ref)
    _check(src)
    base = MODS[src].artist_page(ident)
    name = base["artist"].get("name") or ""
    refs = {src: ident}
    for r in also or []:
        try:
            s, i = parse(r)
        except ValueError:
            continue
        if s in active() and s not in refs:
            refs[s] = i

    def other(s):
        i = refs.get(s) or MODS[s].find_artist(name)
        if not i:
            return None
        page = MODS[s].artist_page(i)
        if key(page["artist"].get("name")) != key(name):           # Sicherheitsnetz gegen falsche Zuordnung
            return None
        return i, page

    ok, bad = _parallel({s: (lambda s=s: other(s)) for s in active() if s != src})
    pages = {src: base}
    for s, v in ok.items():
        if v:
            refs[s], pages[s] = v
    order = [s for s in SOURCES if s in pages]
    art = dict(base["artist"])
    links, tags = {}, []
    for s in order:
        a = pages[s]["artist"]
        for f in ("picture", "picture_big", "fans", "albums", "note", "life", "plays"):
            if not art.get(f) and a.get(f):
                art[f] = a[f]
        if a.get("link"):
            links[s] = a["link"]
        tags = _union(tags, [t for t in a.get("tags") or [] if key(t) not in {key(x) for x in tags}])
    all_refs = {s: f"{next(p for p, n in PREFIX.items() if n == s)}:{i}" for s, i in refs.items()}
    merged = merge_albums([pages[s]["albums"] for s in order])
    if any(pages[s]["albums"] for s in order if s != "lastfm"):     # Last.fm-„Top-Alben“ nur ergänzen, nicht auffüllen
        merged = [x for x in merged if x["sources"] != ["lastfm"]]
    albums, singles = _bucket(merged)
    top = merge_tracks([pages[s]["top"] for s in ("deezer", "lastfm", "apple") if s in pages])[:60]
    return {"artist": {**art, "id": all_refs[src], "refs": all_refs, "links": links, "tags": tags[:10],
                       "picture_big": art.get("picture_big") or art.get("picture")},
            "top": top, "albums": albums, "singles": singles,
            "related": merge_artists([pages[s]["related"] for s in ("deezer", "lastfm") if s in pages])[:24],
            "sources": order, "failed": _failed(bad)}


def album_page(ref) -> dict:
    src, ident = parse(ref)
    _check(src)
    d = MODS[src].album_page(ident)
    return {**d, "album": {**d["album"], "links": {src: d["album"]["link"]} if d["album"].get("link") else {}},
            "sources": [src]}


def chart_sources() -> list[dict]:
    a = active()
    return [{"id": s, "name": NAMES[s] + (" · Deutschland" if s == "apple" else "")} for s in CHARTS if s in a]


def genres(source: str = "deezer") -> dict:
    """Genres/Tags je Charts-Quelle + welche Charts-Quellen es gibt."""
    srcs = chart_sources()
    if source not in CHARTS:
        raise ValueError("Unbekannte Quelle")
    if not any(x["id"] == source for x in srcs):
        return {"source": source, "genres": [], "charts": srcs}
    g = deezer.genres() if source == "deezer" else lastfm.genres() if source == "lastfm" else []
    return {"source": source, "genres": g, "charts": srcs}


def charts(source: str = "deezer", genre="") -> dict:
    if source not in CHARTS:
        raise ValueError("Unbekannte Quelle")
    _check(source)
    d = MODS[source].charts("" if genre is None else str(genre))
    return {"source": source, "genre": str(genre or ""), **d}

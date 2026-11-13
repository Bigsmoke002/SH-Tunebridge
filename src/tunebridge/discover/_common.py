"""Gemeinsame Bausteine der Entdecken-Quellen: Zwischenspeicher, einheitliche Einträge, Kennungen."""
from __future__ import annotations

import re
import threading
import time
import unicodedata

TTL = 3600
_RAM: dict[str, tuple[float, object]] = {}
_LOCK = threading.Lock()
_SPACE = re.compile(r"\s+")
_NAMESAKE = re.compile(r"\s\(\d+\)$")             # Discogs: „Hybrid (2)“


def cached(key: str, fn, ttl: float = TTL):
    """Ergebnis höchstens [ttl] Sekunden im Arbeitsspeicher – nichts landet auf der Platte."""
    with _LOCK:
        hit = _RAM.get(key)
    if hit and time.time() - hit[0] < ttl:
        return hit[1]
    val = fn()
    with _LOCK:
        _RAM[key] = (time.time(), val)
        if len(_RAM) > 600:
            for k, _ in sorted(_RAM.items(), key=lambda kv: kv[1][0])[:200]:
                _RAM.pop(k, None)
    return val


def clear() -> None:
    with _LOCK:
        _RAM.clear()


def clean_q(q) -> str:
    return _SPACE.sub(" ", str(q or "")).strip()[:100]


def key(s) -> str:
    """Vergleichsschlüssel für Namen/Titel über Quellen hinweg (Groß-/Kleinschreibung, Satzzeichen, „&“)."""
    s = unicodedata.normalize("NFKC", str(s or "")).casefold().replace("&", " and ")
    return re.sub(r"[\W_]+", "", s)


def plain_name(name: str) -> str:
    return _NAMESAKE.sub("", str(name or "")).strip()


def year(date) -> str | None:
    s = str(date or "")[:4]
    return s if s.isdigit() else None


def lazy_preview(artists: list[str], title: str) -> str | None:
    """Keine eigene Hörprobe: der Player sucht beim Abspielen die offizielle bei Deezer (wie „Mehr vom Künstler“)."""
    return f"deezer:{(artists or [''])[0]}|{title}" if title and artists else None


def track(src: str, *, title: str, artists: list[str], artist_ids: list | None = None, album: str | None = None,
          album_id: str | None = None, cover: str | None = None, duration_ms: int | None = None, isrc: str | None = None,
          explicit: bool = False, ids: dict | None = None, preview_url: str | None = None, rank: int = 0,
          link: str | None = None, with_: list[str] | None = None) -> dict | None:
    title = str(title or "").strip()
    artists = [plain_name(a) for a in artists or [] if str(a or "").strip()]
    if not title or not artists:
        return None
    ids = {k: str(v) for k, v in (ids or {}).items() if v}
    return {"title": title, "artists": artists,
            "artist_ids": (list(artist_ids) + [None] * len(artists))[:len(artists)] if artist_ids else [None] * len(artists),
            "album": album or None, "album_id": album_id, "cover": cover if str(cover or "").startswith("https://") else None,
            "duration_ms": int(duration_ms) if duration_ms else None, "rank": int(rank or 0), "explicit": bool(explicit),
            "isrc": (isrc or "").upper() or None, "ids": ids,
            "preview_url": preview_url or (f"deezer:{ids['deezer']}" if ids.get("deezer") else lazy_preview(artists, title)),
            "link": link, "with": with_ or [], "sources": [src]}


def artist(src: str, ref: str, name: str, *, picture: str | None = None, fans: int | None = None, albums: int | None = None,
           note: str | None = None, link: str | None = None) -> dict | None:
    name = plain_name(name)
    if not name or not ref:
        return None
    return {"id": ref, "name": name, "picture": picture if str(picture or "").startswith("https://") else None,
            "fans": int(fans) if fans else None, "albums": int(albums) if albums else None, "note": note or None,
            "link": link, "refs": {src: ref}, "sources": [src]}


ALBUM_TYPES = {"album": "Album", "single": "Single", "ep": "EP", "compile": "Zusammenstellung", "compilation": "Zusammenstellung",
               "broadcast": "Sendung", "other": "", "live": "Live", "remix": "Remixe", "dj-mix": "DJ-Mix", "soundtrack": "Soundtrack"}


def album(src: str, ref: str, title: str, *, artist_name: str | None = None, artist_id: str | None = None,
          cover: str | None = None, year_: str | None = None, type_: str = "", tracks: int | None = None,
          explicit: bool = False, link: str | None = None) -> dict | None:
    title = str(title or "").strip()
    if not title or not ref:
        return None
    return {"id": ref, "title": title, "artist": plain_name(artist_name) or None, "artist_id": artist_id,
            "cover": cover if str(cover or "").startswith("https://") else None, "year": year_, "type": type_ or "",
            "tracks": int(tracks) if tracks else None, "explicit": bool(explicit), "link": link,
            "refs": {src: ref}, "sources": [src]}


def first_text(*xs) -> str | None:
    for x in xs:
        if x:
            return x
    return None

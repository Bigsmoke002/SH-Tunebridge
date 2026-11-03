"""Links zu Songs, Alben und Playlists einfügen -> Songliste (nur Metadaten, nie Audio).

Nur offizielle Wege:
* Deezer        – öffentliche API (Song, Album, Playlist), ohne Login
* Spotify       – Web API mit deiner Spotify-App (eigene Playlists, Songs, Alben)
* TIDAL         – über deine TIDAL-Verbindung
* Apple Music   – iTunes-Lookup-API (Songs, Alben; Playlists bietet Apple öffentlich nicht an)
* YouTube/Music – oEmbed (einzelnes Video); Playlists mit eigenem YouTube-API-Key (Data API v3)
* SoundCloud    – oEmbed (einzelner Song)
* Deezer-Profil – Lieblingssongs eines öffentlichen Profils (öffentliche API)
* Last.fm-Profil – „Loved Tracks“ (offizielle API, eigener Last.fm-Key) – Last.fm sammelt das Hören von
                  Spotify, YouTube & Co., liefert also viele zusätzliche Infos
* Dateien       – Exporte der Dienste selbst (Apple Music, Google Takeout, Exportify …), siehe playlistfile.py
Rechtlich: Titel, Künstler, ISRC sind Fakten/Metadaten – kein urheberrechtlich geschütztes Werk.
Es wird nichts heruntergeladen oder gespeichert außer diesen Angaben.
"""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlsplit

import httpx

from . import config
from .models import Track

UA = {"User-Agent": "SH-Tunebridge"}


class LinkError(RuntimeError):
    pass


def _get(url: str, **kw) -> dict:
    try:
        r = httpx.get(url, timeout=20, headers=UA, follow_redirects=True, **kw)
    except httpx.HTTPError as e:
        raise LinkError(f"Nicht erreichbar: {e}") from e
    if r.status_code >= 400:
        raise LinkError(f"HTTP {r.status_code}")
    return r.json()


def _expand(url: str) -> str:
    """Kurzlinks (deezer.page.link, link.deezer.com, spotify.link, on.soundcloud.com) auflösen."""
    host = (urlsplit(url).hostname or "").lower()
    if host in ("deezer.page.link", "link.deezer.com", "spotify.link", "on.soundcloud.com", "youtu.be"):
        if host == "youtu.be":
            return "https://www.youtube.com/watch?v=" + urlsplit(url).path.strip("/")
        try:
            return str(httpx.head(url, timeout=10, follow_redirects=True, headers=UA).url)
        except httpx.HTTPError as e:
            raise LinkError(f"Kurzlink nicht auflösbar: {e}") from e
    return url


def parse(url: str) -> dict:
    """-> {service, kind (track|album|playlist), id}"""
    url = _expand(url.strip())
    u = urlsplit(url)
    host, path = (u.hostname or "").lower(), u.path
    q = parse_qs(u.query)
    if host.endswith("deezer.com"):
        m = re.search(r"/(track|album|playlist|profile)/(\d+)", path)
        if m:
            return {"service": "deezer", "kind": m[1], "id": m[2]}
    if host.endswith("last.fm") or host.endswith("lastfm.de"):
        m = re.search(r"/user/([^/?#]+)", path)
        if m:
            return {"service": "lastfm", "kind": "loved", "id": m[1]}
    if host == "open.spotify.com":
        m = re.search(r"/(track|album|playlist)/([A-Za-z0-9]+)", path)
        if m:
            return {"service": "spotify", "kind": m[1], "id": m[2]}
    if host.endswith("tidal.com"):
        m = re.search(r"/(track|album|playlist)/([0-9a-fA-F-]+)", path)
        if m:
            return {"service": "tidal", "kind": m[1], "id": m[2]}
    if host.endswith("music.apple.com"):
        if "i" in q:
            return {"service": "apple", "kind": "track", "id": q["i"][0]}
        m = re.search(r"/(song|album|playlist)/(?:[^/]+/)?((?:pl\.)?[\w.-]+)$", path)
        if m:
            return {"service": "apple", "kind": {"song": "track"}.get(m[1], m[1]), "id": m[2]}
    if host.endswith("youtube.com"):
        if "list" in q and "v" not in q:
            return {"service": "youtube", "kind": "playlist", "id": q["list"][0]}
        if "v" in q:
            return {"service": "youtube", "kind": "track", "id": q["v"][0]}
    if host.endswith("soundcloud.com") and path.count("/") >= 2:
        return {"service": "soundcloud", "kind": "playlist" if "/sets/" in path else "track", "id": url}
    raise LinkError("Diesen Link kenne ich nicht. Unterstützt: Deezer (auch Profile), Spotify, TIDAL, Apple Music, "
                    "YouTube, SoundCloud, Last.fm-Profile")


# ------------------------------------------------------------------ Dienste
def _dz_track(t: dict) -> Track:
    alb = t.get("album") or {}
    return Track(title=t.get("title") or "", artists=[(t.get("artist") or {}).get("name", "")],
                 album=alb.get("title"), duration_ms=(t.get("duration") or 0) * 1000 or None,
                 isrc=t.get("isrc"), ids={"deezer": str(t["id"])}, cover=alb.get("cover_medium"),
                 preview_url=t.get("preview") or None)


def _deezer_profile(i: str) -> tuple[str, list[Track]]:
    u = _get(f"https://api.deezer.com/user/{i}")
    if "error" in u:
        raise LinkError("Deezer: Profil nicht gefunden")
    items, url = [], f"https://api.deezer.com/user/{i}/tracks?limit=100"
    while url and len(items) < 2000:
        d = _get(url)
        if "error" in d:
            raise LinkError("Deezer: Die Lieblingssongs dieses Profils sind nicht öffentlich "
                            "(Deezer › Einstellungen › Datenschutz › Profil öffentlich) – oder einzelne Playlist-Links nutzen")
        items += d.get("data", [])
        url = d.get("next")
    return f"Lieblingssongs von {u.get('name', i)}", [_dz_track(t) for t in items]


def _lastfm(kind: str, user: str) -> tuple[str, list[Track]]:
    key = config.opt("LASTFM_API_KEY")
    if not key:
        raise LinkError("Für Last.fm-Profile bitte den Last.fm-API-Key eintragen (Einstellungen › Konten)")
    out, page, pages = [], 1, 1
    while page <= pages and len(out) < 2000:
        d = _get("https://ws.audioscrobbler.com/2.0/", params={
            "method": "user.getLovedTracks", "user": user, "api_key": key, "format": "json", "limit": 200, "page": page})
        if "error" in d:
            raise LinkError(f"Last.fm: {d.get('message', 'Profil nicht gefunden')}")
        lt = d.get("lovedtracks") or {}
        pages = int((lt.get("@attr") or {}).get("totalPages") or 1)
        for t in lt.get("track", []):
            out.append(Track(title=t.get("name", ""), artists=[(t.get("artist") or {}).get("name", "")]))
        page += 1
    return f"Last.fm: Lieblingssongs von {user}", out


def _deezer(kind: str, i: str) -> tuple[str, list[Track]]:
    if kind == "profile":
        return _deezer_profile(i)
    d = _get(f"https://api.deezer.com/{kind}/{i}")
    if "error" in d:
        raise LinkError(f"Deezer: {d['error'].get('message', 'nicht gefunden')}")
    if kind == "track":
        return d.get("title", ""), [_dz_track(d)]
    items, nxt = list((d.get("tracks") or {}).get("data", [])), (d.get("tracks") or {}).get("next")
    while nxt and len(items) < 2000:
        page = _get(nxt)
        items += page.get("data", [])
        nxt = page.get("next")
    if kind == "album":
        items = [{**t, "album": {"title": d.get("title"), "cover_medium": d.get("cover_medium")}} for t in items]
    return d.get("title", ""), [_dz_track(t) for t in items]


def _spotify(kind: str, i: str) -> tuple[str, list[Track]]:
    from .providers import get_provider
    sp = get_provider("spotify")
    if not sp.tok.get("access_token"):
        raise LinkError("Für Spotify-Links bitte zuerst Spotify verbinden (Übertragen › Spotify)")
    if kind == "track":
        t = sp.track(i)
        return t.title, [t]
    if kind == "album":
        return sp.album_tracks(i)
    return sp.playlist_name(i), sp.playlist_tracks(i)


def _tidal(kind: str, i: str) -> tuple[str, list[Track]]:
    from .providers import get_provider
    from .providers.tidal import _to_track
    td = get_provider("tidal")
    if not td.connected():
        raise LinkError("Für TIDAL-Links bitte zuerst TIDAL verbinden (Übertragen › TIDAL)")
    if kind == "track":
        t = _to_track(td.s.track(i))
        return t.title, [t]
    if kind == "album":
        a = td.s.album(i)
        return a.name, [_to_track(t) for t in a.tracks()]
    p = td.s.playlist(i)
    return p.name, [_to_track(t) for t in p.tracks_paginated()]


def _apple(kind: str, i: str) -> tuple[str, list[Track]]:
    if kind == "playlist":
        raise LinkError("Apple-Music-Playlists stellt Apple öffentlich nicht bereit – bitte einzelne Songs/Alben")
    d = _get("https://itunes.apple.com/lookup", params={"id": i, "entity": "song", "limit": 200})
    res = d.get("results", [])
    songs = [r for r in res if r.get("wrapperType") == "track"]
    if not songs:
        raise LinkError("Apple Music: nichts gefunden")
    tracks = [Track(title=r.get("trackName", ""), artists=[r.get("artistName", "")], album=r.get("collectionName"),
                    duration_ms=r.get("trackTimeMillis"), ids={"apple": str(r.get("trackId"))},
                    cover=(r.get("artworkUrl100") or "").replace("100x100", "300x300") or None,
                    preview_url=r.get("previewUrl")) for r in songs]
    name = next((r.get("collectionName") for r in res if r.get("wrapperType") == "collection"), tracks[0].title)
    return name, tracks


def split_title(raw: str, author: str = "") -> tuple[list[str], str]:
    """„Künstler - Titel (Official Video)“ -> (["Künstler"], "Titel")."""
    t = re.sub(r"\s*[\(\[](official|offizielles|lyric|lyrics|audio|video|visualizer|hd|4k|music video)[^\)\]]*[\)\]]",
               "", raw, flags=re.I).strip()
    m = re.match(r"^(.+?)\s+[-–—]\s+(.+)$", t)
    if m:
        return [m[1].strip()], m[2].strip()
    author = re.sub(r"\s*-\s*Topic$|VEVO$|Official$", "", author or "").strip()
    return ([author] if author else []), t


def _youtube(kind: str, i: str) -> tuple[str, list[Track]]:
    if kind == "track":
        d = _get("https://www.youtube.com/oembed", params={"url": f"https://www.youtube.com/watch?v={i}",
                                                            "format": "json"})
        artists, title = split_title(d.get("title", ""), d.get("author_name", ""))
        return title, [Track(title=title, artists=artists, ids={"youtube": i})]
    key = config.opt("YOUTUBE_API_KEY")
    if not key:
        raise LinkError("Für YouTube-Playlists bitte einen eigenen YouTube-API-Key eintragen (Einstellungen › Konten)")
    meta = _get("https://www.googleapis.com/youtube/v3/playlists", params={"part": "snippet", "id": i, "key": key})
    name = ((meta.get("items") or [{}])[0].get("snippet") or {}).get("title", "")
    out, token = [], None
    while len(out) < 2000:
        d = _get("https://www.googleapis.com/youtube/v3/playlistItems", params={
            "part": "snippet", "playlistId": i, "maxResults": 50, "key": key, **({"pageToken": token} if token else {})})
        for it in d.get("items", []):
            sn = it.get("snippet") or {}
            if sn.get("title") in ("Private video", "Deleted video"):
                continue
            artists, title = split_title(sn.get("title", ""), sn.get("videoOwnerChannelTitle", ""))
            out.append(Track(title=title, artists=artists,
                             ids={"youtube": (sn.get("resourceId") or {}).get("videoId", "")}))
        token = d.get("nextPageToken")
        if not token:
            break
    return name, out


def _soundcloud(kind: str, url: str) -> tuple[str, list[Track]]:
    if kind == "playlist":
        raise LinkError("SoundCloud-Sets bietet SoundCloud ohne API-Zugang nicht an – bitte einzelne Songs")
    d = _get("https://soundcloud.com/oembed", params={"url": url, "format": "json"})
    raw = re.sub(r"\s+by\s+" + re.escape(d.get("author_name", "")) + r"$", "", d.get("title", ""))
    artists, title = split_title(raw, d.get("author_name", ""))
    return title, [Track(title=title, artists=artists, ids={"soundcloud": url})]


def resolve(url: str) -> dict:
    p = parse(url)
    fn = {"deezer": _deezer, "spotify": _spotify, "tidal": _tidal, "apple": _apple,
          "youtube": _youtube, "soundcloud": _soundcloud, "lastfm": _lastfm}[p["service"]]
    name, tracks = fn(p["kind"], p["id"])
    tracks = [t for t in tracks if t.title]
    if not tracks:
        raise LinkError("Keine Songs gefunden")
    return {**p, "name": name, "tracks": tracks}


# ------------------------------------------------------------------ Analyse-Aufträge
import threading  # noqa: E402
import time  # noqa: E402
import uuid  # noqa: E402

_jobs: dict[str, dict] = {}
MAX_TRACKS = 500


def _analyse_one(t: Track) -> dict:
    from .enrich import enrich
    from .recognize.engines import Recognition
    rec = Recognition(engine="link", title=t.title, artists=t.artists or [""], album=t.album, isrc=t.isrc,
                      cover=t.cover, preview_url=t.preview_url, duration_ms=t.duration_ms)
    track, extra = enrich(rec)
    track.ids = {**t.ids, **track.ids}
    return {"title": track.title, "artist": track.artist, "artists": track.artists, "album": track.album,
            "isrc": track.isrc or t.isrc, "ids": track.ids, "cover": track.cover or t.cover,
            "preview_url": track.preview_url or t.preview_url, "genre": track.genre, "subgenre": track.subgenre,
            "niche": track.niche, "confidence": extra.get("confidence"), "bpm": extra.get("bpm"),
            "deezer": (extra.get("links") or {}).get("deezer", "").rsplit("/", 1)[-1] or None,
            "tags": list((track.tags or {}).keys())[:20], "ai": extra.get("ai")}


def _run(job: dict) -> None:
    from collections import Counter
    from . import debuglog as dbg
    try:
        job["state"] = "loading"
        res = job.pop("preset", None) or resolve(job["url"])
        job.update(service=res["service"], kind=res["kind"], name=res["name"])
        tracks = res["tracks"][:MAX_TRACKS]
        job["total"], job["cut"] = len(tracks), max(0, len(res["tracks"]) - MAX_TRACKS)
        job["state"] = "analysing"
        for i, t in enumerate(tracks):
            if job["cancel"]:
                raise InterruptedError
            try:
                job["items"].append(_analyse_one(t))
            except Exception as e:      # ein Song darf nicht alles abbrechen
                dbg.error("links", "Song-Analyse fehlgeschlagen", e)
                job["items"].append({"title": t.title, "artist": ", ".join(t.artists), "artists": t.artists,
                                     "isrc": t.isrc, "ids": t.ids, "cover": t.cover, "genre": None,
                                     "preview_url": t.preview_url})
            job["done"] = i + 1
        job["verteilung"] = dict(Counter(x.get("genre") or "unbekannt" for x in job["items"]).most_common())
        job["state"] = "done"
    except InterruptedError:
        job["state"] = "cancelled"
    except LinkError as e:
        job.update(state="error", error=str(e))
    except Exception as e:
        dbg.error("links", "Link-Analyse abgebrochen", e)
        job.update(state="error", error=str(e))


def start(url: str | None = None, preset: dict | None = None) -> str:
    """Link analysieren – oder eine schon eingelesene Liste (preset: {service, kind, name, tracks}, z. B. Datei)."""
    if preset is None:
        parse(url or "")            # sofort melden, wenn der Link unbekannt ist
    jid = uuid.uuid4().hex[:10]
    _jobs[jid] = {"id": jid, "url": url or "", "state": "queued", "done": 0, "total": 0, "items": [],
                  "cancel": False, "started": time.time(), **({"preset": preset} if preset else {})}
    threading.Thread(target=_run, args=(_jobs[jid],), daemon=True).start()
    for k in [k for k, j in _jobs.items() if time.time() - j["started"] > 6 * 3600]:
        _jobs.pop(k, None)          # alte Aufträge nicht ewig im Speicher halten
    return jid


def job(jid: str) -> dict | None:
    j = _jobs.get(jid)
    return {k: v for k, v in j.items() if k not in ("cancel", "preset")} if j else None


def cancel(jid: str) -> None:
    if jid in _jobs:
        _jobs[jid]["cancel"] = True


def tracks(jid: str, indices: list[int] | None = None) -> list[Track]:
    j = _jobs.get(jid)
    if not j:
        return []
    items = [x for i, x in enumerate(j["items"]) if indices is None or i in indices]
    return [Track(title=x["title"], artists=x.get("artists") or [x.get("artist", "")], album=x.get("album"),
                  isrc=x.get("isrc"), ids=x.get("ids") or {}, cover=x.get("cover"), genre=x.get("genre"),
                  subgenre=x.get("subgenre"), niche=x.get("niche"), preview_url=x.get("preview_url"))
            for x in items]

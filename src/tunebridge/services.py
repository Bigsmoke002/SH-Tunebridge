"""„Dienste“: Playlists der Musikanbieter ansehen und als Vorschau sortieren lassen.

Rechtlich sauber: nur offizielle Schnittstellen, nur eigene Konten bzw. öffentliche Profile, nur Metadaten.
* Spotify, TIDAL   – eigenes, verbundenes Konto (Lesen + neue Playlists anlegen)
* Deezer           – öffentliches Profil (Lieblingssongs + öffentliche Playlists), ohne Login
* Last.fm          – öffentliches Profil (Loved Tracks), eigener Last.fm-Key
* YouTube          – Google-Login (eigene OAuth-App, nur Lesen) oder öffentliche Playlists eines Kanals (API-Key)
* SoundCloud       – Login mit eigener SoundCloud-App (Artist Pro nötig, nur Lesen)
* Apple Music      – nur Datei-Export (offizielle API kostet 99 $/Jahr)
"""

from __future__ import annotations

import json
import re
import threading
import time
import uuid

import httpx

from . import config, dataexport, store
from . import debuglog as dbg
from .models import Track

_PROFILES = "service_profiles"
_http = httpx.Client(timeout=20, headers={"User-Agent": "tunebridge/0.4"})

SERVICES = [
    # id, Name, Art (account|profile|file|none), schreibbar?
    ("spotify", "Spotify", "account", True),
    ("tidal", "TIDAL", "account", True),
    ("youtube", "YouTube / YouTube Music", "account", False),
    ("deezer", "Deezer", "profile", False),
    ("lastfm", "Last.fm", "profile", False),
    ("apple", "Apple Music", "file", False),
    ("soundcloud", "SoundCloud", "account", False),
]
NOTES = {
    "spotify": "Eigene Playlists und Lieblingssongs. Sortierte Playlists können direkt in Spotify angelegt werden.",
    "tidal": "Eigene Playlists und Favoriten. Sortierte Playlists können direkt in TIDAL angelegt werden.",
    "youtube": "Mit Google anmelden: deine Playlists (auch private) und „Mag ich“-Videos – darin landen meist auch "
               "Likes aus YouTube Music. Alternativ nur öffentliche Playlists eines Kanals mit API-Key.",
    "deezer": "Öffentliches Profil: Lieblingssongs und öffentliche Playlists – ohne Login.",
    "lastfm": "Öffentliches Profil: deine Loved Tracks. Last.fm sammelt auch, was du bei Spotify/YouTube hörst.",
    "apple": "Apple erlaubt den Zugriff nur mit kostenpflichtigem Entwicklerkonto. Lösung: in der Musik-App "
             "die Mediathek exportieren und hier laden – alle Playlists auf einmal.",
    "soundcloud": "Mit deiner eigenen SoundCloud-App anmelden (offizielle API, dafür braucht dein Konto Artist Pro): "
                  "deine Playlists und Likes. Ohne App: einzelne Songs über „Link einfügen“.",
}


class ServiceError(RuntimeError):
    pass


# ------------------------------------------------------------------ Profile (Deezer/Last.fm/YouTube)
def profiles() -> dict:
    try:
        return json.loads(store.meta_get(_PROFILES) or "{}")
    except ValueError:
        return {}


def _get(url: str, **params) -> dict:
    r = _http.get(url, params=params)
    try:
        return r.json()
    except ValueError as e:
        raise ServiceError(f"Unerwartete Antwort ({r.status_code})") from e


def set_profile(svc: str, value: str) -> dict:
    """Profil-Link oder Name speichern (leer = entfernen). Prüft, ob es das Profil gibt."""
    value = (value or "").strip()
    p = profiles()
    if not value:
        p.pop(svc, None)
        store.meta_set(_PROFILES, json.dumps(p))
        return p
    if svc == "deezer":
        m = re.search(r"(?:profile|user)/(\d+)", value) or re.fullmatch(r"(\d+)", value)
        if not m:
            raise ServiceError("Bitte den Link zu deinem Deezer-Profil einfügen (deezer.com/…/profile/123456)")
        u = _get(f"https://api.deezer.com/user/{m[1]}")
        if "error" in u:
            raise ServiceError("Deezer-Profil nicht gefunden")
        p[svc] = {"id": m[1], "name": u.get("name") or m[1]}
    elif svc == "lastfm":
        m = re.search(r"last\.fm/(?:[a-z]{2}/)?user/([^/?#]+)", value) or re.fullmatch(r"([\w.-]{2,15})", value)
        if not m:
            raise ServiceError("Bitte deinen Last.fm-Benutzernamen oder Profil-Link eingeben")
        key = config.opt("LASTFM_API_KEY")
        if not key:
            raise ServiceError("Dafür bitte zuerst den Last.fm-API-Key eintragen (Einstellungen › Konten & Dienste)")
        d = _get("https://ws.audioscrobbler.com/2.0/", method="user.getInfo", user=m[1], api_key=key, format="json")
        if "error" in d:
            raise ServiceError(f"Last.fm: {d.get('message', 'Profil nicht gefunden')}")
        p[svc] = {"id": d["user"]["name"], "name": d["user"]["name"]}
    elif svc == "youtube":
        key = config.opt("YOUTUBE_API_KEY")
        if not key:
            raise ServiceError("Dafür bitte zuerst einen eigenen YouTube-API-Key eintragen (Einstellungen › Konten & Dienste)")
        m = re.search(r"/channel/(UC[\w-]{22})", value) or re.fullmatch(r"(UC[\w-]{22})", value)
        if m:
            q = {"id": m[1]}
        else:
            h = re.search(r"@([\w.-]+)", value)
            if not h:
                raise ServiceError("Bitte den Link zu deinem YouTube-Kanal einfügen (youtube.com/@name)")
            q = {"forHandle": "@" + h[1]}
        d = _get("https://www.googleapis.com/youtube/v3/channels", part="snippet", key=key, **q)
        if not d.get("items"):
            raise ServiceError("YouTube-Kanal nicht gefunden")
        it = d["items"][0]
        p[svc] = {"id": it["id"], "name": it["snippet"]["title"]}
    else:
        raise ServiceError("Für diesen Dienst gibt es kein Profil")
    store.meta_set(_PROFILES, json.dumps(p))
    return p


# ------------------------------------------------------------------ Übersicht
def overview(account_state) -> list[dict]:
    """account_state(pid) -> (verbunden, Kontoname) – kommt aus der Web-App (zwischengespeichert)."""
    p = profiles()
    out = []
    for sid, name, kind, writable in SERVICES:
        st = {"id": sid, "name": name, "kind": kind, "writable": writable, "note": NOTES[sid],
              "ready": False, "account": None, "needs": None}
        if kind == "account":
            try:
                ok, acc = account_state(sid)
            except Exception:  # noqa: BLE001
                ok, acc = False, None
            st.update(ready=ok, account=acc, needs=None if ok else ("connect" if _configured(sid) else "setup"))
            if not ok and sid == "youtube" and config.opt("YOUTUBE_API_KEY") and sid in p:   # Kanal-Profil (öffentlich)
                st.update(ready=True, account=p[sid]["name"], needs=None, mode="profile")
        elif kind == "profile":
            need_key = {"lastfm": "LASTFM_API_KEY", "youtube": "YOUTUBE_API_KEY"}.get(sid)
            if need_key and not config.opt(need_key):
                st["needs"] = "key"
            elif sid not in p:
                st["needs"] = "profile"
            else:
                st.update(ready=True, account=p[sid]["name"])
        elif kind == "file":
            st.update(needs="import")
        imp = dataexport.info(sid) if sid in dataexport.IMPORT_SERVICES else None
        st["import"] = imp
        st["importable"] = sid in dataexport.IMPORT_SERVICES
        if imp and not st["ready"]:
            st.update(ready=True, needs=None, mode="import",
                      account=f"Import vom {time.strftime('%d.%m.%Y', time.localtime(imp['imported']))}")
        out.append(st)
    return out


def _configured(sid: str) -> bool:
    if sid in ("youtube", "soundcloud"):
        from .providers import get_provider
        return get_provider(sid).configured()
    if sid == "spotify":
        return bool(config.opt("SPOTIFY_CLIENT_ID"))
    return True


def oauth_ready(sid: str) -> bool:
    """Ist ein Konto per Login verbunden (Token vorhanden)? – ohne Netzabfrage."""
    if sid not in ("youtube", "soundcloud"):
        return False
    from .providers import get_provider
    prov = get_provider(sid)
    return bool(prov.tok.get("access_token")) and prov.configured()


def _use_import(sid: str) -> bool:
    """Datei-Import nutzen, wenn kein Konto verbunden ist (ein verbundenes Konto ist aktueller)."""
    if sid not in dataexport.IMPORT_SERVICES or not dataexport.info(sid):
        return False
    if sid == "spotify":
        from .providers import get_provider
        return not get_provider("spotify").tok.get("access_token")
    return sid == "apple" or not oauth_ready(sid)


def playlists(sid: str) -> list[dict]:
    if _use_import(sid):
        return dataexport.playlists(sid)
    p = profiles().get(sid) or {}
    if sid in ("spotify", "tidal") or oauth_ready(sid):
        from .providers import get_provider
        prov = get_provider(sid)
        lists = prov.playlist_list()
        try:
            liked = prov.liked_count()
        except Exception:  # noqa: BLE001
            liked = None
        return [{"id": "__liked__", "name": "Lieblingssongs", "count": liked, "own": True}] + lists
    if sid == "deezer":
        out = [{"id": "__liked__", "name": "Lieblingssongs", "count": None, "own": True}]
        url = f"https://api.deezer.com/user/{p['id']}/playlists?limit=100"
        while url and len(out) < 500:
            d = _get(url)
            if "error" in d:
                break
            out += [{"id": str(x["id"]), "name": x.get("title", ""), "count": x.get("nb_tracks"),
                     "cover": x.get("picture_medium"), "own": (x.get("creator") or {}).get("id") == int(p["id"])}
                    for x in d.get("data", [])]
            url = d.get("next")
        return out
    if sid == "lastfm":
        d = _get("https://ws.audioscrobbler.com/2.0/", method="user.getLovedTracks", user=p["id"], limit=1,
                 api_key=config.opt("LASTFM_API_KEY"), format="json")
        total = int(((d.get("lovedtracks") or {}).get("@attr") or {}).get("total") or 0)
        return [{"id": "__liked__", "name": "Lieblingssongs (Loved Tracks)", "count": total, "own": True}]
    if sid == "youtube":
        out, token = [], None
        while len(out) < 500:
            d = _get("https://www.googleapis.com/youtube/v3/playlists", part="snippet,contentDetails",
                     channelId=p["id"], maxResults=50, key=config.opt("YOUTUBE_API_KEY"),
                     **({"pageToken": token} if token else {}))
            if "error" in d:
                raise ServiceError("YouTube: " + (d["error"].get("message") or "Fehler"))
            out += [{"id": x["id"], "name": x["snippet"]["title"], "count": (x.get("contentDetails") or {}).get("itemCount"),
                     "cover": ((x["snippet"].get("thumbnails") or {}).get("medium") or {}).get("url"), "own": True}
                    for x in d.get("items", [])]
            token = d.get("nextPageToken")
            if not token:
                break
        return out
    raise ServiceError("Für diesen Dienst gibt es keine Playlist-Liste")


def load(sid: str, pid: str) -> tuple[str, list[Track]]:
    from . import linkimport
    if _use_import(sid):
        return dataexport.load(sid, pid)
    p = profiles().get(sid) or {}
    if sid in ("spotify", "tidal") or oauth_ready(sid):
        from . import transfer
        return "", transfer.load(sid, pid)
    if sid == "deezer":
        return linkimport._deezer_profile(p["id"]) if pid == "__liked__" else linkimport._deezer("playlist", pid)
    if sid == "lastfm":
        return linkimport._lastfm("loved", p["id"])
    if sid == "youtube":
        return linkimport._youtube("playlist", pid)
    raise ServiceError("Unbekannter Dienst")


# ------------------------------------------------------------------ Sortier-Aufträge
_jobs: dict[str, dict] = {}
MAX_TRACKS = 1000


def _item(t: Track, a: dict) -> dict:
    return {**a, "duration_ms": t.duration_ms, "album": a.get("album") or t.album}


def _run(job: dict) -> None:
    from . import audiofeat, linkimport
    try:
        job["state"] = "loading"
        if job.get("preset") is not None:
            name, tracks = job.pop("preset")
        else:
            name, tracks = load(job["service"], job["playlist"])
        job["name"] = job.get("name") or name
        tracks = tracks[:MAX_TRACKS]
        job["total"] = len(tracks)
        job["state"] = "analysing"
        for i, t in enumerate(tracks):
            if job["cancel"]:
                raise InterruptedError
            try:
                a = linkimport._analyse_one(t)
            except Exception as e:  # noqa: BLE001
                dbg.error("sortieren", "Song-Analyse fehlgeschlagen", e)
                a = {"title": t.title, "artist": ", ".join(t.artists), "artists": t.artists, "ids": t.ids,
                     "isrc": t.isrc, "cover": t.cover, "genre": None}
            it = _item(t, a)
            try:
                tr = Track(title=it["title"], artists=it.get("artists") or [it.get("artist", "")], isrc=it.get("isrc"),
                           ids=it.get("ids") or {}, preview_url=it.get("preview_url"), genre=it.get("genre"))
                f = audiofeat.features(tr, deezer_bpm=it.get("bpm"))
                if f:
                    it.update(bpm=f.get("bpm"), camelot=f.get("camelot"), key=f.get("key"), energy=f.get("energy"))
            except Exception as e:  # noqa: BLE001
                dbg.error("sortieren", "Tempo/Tonart nicht ermittelt", e)
            job["items"].append(it)
            job["done"] = i + 1
        if job.get("ai_check"):
            job["state"] = "ai"
            try:
                from . import ai
                fixes = ai.review_genres(job["items"])
                for f in fixes:
                    it = job["items"][f["i"]]
                    it["ki"] = {"vorher": [it.get("genre"), it.get("subgenre")], "grund": f.get("grund")}
                    it["genre"], it["subgenre"] = f["genre"], f.get("subgenre")
                job["ai_fixes"] = len(fixes)
            except Exception as e:  # noqa: BLE001
                job["ai_error"] = str(e)
                dbg.error("sortieren", "KI-Prüfung fehlgeschlagen", e)
        job["state"] = "done"
    except InterruptedError:
        job["state"] = "cancelled"
    except Exception as e:  # noqa: BLE001
        dbg.error("sortieren", "Sortier-Vorschau abgebrochen", e)
        job.update(state="error", error=str(e))
    job["finished"] = time.time()


def start(service: str, playlist: str, name: str = "", ai_check: bool = False,
          preset: tuple[str, list[Track]] | None = None) -> str:
    jid = uuid.uuid4().hex[:10]
    _jobs[jid] = {"id": jid, "service": service, "playlist": playlist, "name": name, "ai_check": ai_check,
                  "state": "queued", "done": 0, "total": 0, "items": [], "cancel": False, "started": time.time(),
                  **({"preset": preset} if preset is not None else {})}
    threading.Thread(target=_run, args=(_jobs[jid],), daemon=True).start()
    for k in [k for k, j in _jobs.items() if time.time() - j["started"] > 6 * 3600]:
        _jobs.pop(k, None)
    return jid


def job(jid: str) -> dict | None:
    j = _jobs.get(jid)
    return {k: v for k, v in j.items() if k not in ("cancel", "preset")} if j else None


def cancel(jid: str) -> None:
    if jid in _jobs:
        _jobs[jid]["cancel"] = True


def groups(jid: str, level: int, min_size: int) -> list[dict]:
    from . import sorter
    j = _jobs.get(jid)
    if not j:
        raise ServiceError("Auftrag nicht gefunden (abgelaufen?) – bitte neu starten")
    return sorter.sort(j["items"], level, min_size)


def _track(it: dict) -> Track:
    return Track(title=it["title"], artists=it.get("artists") or [it.get("artist", "")], album=it.get("album"),
                 isrc=it.get("isrc"), ids=it.get("ids") or {}, cover=it.get("cover"), genre=it.get("genre"),
                 subgenre=it.get("subgenre"), niche=it.get("niche"), duration_ms=it.get("duration_ms"),
                 preview_url=it.get("preview_url"))


def apply(jid: str, plan: list[dict], target: str, prefix: str = "") -> dict:
    """plan: [{name, items:[Index…]}] (vom Nutzer evtl. umbenannt/umsortiert). target: local | spotify | tidal."""
    j = _jobs.get(jid)
    if not j:
        raise ServiceError("Auftrag nicht gefunden (abgelaufen?) – bitte neu starten")
    items = j["items"]
    made, missing = [], 0
    if target == "local":
        for g in plan:
            name = (prefix + g["name"]).strip()[:120]
            for i in g["items"]:
                store.add_to_playlist(name, _track(items[i]))
            made.append({"name": name, "count": len(g["items"])})
        return {"playlists": made, "missing": 0}
    from .providers import get_provider
    from .transfer import _match
    prov = get_provider(target)
    if not prov.connected():
        raise ServiceError("Bitte zuerst verbinden")
    for g in plan:
        found = []
        for i in g["items"]:
            t = _track(items[i])
            m = t if t.ids.get(prov.name) else _match(prov, t)
            if m:
                found.append(m)
            else:
                missing += 1
        if not found:
            continue
        name = (prefix + g["name"]).strip()[:100]
        pid = prov.create_playlist(name, "Sortiert mit SH-Tunebridge")
        prov.add_to_playlist(pid, found)
        made.append({"name": name, "count": len(found), "url": getattr(prov, "playlist_url", lambda x: None)(pid)})
    dbg.event("sortieren", f"{len(made)} Playlists in {target} angelegt", fehlend=missing)
    return {"playlists": made, "missing": missing}


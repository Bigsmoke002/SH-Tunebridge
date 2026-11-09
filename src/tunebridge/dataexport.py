"""Offizielle Datenexporte der Dienste einlesen – der Weg ohne Entwickler-App, ohne Premium, ohne Fachwissen.

Jede und jeder hat nach DSGVO Art. 15/20 Anspruch auf eine Kopie der eigenen Daten. Die Dienste liefern sie als Datei:
* Spotify:  Konto › Datenschutz › „Daten herunterladen“ (Kontodaten) -> ZIP mit Playlist*.json + YourLibrary.json
* YouTube / YouTube Music: Google Takeout (nur „YouTube und YouTube Music“, Playlists + Musikbibliothek) -> ZIP mit CSV
* Apple Music: Musik-App › Datei › Bibliothek › „Bibliothek exportieren …“ -> Mediathek.xml (alle Playlists)
* Shazam: shazam.com › „Meine Bibliothek“ › „CSV herunterladen“ -> shazamlibrary.csv (alle Shazams mit Zeitpunkt)
  Shazam/Apple bieten keine Schnittstelle zum Anmelden – fremde App-Tokens abgreifen ist tabu, daher die Datei.
* außerdem einzelne Dateien wie bisher (Exportify-CSV, .m3u, Apple-Playlist-XML/-TXT)

Gelesen werden nur Playlist-Namen, Titel, Künstler, Album, ISRC/Video-ID. Der Rest des Exports (Hörverlauf,
Suchanfragen, Zahlungsdaten …) wird nicht angefasst und nichts davon gespeichert. Die Datei selbst wird nicht
aufbewahrt – nur die gefundenen Playlists, lokal in der eigenen Datenbank (löschbar).
"""

from __future__ import annotations

import io
import json
import re
import threading
import time
import uuid
import zipfile
from pathlib import PurePosixPath

from . import playlistfile, store
from . import debuglog as dbg
from .models import Track

MAX_UPLOAD = 300 * 1024 * 1024          # Takeout-Archive können groß sein (Videos bitte abwählen)
MAX_ENTRY = 40 * 1024 * 1024            # einzelne Datei im Archiv
MAX_TOTAL = 400 * 1024 * 1024           # Schutz vor „ZIP-Bomben“
MAX_PLAYLISTS = 500
MAX_TRACKS_TOTAL = 30_000
_KEY = "svc_import:"
IMPORT_SERVICES = ("spotify", "youtube", "apple", "shazam")
_LIKED = "__liked__"


class ExportError(ValueError):
    pass


# ------------------------------------------------------------------ Erkennen
def _t(title: str, artists, album: str | None = None, isrc: str | None = None, ids: dict | None = None,
       ms=None) -> Track | None:
    title = (title or "").strip()
    if isinstance(artists, str):
        artists = playlistfile._split_artists(artists)
    artists = [a.strip() for a in artists or [] if a and a.strip()]
    if not title:
        return None
    return Track(title=title, artists=artists, album=(album or "").strip() or None, isrc=(isrc or "").strip() or None,
                 ids=ids or {}, duration_ms=int(ms) if isinstance(ms, (int, float)) and ms > 0 else None)


def _spotify_id(uri: str | None) -> dict:
    m = re.search(r"spotify:track:([A-Za-z0-9]{22})", uri or "")
    return {"spotify": m[1]} if m else {}


def _spotify_item(it: dict) -> Track | None:
    """Ein Eintrag aus Playlist*.json ({track:{trackName, artistName, albumName, trackUri}}) oder YourLibrary.json
    ({artist, album, track, uri}). Podcasts, Hörbücher und lokale Dateien ohne Titel werden übersprungen."""
    tr = it.get("track") if isinstance(it.get("track"), dict) else None
    if tr:
        return _t(tr.get("trackName") or tr.get("name"), tr.get("artistName") or tr.get("artist"),
                  tr.get("albumName") or tr.get("album"), ids=_spotify_id(tr.get("trackUri") or tr.get("uri")))
    if isinstance(it.get("localTrack"), dict):
        lt = it["localTrack"]
        return _t(lt.get("trackName") or lt.get("name"), lt.get("artistName") or lt.get("artist"), lt.get("albumName"))
    if isinstance(it.get("track"), str):
        return _t(it["track"], it.get("artist"), it.get("album"), ids=_spotify_id(it.get("uri")))
    return None


def _spotify_json(name: str, data: dict | list, out: dict) -> bool:
    base = PurePosixPath(name).name.lower()
    if re.fullmatch(r"playlist\d*\.json", base) and isinstance(data, dict):
        for pl in data.get("playlists") or []:
            tracks = [t for t in (_spotify_item(i) for i in pl.get("items") or [] if isinstance(i, dict)) if t]
            if pl.get("name") and tracks:
                out["playlists"].append({"name": str(pl["name"])[:200], "tracks": tracks})
        return True
    if base == "yourlibrary.json" and isinstance(data, dict):
        out["liked"] += [t for t in (_spotify_item(i) for i in data.get("tracks") or [] if isinstance(i, dict)) if t]
        return True
    return False


_YT_MUSIC_LIB = re.compile(r"(music.*library.*songs|musikbibliothek.*songs|songs.*musikbibliothek|"
                           r"bibliothek.*songs)", re.I)


def _takeout_csv(name: str, text: str, out: dict, pending: list) -> bool:
    """Google Takeout: playlists/<Name>-videos.csv (nur Video-IDs) und „music (library) songs.csv“ (mit Titeln)."""
    p = PurePosixPath(name)
    low = name.lower()
    if "youtube" not in low:
        return False
    rows = playlistfile._rows(text)
    if not rows:
        return True
    # alte Takeout-Form: erst Playlist-Infos, dann eine Leerzeile und die Video-Tabelle
    start = next((i for i, r in enumerate(rows) if playlistfile._col(r, "video") is not None), None)
    if start is None:
        return True                                    # z. B. playlists.csv (nur Übersicht) – nichts zu holen
    rows = rows[start:]
    if _YT_MUSIC_LIB.search(p.stem) or playlistfile._col(rows[0], "title") is not None:
        h = rows[0]
        vi, ti, ali = (playlistfile._col(h, k) for k in ("video", "title", "album"))
        hl = [c.strip().lower() for c in h]
        ai = [i for i, c in enumerate(hl) if "artist" in c or "künstler" in c or "interpret" in c]
        tracks = []
        for r in rows[1:]:
            g = (lambda i: r[i].strip() if i is not None and i < len(r) else "")
            t = _t(g(ti), [g(i) for i in ai], g(ali), ids={"youtube": g(vi)} if g(vi) else {})
            if t:
                tracks.append(t)
        if _YT_MUSIC_LIB.search(p.stem):
            out["liked"] += tracks
        elif tracks:
            out["playlists"].append({"name": _pl_name(p.stem), "tracks": tracks})
        return True
    vi = playlistfile._col(rows[0], "video")
    ids = [r[vi].strip() for r in rows[1:] if vi < len(r) and re.fullmatch(r"[\w-]{11}", r[vi].strip())]
    if ids:
        pending.append({"name": _pl_name(p.stem), "video_ids": ids})
    return True


def _shazam_csv(text: str, out: dict) -> bool:
    """Shazam-Bibliothek (shazam.com › Meine Bibliothek › CSV): erste Zeile „Shazam Library“, dann
    Index,TagTime,Title,Artist,URL,TrackKey. -> Playlist „Meine Shazams“ (neueste zuerst, ohne Doppelte)
    und je Jahr eine eigene Playlist, wenn die Scans über mehrere Jahre gehen."""
    rows = playlistfile._rows(text, ",")
    if not rows:
        return False
    first = [c.strip().lower().lstrip("\ufeff") for c in rows[0]]
    start = next((i for i, r in enumerate(rows[:3])
                  if {"tagtime", "trackkey"} & {c.strip().lower().lstrip("\ufeff") for c in r}), None)
    if start is None and not (first and first[0] == "shazam library"):
        return False
    if start is None:
        return True                                     # nur Kopfzeile, keine Songs
    h = [c.strip().lower().lstrip("\ufeff") for c in rows[start]]
    col = lambda *names: next((h.index(n) for n in names if n in h), None)  # noqa: E731
    ti, ai, wi, ui, ki = col("title"), col("artist"), col("tagtime", "date"), col("url"), col("trackkey")
    if ti is None:
        return False
    from .matching import normalize
    scans = []
    for r in rows[start + 1:]:
        g = (lambda i: r[i].strip() if i is not None and i < len(r) else "")
        t = _t(g(ti), g(ai))
        if t:
            m = re.search(r"/track/(\d+)", g(ui))
            if (key := g(ki) or (m and m[1])):
                t.ids = {"shazam": key}
            scans.append((g(wi), t))
    if scans and all(re.match(r"\d{4}-\d\d", w) for w, _ in scans):
        scans.sort(key=lambda x: x[0], reverse=True)      # ISO-Zeitpunkte: neueste zuerst (sonst Reihenfolge der Datei)
    seen, all_, by_year = set(), [], {}
    for when, t in scans:
        k = (normalize(t.artists[0] if t.artists else ""), normalize(t.title))
        if k in seen:
            continue
        seen.add(k)
        all_.append(t)
        if (y := re.search(r"\b(19|20)\d\d\b", when)):
            by_year.setdefault(y[0], []).append(t)
    if all_:
        out["playlists"].append({"name": "Meine Shazams", "tracks": all_})
        if len(by_year) > 1:
            out["playlists"] += [{"name": f"Shazams {y}", "tracks": by_year[y]} for y in sorted(by_year, reverse=True)]
    out["shazam_scans"] = len(scans)
    return True


def _pl_name(stem: str) -> str:
    return re.sub(r"[-_ ]+(videos|Videos|video)$", "", stem).strip() or stem


def _apple_library(data: bytes, out: dict) -> bool:
    import plistlib
    try:
        pl = plistlib.loads(data)
    except Exception:  # noqa: BLE001
        return False
    if not isinstance(pl, dict) or "Tracks" not in pl:
        return False
    tracks = pl.get("Tracks") or {}

    def tr(tid):
        t = tracks.get(str(tid)) or {}
        return _t(t.get("Name"), t.get("Artist", ""), t.get("Album"), ms=t.get("Total Time"))
    for p in pl.get("Playlists") or []:
        # Systemlisten (Mediathek, Musik, Ordner, intelligente Standardlisten) überspringen
        if p.get("Master") or p.get("Distinguished Kind") or p.get("Folder") or p.get("Visible") is False:
            continue
        items = [t for t in (tr(i.get("Track ID")) for i in p.get("Playlist Items") or []) if t]
        if p.get("Name") and items:
            out["playlists"].append({"name": str(p["Name"])[:200], "tracks": items})
    out["liked"] += [t for t in (tr(k) for k, v in tracks.items() if v.get("Loved") or v.get("Favorited")) if t]
    return True


def _read_zip(data: bytes, out: dict, pending: list) -> None:
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as e:
        raise ExportError("Die ZIP-Datei ist beschädigt oder unvollständig heruntergeladen") from e
    total = 0
    with z:
        for info in z.infolist():
            if info.is_dir() or info.file_size > MAX_ENTRY:
                continue
            low = info.filename.lower()
            if not low.endswith((".json", ".csv", ".xml")):
                continue
            total += info.file_size
            if total > MAX_TOTAL:
                raise ExportError("Das Archiv ist zu groß – bitte beim Export nur Playlists/Bibliothek auswählen")
            raw = z.read(info)
            _read_one(info.filename, raw, out, pending)


def _read_one(name: str, raw: bytes, out: dict, pending: list) -> None:
    low = name.lower()
    if low.endswith(".json"):
        try:
            d = json.loads(playlistfile._text(raw))
        except ValueError:
            return
        if _spotify_json(name, d, out):
            out["service"] = out.get("service") or "spotify"
    elif low.endswith(".csv"):
        text = playlistfile._text(raw)
        if _shazam_csv(text, out):
            out["service"] = out.get("service") or "shazam"
        elif _takeout_csv(name, text, out, pending):
            out["service"] = out.get("service") or "youtube"
    elif low.endswith(".xml"):
        if _apple_library(raw, out):
            out["service"] = out.get("service") or "apple"


def parse(filename: str, data: bytes) -> dict:
    """-> {service, playlists:[{name, tracks}], liked:[Track], pending:[{name, video_ids}]}.
    pending = YouTube-Playlists mit reinen Video-IDs; die Titel holt resolve() per offiziellem oEmbed."""
    if len(data) > MAX_UPLOAD:
        raise ExportError("Datei ist zu groß (max. 300 MB) – bitte beim Export nur Playlists/Bibliothek auswählen")
    out: dict = {"service": None, "playlists": [], "liked": []}
    pending: list = []
    low = (filename or "").lower()
    if data[:4] == b"PK\x03\x04" or low.endswith(".zip"):
        _read_zip(data, out, pending)
    else:
        _read_one(filename or "datei", data, out, pending)
        if not (out["playlists"] or out["liked"] or pending):
            try:      # einzelne Playlist-Datei (Exportify-CSV, .m3u, Apple-Playlist …)
                name, tracks = playlistfile.parse(filename, data)
            except playlistfile.FileError as e:
                raise ExportError(str(e)) from e
            out["playlists"].append({"name": name, "tracks": tracks})
    out["pending"] = pending[:MAX_PLAYLISTS]
    out["playlists"] = out["playlists"][:MAX_PLAYLISTS]
    if not (out["playlists"] or out["liked"] or out["pending"]):
        raise ExportError("In der Datei wurden keine Playlists gefunden. Erwartet: Spotify-Kontodaten (ZIP), "
                          "Google Takeout mit YouTube (ZIP), die Apple-Music-Mediathek (XML) oder die Shazam-Bibliothek (CSV).")
    return out


# ------------------------------------------------------------------ Speichern (nur lokal)
def _ser(t: Track) -> dict:
    d = {"title": t.title, "artists": t.artists}
    for k in ("album", "isrc", "duration_ms"):
        if getattr(t, k):
            d[k] = getattr(t, k)
    if t.ids:
        d["ids"] = t.ids
    return d


def _de(d: dict) -> Track:
    return Track(title=d["title"], artists=d.get("artists") or [], album=d.get("album"), isrc=d.get("isrc"),
                 duration_ms=d.get("duration_ms"), ids=d.get("ids") or {})


def save(sid: str, result: dict, filename: str) -> dict:
    if sid not in IMPORT_SERVICES:
        raise ExportError("Für diesen Dienst gibt es keinen Datei-Import")
    n, lists = 0, []
    for i, pl in enumerate(result["playlists"]):
        tr = pl["tracks"][:max(0, MAX_TRACKS_TOTAL - n)]
        n += len(tr)
        lists.append({"id": f"p{i}", "name": pl["name"], "tracks": [_ser(t) for t in tr]})
    liked = [_ser(t) for t in result["liked"][:max(0, MAX_TRACKS_TOTAL - n)]]
    doc = {"imported": time.time(), "file": (filename or "")[-120:], "playlists": lists, "liked": liked}
    store.meta_set(_KEY + sid, json.dumps(doc, ensure_ascii=False))
    if sid == "shazam":
        refresh_phone_shazams()                        # Shazams vom Handy bleiben neben der CSV erhalten
    return info(sid)


PHONE_LIST = "Shazams vom Handy"


def refresh_phone_shazams() -> int:
    """Shazams, die ein Handy aus der Shazam-App übernommen und hergeschickt hat, als Playlists unter dem Import
    „Shazam“ ablegen: „Shazams vom Handy“ (neueste zuerst, ohne Doppelte) und je Jahr eine, wenn es mehrere sind.
    Playlists aus einer Shazam-CSV bleiben unangetastet. -> Anzahl Songs."""
    from .matching import normalize
    recs = store.recognitions_by_source("shazam-app")
    seen: dict = {}
    all_, by_year = [], {}
    for r in recs:                                     # neueste zuerst
        t = r["track"]
        k = (normalize((t.get("artists") or [""])[0]), normalize(t.get("title") or ""))
        key = (r.get("extra") or {}).get("shazam_key")
        if not t.get("title"):
            continue
        if k in seen:                                  # doppelt: Shazam-Nummer trotzdem übernehmen
            if key and "shazam" not in seen[k].setdefault("ids", {}):
                seen[k]["ids"]["shazam"] = str(key)
            continue
        d = _ser(_t(t["title"], t.get("artists") or [], t.get("album"), t.get("isrc"),
                    {**(t.get("ids") or {}), **({"shazam": str(key)} if key else {})}) or Track(title=t["title"]))
        seen[k] = d
        all_.append(d)
        by_year.setdefault(time.strftime("%Y", time.localtime(r["ts"])), []).append(d)
    doc = _doc("shazam") or {"imported": time.time(), "file": "", "playlists": [], "liked": []}
    keep = [p for p in doc["playlists"] if not p.get("phone")]
    mine = []
    if all_:
        mine.append({"id": "h0", "name": PHONE_LIST, "tracks": all_[:MAX_TRACKS_TOTAL], "phone": True})
        if len(by_year) > 1:
            mine += [{"id": f"h{y}", "name": f"{PHONE_LIST} {y}", "tracks": by_year[y], "phone": True} for y in sorted(by_year, reverse=True)]
    if not keep and not mine and not doc["liked"]:
        if _doc("shazam"):
            remove("shazam")
        return 0
    doc["playlists"] = mine + keep
    if not doc.get("file"):
        doc["file"] = "vom Handy (Shazam-App)"
    doc["imported"] = time.time()
    store.meta_set(_KEY + "shazam", json.dumps(doc, ensure_ascii=False))
    return len(all_)


def _doc(sid: str) -> dict | None:
    raw = store.meta_get(_KEY + sid)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except ValueError:
        return None


def info(sid: str) -> dict | None:
    d = _doc(sid)
    if not d:
        return None
    return {"imported": d["imported"], "file": d.get("file"), "playlists": len(d["playlists"]),
            "liked": len(d["liked"]), "songs": sum(len(p["tracks"]) for p in d["playlists"]) + len(d["liked"])}


def remove(sid: str) -> None:
    store.meta_set(_KEY + sid, "")


def playlists(sid: str) -> list[dict]:
    d = _doc(sid) or {"playlists": [], "liked": []}
    out = [{"id": _LIKED, "name": "Lieblingssongs", "count": len(d["liked"]), "own": True}] if d["liked"] else []
    return out + [{"id": p["id"], "name": p["name"], "count": len(p["tracks"]), "own": True} for p in d["playlists"]]


def load(sid: str, pid: str) -> tuple[str, list[Track]]:
    d = _doc(sid)
    if not d:
        raise ExportError("Kein Import vorhanden")
    if pid == _LIKED:
        return "Lieblingssongs", [_de(x) for x in d["liked"]]
    for p in d["playlists"]:
        if p["id"] == pid:
            return p["name"], [_de(x) for x in p["tracks"]]
    raise ExportError("Playlist nicht im Import gefunden")


# ------------------------------------------------------------------ Import-Aufträge (mit Fortschritt)
_jobs: dict[str, dict] = {}


def _resolve(job: dict, pending: list[dict]) -> list[dict]:
    """YouTube-Takeout: Titel zu Video-IDs über das offizielle oEmbed von YouTube (kein Konto, kein Key)."""
    from .linkimport import LinkError, _youtube
    out, cache = [], {}
    job["total"] = sum(len(p["video_ids"]) for p in pending)
    for pl in pending:
        tracks = []
        for vid in pl["video_ids"][:playlistfile.MAX_TRACKS]:
            if job["cancel"]:
                raise InterruptedError
            if vid not in cache:
                try:
                    cache[vid] = _youtube("track", vid)[1][0]
                except (LinkError, IndexError):
                    cache[vid] = None                    # privat oder gelöscht
                except Exception as e:  # noqa: BLE001
                    dbg.error("import", "YouTube-Titel nicht abrufbar", e)
                    cache[vid] = None
                time.sleep(0.05)
            job["done"] += 1
            if cache[vid]:
                tracks.append(cache[vid])
        if tracks:
            out.append({"name": pl["name"], "tracks": tracks})
    return out


def _run(job: dict, sid: str, filename: str, data: bytes) -> None:
    try:
        job["state"] = "reading"
        res = parse(filename, data)
        del data
        found = res.get("service")
        if found and found != sid:
            names = {"spotify": "Spotify", "youtube": "YouTube (Google Takeout)", "apple": "Apple Music", "shazam": "Shazam"}
            raise ExportError(f"Das ist ein Export von {names.get(found, found)} – bitte dort importieren")
        if res["pending"]:
            job["state"] = "titles"
            res["playlists"] += _resolve(job, res["pending"])
        job["result"] = save(sid, res, filename)
        job["state"] = "done"
    except InterruptedError:
        job["state"] = "cancelled"
    except ExportError as e:
        job.update(state="error", error=str(e))
    except Exception as e:  # noqa: BLE001
        dbg.error("import", "Datenexport konnte nicht gelesen werden", e)
        job.update(state="error", error=f"Datei konnte nicht gelesen werden: {e}")


def start(sid: str, filename: str, data: bytes) -> str:
    if sid not in IMPORT_SERVICES:
        raise ExportError("Für diesen Dienst gibt es keinen Datei-Import")
    jid = uuid.uuid4().hex[:10]
    _jobs[jid] = {"id": jid, "service": sid, "state": "queued", "done": 0, "total": 0, "cancel": False,
                  "started": time.time()}
    threading.Thread(target=_run, args=(_jobs[jid], sid, filename, data), daemon=True).start()
    for k in [k for k, j in _jobs.items() if time.time() - j["started"] > 3600]:
        _jobs.pop(k, None)
    return jid


def job(jid: str) -> dict | None:
    j = _jobs.get(jid)
    return {k: v for k, v in j.items() if k != "cancel"} if j else None


def cancel(jid: str) -> None:
    if jid in _jobs:
        _jobs[jid]["cancel"] = True

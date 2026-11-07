"""Playlists/Likes übertragen – zwischen SH-Tunebridge (lokal) und angebundenen Diensten.

Sparsam mit API-Aufrufen:
  * Treffer werden pro Dienst gespeichert (Cache „match:<dienst>“) – ein zweiter Lauf
    oder dieselben Songs in einer anderen Playlist kosten keinen Aufruf mehr.
  * ISRC zuerst (exakt, 1 Aufruf), Textsuche nur als Notlösung.
  * Hinzufügen in Paketen (100 Songs pro Aufruf).
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import asdict

from . import store
from .models import Track
from .providers import get_provider

_jobs: dict[str, dict] = {}


def sources() -> list[dict]:
    """Alles, was als Quelle wählbar ist."""
    out = [{"service": "local", "id": p.name, "name": p.name, "count": len(p.tracks)} for p in store.local_playlists()]
    return out


def load(service: str, pid: str) -> list[Track]:
    if service == "local":
        return next((p.tracks for p in [*store.local_playlists(), *store.exported_playlists()] if p.name == pid), [])
    if service == "link":               # pid = "<auftrag>" oder "<auftrag>:1,4,7" (Auswahl)
        from . import linkimport
        jid, _, sel = pid.partition(":")
        return linkimport.tracks(jid, [int(x) for x in sel.split(",") if x.isdigit()] if sel else None)
    prov = get_provider(service)
    return prov.liked() if pid == "__liked__" else prov.playlist_tracks(pid)


def _match(prov, t: Track) -> Track | None:
    ns, key = f"match:{prov.name}", store.track_key(t)
    hit = store.cache_get(ns, key)
    if hit is not None:
        return Track(**hit) if hit else None
    m = prov.find(t)
    store.cache_set(ns, key, asdict(m) if m else {})
    return m


def _run(job: dict) -> None:
    try:
        job["state"] = "loading"
        tracks = load(job["src"], job["src_id"])
        job["total"] = len(tracks)
        found, missing = [], []
        if job["dst"] == "local":
            job["state"] = "adding"
            for i, t in enumerate(tracks):
                store.add_to_playlist(job["name"], t)
                job["done"] = i + 1
            found = tracks
        else:
            prov = get_provider(job["dst"])
            job["state"] = "matching"
            for i, t in enumerate(tracks):
                if job["cancel"]:
                    raise InterruptedError
                if t.ids.get(prov.name):
                    m = t
                else:
                    m = _match(prov, t)
                (found.append(m) if m else missing.append(t))
                job["done"] = i + 1
            job["state"] = "adding"
            if job["like"]:
                prov.like(found)
            else:
                pid = prov.create_playlist(job["name"])
                prov.add_to_playlist(pid, found)
                job["url"] = getattr(prov, "playlist_url", lambda x: None)(pid)
        job.update(state="done", found=len(found),
                   missing=[{"title": t.title, "artist": ", ".join(t.artists)} for t in missing])
        from . import debuglog as dbg
        (dbg.problem if missing else dbg.event)("übertragen", f"Fertig: {len(found)} gefunden, {len(missing)} fehlen",
                                                fehlend=[f"{', '.join(t.artists)} – {t.title}" for t in missing][:50])
    except InterruptedError:
        job["state"] = "cancelled"
    except Exception as e:
        from . import debuglog as dbg
        dbg.error("übertragen", "Übertragung abgebrochen", e)
        job.update(state="error", error=str(e))
    job["finished"] = time.time()


def start(src: str, src_id: str, dst: str, name: str, like: bool = False) -> str:
    jid = uuid.uuid4().hex[:10]
    _jobs[jid] = {"id": jid, "src": src, "src_id": src_id, "dst": dst, "name": name, "like": like,
                  "state": "queued", "done": 0, "total": 0, "cancel": False, "started": time.time()}
    threading.Thread(target=_run, args=(_jobs[jid],), daemon=True).start()
    return jid


def job(jid: str) -> dict | None:
    j = _jobs.get(jid)
    return {k: v for k, v in j.items() if k != "cancel"} if j else None


def cancel(jid: str) -> None:
    if jid in _jobs:
        _jobs[jid]["cancel"] = True

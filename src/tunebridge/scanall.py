"""„Alles einlesen“: alle verbundenen Dienste auf einmal – Lieblingssongs, eigene (und auf Wunsch gefolgte) Playlists.

Läuft als Teil eines Sortier-Auftrags (services._run_inner, Dienst „__all__“), damit danach dieselbe Vorschau
kommt wie bei einer einzelnen Playlist. Es wird nur über die offiziellen Schnittstellen und mit dem eigenen Login
gelesen. Grenzen und Rücksicht auf die Dienste:

* Pausen, um die ein Dienst bittet (HTTP 429 / Retry-After), werden abgewartet (ratelimit.patient im Auftrag).
* Zwischen zwei Playlists eine kleine Pause (PAUSE_S) – kein Dauerfeuer auf die Schnittstellen.
* Höchstens MAX_PLAYLISTS Playlists je Dienst und MAX_TRACKS verschiedene Songs insgesamt.
* Fehler bei einer Playlist (gelöscht, privat, Kontingent aufgebraucht …) überspringen die Playlist, nicht den Lauf.

Spec (aus der Adresse): "spotify,tidal|liked,own,followed"
"""
from __future__ import annotations

import time

from .models import Track

MAX_PLAYLISTS = 300
MAX_TRACKS = 80000
PAUSE_S = 0.4
KINDS = ("liked", "own", "followed")
NAMES = {"spotify": "Spotify", "tidal": "TIDAL", "soundcloud": "SoundCloud", "youtube": "YouTube",
         "deezer": "Deezer", "lastfm": "Last.fm", "apple": "Apple Music"}


def parse(spec: str) -> tuple[list[str], set[str]]:
    svc, _, kinds = (spec or "").partition("|")
    sids = [s for s in (x.strip() for x in svc.split(",")) if s and not s.startswith("friend-") and s != "__all__"]
    ks = {k for k in kinds.split(",") if k in KINDS} or {"liked", "own"}
    return sids, ks


def _key(t: Track) -> str:
    from .matching import hard_version, normalize
    from .versions import main_artist
    if t.isrc:      # ISRC + Fassung: ein Remix mit falscher Original-ISRC bleibt ein eigener Song
        kind, rest = hard_version(t.title)
        return f"{t.isrc.upper()}|{','.join(sorted(kind))}|{rest}"
    return f"{normalize(main_artist(t.artists[0])) if t.artists else ''}|{normalize(t.title)}"


def collect(spec: str, job: dict) -> tuple[str, list[Track]]:
    """Alle gewählten Listen laden und Doppelte zusammenführen. Fortschritt in job["scan"]."""
    from . import services
    from .ratelimit import LimitReached
    sids, kinds = parse(spec)
    if not sids:
        raise services.ServiceError("Kein Dienst ausgewählt")
    scan = job.setdefault("scan", {"dienst": None, "playlist": None, "i": 0, "n": 0, "songs": 0, "lists": 0,
                                   "doppelt": 0, "fehler": [], "gekappt": False})
    # 1) Playlist-Listen aller Dienste holen
    todo: list[tuple[str, dict]] = []
    for sid in sids:
        if job.get("cancel"):
            raise InterruptedError
        scan.update(dienst=NAMES.get(sid, sid), playlist="Playlist-Liste")
        try:
            lists = services.playlists(sid)
        except Exception as e:  # noqa: BLE001 – ein Dienst ohne Liste hält die anderen nicht auf
            scan["fehler"].append({"dienst": NAMES.get(sid, sid), "playlist": "–", "grund": str(e)[:200]})
            continue
        chosen = [p for p in lists if (p["id"] == "__liked__" and "liked" in kinds)
                  or (p["id"] != "__liked__" and (("own" in kinds and p.get("own", True))
                                                  or ("followed" in kinds and not p.get("own", True))))]
        if len(chosen) > MAX_PLAYLISTS:
            scan["gekappt"] = True
            chosen = chosen[:MAX_PLAYLISTS]
        todo += [(sid, p) for p in chosen]
    scan["n"] = len(todo)
    # 2) Songs laden, Doppelte zusammenführen
    seen: dict[str, Track] = {}
    for i, (sid, p) in enumerate(todo):
        if job.get("cancel"):
            raise InterruptedError
        scan.update(i=i + 1, dienst=NAMES.get(sid, sid), playlist=p.get("name") or p["id"])
        try:
            _, tracks = services.load(sid, p["id"])
        except LimitReached as e:
            scan["fehler"].append({"dienst": NAMES.get(sid, sid), "playlist": p.get("name"), "grund": str(e)[:200]})
            continue
        except Exception as e:  # noqa: BLE001
            scan["fehler"].append({"dienst": NAMES.get(sid, sid), "playlist": p.get("name"), "grund": str(e)[:200]})
            continue
        scan["lists"] += 1
        for t in tracks:
            if not t.title or not t.artists:
                continue
            k = _key(t)
            if k in seen:
                scan["doppelt"] += 1
                old = seen[k]
                old.ids = {**t.ids, **old.ids}           # IDs aller Dienste sammeln (hilft beim Übertragen)
                continue
            if len(seen) >= MAX_TRACKS:
                scan["gekappt"] = True
                continue
            seen[k] = t
        scan["songs"] = len(seen)
        time.sleep(PAUSE_S)
    names = ", ".join(NAMES.get(s, s) for s in sids)
    return f"Alles aus {names}", list(seen.values())

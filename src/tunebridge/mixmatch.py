"""„Passt dazu“: Songs aus deiner eigenen Bibliothek, die sich gut mit einem Song mixen lassen.

Passend = Tempo höchstens MAX_TEMPO % entfernt (halbes/doppeltes Tempo zählt mit) und Tonart gleich oder
Camelot-Nachbar. Für den gesuchten Song wird Tempo/Tonart notfalls aus der Hörprobe gemessen (1 Abfrage);
für die Bibliothek werden NUR schon gemessene Werte benutzt (Song-Speicher) – keine Abfrage-Flut.
Noch nicht gemessene Songs misst der Set-Planer oder das Sortieren mit.
"""

from __future__ import annotations

from . import store
from .audiofeat import camelot_distance
from .models import Track
from .setplan import tempo_jump

MAX_TEMPO = 6.0
MAX_RESULTS = 25


def _library() -> list[tuple[Track, list[str]]]:
    seen: dict[str, tuple[Track, list[str]]] = {}
    for p in store.local_playlists():
        for t in p.tracks:
            k = store.track_key(t)
            if k in seen:
                seen[k][1].append(p.name)
            else:
                seen[k] = (t, [p.name])
    return list(seen.values())


def find(t: Track, deezer_bpm: float | None = None) -> dict:
    from . import audiofeat
    f = audiofeat.features(t, deezer_bpm=deezer_bpm)
    if not f or not (f.get("bpm") or f.get("camelot")):
        return {"song": None, "matches": [], "unmeasured": 0, "total": 0,
                "error": "Für diesen Song gibt es keine Hörprobe – Tempo und Tonart unbekannt"}
    me = store.track_key(t)
    out, unmeasured, lib = [], 0, _library()
    for cand, pls in lib:
        k = store.track_key(cand)
        if k == me:
            continue
        cf = store.cache_get("audiofeat", k)
        if not cf:
            unmeasured += 1
            continue
        tj = tempo_jump(f.get("bpm"), cf.get("bpm"))
        kd = camelot_distance(f.get("camelot"), cf.get("camelot")) if f.get("camelot") and cf.get("camelot") else None
        if tj is None or tj > MAX_TEMPO or (kd is not None and kd > 1):
            continue
        score = tj + (kd if kd is not None else 1.5) * 2
        out.append({"title": cand.title, "artists": cand.artists, "cover": cand.cover, "isrc": cand.isrc, "ids": cand.ids,
                    "preview_url": cand.preview_url, "genre": cand.genre, "subgenre": cand.subgenre, "key": k,
                    "bpm": cf.get("bpm"), "camelot": cf.get("camelot"), "tempo": round(tj, 1), "key_d": kd,
                    "playlists": pls[:3], "score": round(score, 2)})
    out.sort(key=lambda x: x["score"])
    return {"song": {"bpm": f.get("bpm"), "camelot": f.get("camelot"), "key": f.get("key")},
            "matches": out[:MAX_RESULTS], "found": len(out), "unmeasured": unmeasured, "total": len(lib)}

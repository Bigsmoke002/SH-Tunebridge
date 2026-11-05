"""Set-Planer: aus einer Playlist eine DJ-taugliche Reihenfolge bauen.

1. Für jeden Song Tempo, Tonart (Camelot) und Energie holen – aus dem Speicher oder aus der offiziellen
   30-s-Hörprobe (wie beim Sortieren; bekannte Songs kosten keine Abfrage).
2. Reihenfolge: Schritt für Schritt der beste nächste Song – kleiner Tempo-Sprung (halbes/doppeltes Tempo zählt
   als passend), harmonische Tonart (Camelot-Nachbarn) und nah an der gewünschten Energie-Kurve.
3. Export als M3U8 / CSV / Tracklist-Text in den Download-Ordner, oder als neue lokale Playlist in dieser Reihenfolge.
Musikdateien gibt es keine – die Exporte enthalten Titel, Künstler, Tempo, Tonart und Links.
"""

from __future__ import annotations

import csv
import io
import math
import re
import threading
import time
import uuid

from . import debuglog as dbg
from . import store
from .audiofeat import camelot_distance
from .models import Track
from .sorter import energy

MAX_TRACKS = 300

CURVES = {
    "aufbau": ("Aufbauen", "ruhig starten, immer mehr Energie"),
    "peak": ("Peak in der Mitte", "aufbauen, Höhepunkt bei etwa 70 %, sanft ausklingen"),
    "gleich": ("Gleichmäßig", "Energie egal – nur Tempo und Tonart"),
    "runter": ("Runterfahren", "mit Energie starten, ruhig enden (Afterhour, Warm-down)"),
}


def target(curve: str, x: float) -> float | None:
    """Gewünschte Energie (0..1) an Position x (0 = Anfang, 1 = Ende)."""
    if curve == "aufbau":
        return 0.3 + 0.6 * x
    if curve == "runter":
        return 0.9 - 0.6 * x
    if curve == "peak":
        return 0.35 + 0.6 * math.sin(math.pi / 2 * x / 0.7) if x <= 0.7 else 0.95 - 0.45 * (x - 0.7) / 0.3
    return None


def scaled_target(items: list[dict], curve: str, x: float) -> float | None:
    """Ziel-Kurve auf die Energie-Spanne DIESER Playlist strecken – sonst sind die Kurven bei einer Playlist mit
    Energie 35–70 % kaum unterscheidbar (die Kurven selbst laufen von 30 bis 95 %)."""
    t = target(curve, x)
    if t is None or not items:
        return t
    es = [energy(it) for it in items]
    lo, hi = min(es), max(es)
    if hi - lo < 0.05:
        return t
    return lo + (t - 0.3) / 0.65 * (hi - lo)


def tempo_jump(a: float | None, b: float | None) -> float | None:
    """Tempo-Sprung in % – halbes/doppeltes Tempo gilt als gleich (70 ↔ 140 BPM)."""
    if not a or not b:
        return None
    return min(abs(a - c) / a * 100 for c in (b, b * 2, b / 2))


def key_label(d: int, a: str | None, b: str | None) -> str:
    if not a or not b:
        return "Tonart unbekannt"
    return {0: "gleiche Tonart", 1: "harmonisch"}.get(d, "Tonart 2 Schritte entfernt" if d == 2 else "Tonart-Bruch")


def _step(a: dict, b: dict) -> float:
    tj = tempo_jump(a.get("bpm"), b.get("bpm"))
    return (min(tj, 25) if tj is not None else 5.0) + 1.6 * camelot_distance(a.get("camelot"), b.get("camelot"))


def _fit(it: dict, want: float | None) -> float:
    return 14 * abs(energy(it) - want) if want is not None else 0.0


def total_cost(items: list[dict], idx: list[int], curve: str) -> float:
    n = len(idx)
    c = sum(_step(items[idx[k - 1]], items[idx[k]]) for k in range(1, n))
    return c + sum(_fit(items[i], scaled_target(items, curve, k / max(1, n - 1))) for k, i in enumerate(idx))


def _improve(items: list[dict], idx: list[int], curve: str, passes: int = 4) -> list[int]:
    """Nachbessern durch Tauschen von Paaren: die Schritt-für-Schritt-Auswahl lässt sonst Ausreißer fürs Ende übrig."""
    n = len(idx)
    if n < 4 or n > 400:
        return idx
    want = [scaled_target(items, curve, k / (n - 1)) for k in range(n)]

    def local(o, ks):
        c = 0.0
        for k in ks:
            c += _fit(items[o[k]], want[k])
            if k > 0:
                c += _step(items[o[k - 1]], items[o[k]])
            if k < n - 1 and k + 1 not in ks:
                c += _step(items[o[k]], items[o[k + 1]])
        return c
    o = list(idx)
    for _ in range(passes):
        better = False
        for a in range(n - 1):
            for b in range(a + 1, n):
                ks = sorted({a, b})
                before = local(o, set(ks))
                o[a], o[b] = o[b], o[a]
                if local(o, set(ks)) < before - 1e-9:
                    better = True
                else:
                    o[a], o[b] = o[b], o[a]
        if not better:
            break
    return o


def order(items: list[dict], curve: str = "peak") -> list[int]:
    n = len(items)
    if n <= 1:
        return list(range(n))
    rest = set(range(n))
    t0 = scaled_target(items, curve, 0)
    start = min(rest, key=lambda i: (abs(energy(items[i]) - t0) if t0 is not None else energy(items[i]),
                                     items[i].get("bpm") or 999))
    out = [start]
    rest.discard(start)
    while rest:
        a = items[out[-1]]
        want = scaled_target(items, curve, len(out) / (n - 1))

        def cost(j):
            b = items[j]
            return _step(a, b) + (_fit(b, want) if want is not None else abs(energy(b) - energy(a)) * 4)
        nxt = min(rest, key=cost)
        out.append(nxt)
        rest.discard(nxt)
    return _improve(items, out, curve, passes=4 if n <= 150 else 2)


def describe(items: list[dict], idx: list[int], curve: str) -> dict:
    """Übergänge + Kurven für die Anzeige."""
    steps, n = [], len(idx)
    for k, i in enumerate(idx):
        it = items[i]
        step = {"i": i, "energy": round(energy(it), 2), "target": None if (t := scaled_target(items, curve, k / max(1, n - 1))) is None else round(t, 2)}
        if k:
            p = items[idx[k - 1]]
            d = camelot_distance(p.get("camelot"), it.get("camelot"))
            tj = tempo_jump(p.get("bpm"), it.get("bpm"))
            step.update(key=key_label(d, p.get("camelot"), it.get("camelot")), key_d=d if p.get("camelot") and it.get("camelot") else None,
                        tempo=round(tj, 1) if tj is not None else None)
        steps.append(step)
    known = [s for s in steps[1:] if s.get("key_d") is not None]
    return {"order": idx, "steps": steps, "curve": curve,
            "harmonisch": sum(1 for s in known if s["key_d"] <= 1), "bekannt": len(known),
            "minuten": round(sum(items[i].get("duration_ms") or 0 for i in idx) / 60000)}


# ------------------------------------------------------------------ Aufträge
_jobs: dict[str, dict] = {}


def _run(job: dict) -> None:
    from . import audiofeat, ratelimit
    try:
        with ratelimit.patient():
            for k, it in enumerate(job["items"]):
                if job["cancel"]:
                    job["state"] = "cancelled"
                    return
                t = Track(title=it["title"], artists=it["artists"], isrc=it.get("isrc"), ids=it.get("ids") or {},
                          preview_url=it.get("preview_url"), genre=it.get("genre"))
                try:
                    f = audiofeat.features(t)
                except Exception as e:  # noqa: BLE001
                    dbg.error("setplan", "Tempo/Tonart nicht ermittelt", e)
                    f = None
                if f:
                    it.update(bpm=f.get("bpm"), camelot=f.get("camelot"), key=f.get("key"), energy=f.get("energy"))
                job["done"] = k + 1
        job["state"] = "done"
    except Exception as e:  # noqa: BLE001
        dbg.error("setplan", "Set-Planer abgebrochen", e)
        job.update(state="error", error=str(e))


def start(playlist: str) -> str:
    pl = next((p for p in store.local_playlists() if p.name == playlist), None)
    if not pl or not pl.tracks:
        raise ValueError("Playlist leer oder nicht gefunden")
    items = [{"title": t.title, "artists": t.artists, "artist": t.artist, "isrc": t.isrc, "ids": t.ids, "cover": t.cover,
              "preview_url": t.preview_url, "genre": t.genre, "subgenre": t.subgenre, "duration_ms": t.duration_ms,
              "album": t.album, "niche": t.niche}
             for t in pl.tracks[:MAX_TRACKS]]
    jid = uuid.uuid4().hex[:10]
    _jobs[jid] = {"id": jid, "playlist": playlist, "state": "analysing", "done": 0, "total": len(items),
                  "cut": max(0, len(pl.tracks) - MAX_TRACKS), "items": items, "cancel": False, "started": time.time()}
    threading.Thread(target=_run, args=(_jobs[jid],), daemon=True).start()
    for k in [k for k, j in _jobs.items() if time.time() - j["started"] > 6 * 3600]:
        _jobs.pop(k, None)
    return jid


def job(jid: str) -> dict:
    j = _jobs.get(jid)
    if not j:
        raise ValueError("Auftrag nicht gefunden (abgelaufen?) – bitte neu starten")
    return j


def _checked_order(j: dict, idx: list[int]) -> list[int]:
    if sorted(idx) != list(range(len(j["items"]))):
        raise ValueError("Reihenfolge passt nicht zur Playlist")
    return idx


def _link(it: dict) -> str:
    ids = it.get("ids") or {}
    if ids.get("deezer"):
        return f"https://www.deezer.com/track/{ids['deezer']}"
    if ids.get("spotify"):
        return f"https://open.spotify.com/track/{ids['spotify']}"
    if ids.get("youtube"):
        return f"https://www.youtube.com/watch?v={ids['youtube']}"
    return ""


def render(j: dict, idx: list[int], fmt: str) -> str:
    items = [j["items"][i] for i in _checked_order(j, idx)]
    if fmt == "m3u8":
        lines = ["#EXTM3U", f"#PLAYLIST:{j['playlist']} (Set)"]
        for it in items:
            secs = round((it.get("duration_ms") or 0) / 1000) or -1
            extra = " ".join(x for x in (f"{round(it['bpm'])} BPM" if it.get("bpm") else "", it.get("camelot") or "") if x)
            lines.append(f"#EXTINF:{secs},{it['artist']} - {it['title']}{f' [{extra}]' if extra else ''}")
            lines.append(_link(it) or f"# {it['artist']} - {it['title']}")
        return "\n".join(lines) + "\n"
    if fmt == "csv":
        buf = io.StringIO()
        w = csv.writer(buf, delimiter=";")
        w.writerow(["Nr", "Künstler", "Titel", "BPM", "Tonart", "Camelot", "Energie", "Genre", "Link"])
        for n, it in enumerate(items, 1):
            w.writerow([n, it["artist"], it["title"], round(it["bpm"]) if it.get("bpm") else "", it.get("key") or "",
                        it.get("camelot") or "", round(energy(it) * 100), it.get("subgenre") or it.get("genre") or "", _link(it)])
        return buf.getvalue()
    if fmt == "txt":
        return "\n".join(f"{n:02d}. {it['artist']} – {it['title']}"
                         f"{' (' + ', '.join(x for x in (f'{round(it['bpm'])} BPM' if it.get('bpm') else '', it.get('camelot') or '') if x) + ')' if it.get('bpm') or it.get('camelot') else ''}"
                         for n, it in enumerate(items, 1)) + "\n"
    raise ValueError("Unbekanntes Format")


def export(jid: str, idx: list[int], fmt: str) -> dict:
    from .osutil import downloads_dir
    j = job(jid)
    text = render(j, idx, fmt)
    safe = re.sub(r"[^\w\- ]+", "", j["playlist"]).strip()[:60] or "Set"
    out = downloads_dir() / f"{safe} - Set {time.strftime('%Y%m%d-%H%M')}.{fmt}"
    out.write_text(text, encoding="utf-8")
    return {"path": str(out), "name": out.name, "folder": str(out.parent)}


def save(jid: str, idx: list[int], name: str) -> dict:
    j = job(jid)
    name = (name or "").strip()[:120]
    if not name:
        raise ValueError("Bitte einen Namen eingeben")
    if any(p.name == name for p in store.local_playlists()):
        raise ValueError(f"Eine Playlist „{name}“ gibt es schon – bitte anderen Namen wählen")
    for i in _checked_order(j, idx):
        it = j["items"][i]
        store.add_to_playlist(name, Track(title=it["title"], artists=it["artists"], album=it.get("album"), isrc=it.get("isrc"),
                                          ids=it.get("ids") or {}, cover=it.get("cover"), preview_url=it.get("preview_url"),
                                          genre=it.get("genre"), subgenre=it.get("subgenre"), niche=it.get("niche"),
                                          duration_ms=it.get("duration_ms")))
    return {"name": name, "count": len(idx)}

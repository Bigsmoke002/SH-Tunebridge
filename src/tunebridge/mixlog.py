"""Mix-Tracklists aus dem Erkennungs-Verlauf.

Eine „Sitzung“ = Erkennungen mit weniger als GAP Minuten Abstand (z. B. ein DJ-Mix im Dauer-Modus).
Wird derselbe Song mehrmals hintereinander erkannt (Dauer-Modus), zählt er einmal – mit dem ersten Zeitpunkt.
Zeitstempel = Zeitpunkt der Erkennung, gerechnet ab dem ersten Song (00:00). Alles lokal.
"""

from __future__ import annotations

import json
from datetime import datetime

from . import store
from .matching import normalize

GAP = 15 * 60
MAX_ROWS = 5000
WEEKDAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]


def _rows() -> list[dict]:
    with store._conn() as c:
        rows = c.execute("SELECT id, ts, track, extra FROM recognitions ORDER BY ts DESC LIMIT ?", (MAX_ROWS,)).fetchall()
    out = []
    for r in reversed(rows):
        t = json.loads(r["track"])
        out.append({"id": r["id"], "ts": r["ts"], "title": t.get("title") or "", "artists": t.get("artists") or [],
                    "genre": t.get("genre"), "subgenre": t.get("subgenre"), "isrc": t.get("isrc"), "ids": t.get("ids") or {},
                    "cover": t.get("cover") or json.loads(r["extra"] or "{}").get("cover"), "preview_url": t.get("preview_url")})
    return out


def _same(a: dict, b: dict) -> bool:
    if a.get("isrc") and a.get("isrc") == b.get("isrc"):
        return True
    return (normalize(a["title"]), normalize((a["artists"] or [""])[0])) == (normalize(b["title"]), normalize((b["artists"] or [""])[0]))


def sessions(rows: list[dict] | None = None, gap: int = GAP) -> list[dict]:
    rows = _rows() if rows is None else rows
    groups: list[list[dict]] = []
    for r in rows:
        if groups and r["ts"] - groups[-1][-1]["ts"] < gap:
            groups[-1].append(r)
        else:
            groups.append([r])
    out = []
    for g in groups:
        songs: list[dict] = []
        for r in g:
            if not (songs and _same(songs[-1], r)):
                songs.append(r)
        start = songs[0]["ts"]
        for s in songs:
            s["offset"] = round(s["ts"] - start)
        out.append({"id": int(start), "start": start, "end": g[-1]["ts"], "count": len(songs), "songs": songs,
                    "label": label(start, g[-1]["ts"])})
    return list(reversed(out))          # neueste zuerst


def label(start: float, end: float) -> str:
    a, b = datetime.fromtimestamp(start), datetime.fromtimestamp(end)
    return f"{WEEKDAYS[a.weekday()]} {a.day}.{a.month}.{a.year}, {a:%H:%M}–{b:%H:%M}"


def _clock(sec: int) -> str:
    h, m, s = sec // 3600, sec % 3600 // 60, sec % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def tracklist(session: dict, fmt: str = "offset", genre: bool = False) -> str:
    """fmt: offset (00:00 ab Start) · clock (Uhrzeit) · plain (nummeriert, ohne Zeit)."""
    lines = []
    for n, s in enumerate(session["songs"], 1):
        name = f"{', '.join(s['artists'])} – {s['title']}"
        if genre and (s.get("subgenre") or s.get("genre")):
            name += f" [{s.get('subgenre') or s.get('genre')}]"
        if fmt == "clock":
            lines.append(f"{datetime.fromtimestamp(s['ts']):%H:%M} {name}")
        elif fmt == "plain":
            lines.append(f"{n:02d}. {name}")
        else:
            lines.append(f"{_clock(s['offset'])} {name}")
    return "\n".join(lines) + "\n"


def find(sid: int) -> dict | None:
    return next((s for s in sessions() if s["id"] == sid), None)


def overview(limit: int = 50) -> list[dict]:
    return [{k: v for k, v in s.items() if k != "songs"} | {"first": [f"{', '.join(x['artists'])} – {x['title']}" for x in s["songs"][:3]]}
            for s in sessions()[:limit] if s["count"] >= 2]


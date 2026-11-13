#!/usr/bin/env python3
"""SH-Tunebridge-Symbole (Stil „Glyph“): EINE Quelle für PC (app.js) und Handy (Icons.kt).

Eigene Zeichnungen im 24er-Raster – keine fremden Icon-Sätze, keine Logos von Diensten.
Jedes Symbol besteht aus
  f: gefüllten Pfaden (gerade/ungerade-Regel: innere Teilpfade stanzen Löcher aus) und
  s: Linien (Strichstärke STROKE, runde Enden).
Aufruf:  python scripts/gen-icons.py          -> schreibt beide Dateien neu
         python scripts/gen-icons.py --check  -> Fehler, wenn eine Datei nicht aktuell ist (Test/CI)
"""
from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "src/tunebridge/web/static/app.js"
KT = ROOT / "android/app/src/main/java/de/bs002/tunebridge/ui/theme/Icons.kt"
STROKE = 2.2


def n(x: float) -> str:
    s = f"{x:.2f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def circ(cx, cy, r):
    return f"M{n(cx - r)} {n(cy)}a{n(r)} {n(r)} 0 1 0 {n(2 * r)} 0a{n(r)} {n(r)} 0 1 0 {n(-2 * r)} 0Z"


def rr(x, y, w, h, r):
    r = min(r, w / 2, h / 2)
    return (f"M{n(x + r)} {n(y)}h{n(w - 2 * r)}a{n(r)} {n(r)} 0 0 1 {n(r)} {n(r)}v{n(h - 2 * r)}"
            f"a{n(r)} {n(r)} 0 0 1 {n(-r)} {n(r)}h{n(-(w - 2 * r))}a{n(r)} {n(r)} 0 0 1 {n(-r)} {n(-r)}"
            f"v{n(-(h - 2 * r))}a{n(r)} {n(r)} 0 0 1 {n(r)} {n(-r)}Z")


def cap(x1, y1, x2, y2, w):
    """Ausstanz-Strich mit runden Enden (als Umriss, damit er in einen gefüllten Pfad passt)."""
    a, r = math.atan2(y2 - y1, x2 - x1), w / 2
    pts = []
    for (cx, cy), start in (((x2, y2), a - math.pi / 2), ((x1, y1), a + math.pi / 2)):
        for i in range(9):
            t = start + math.pi * i / 8
            pts.append((cx + r * math.cos(t), cy + r * math.sin(t)))
    return "M" + "L".join(f"{n(x)} {n(y)}" for x, y in pts) + "Z"


PLAY = "M7.5 5.6v12.8a1.3 1.3 0 0 0 2 1.1l10.2-6.4a1.3 1.3 0 0 0 0-2.2L9.5 4.5a1.3 1.3 0 0 0-2 1.1Z"
HEART = ("M19.2 13.9c1.5-1.5 2.8-3.2 2.8-5.4A5.5 5.5 0 0 0 16.5 3c-1.8 0-3 .5-4.5 2-1.5-1.5-2.7-2-4.5-2"
         "A5.5 5.5 0 0 0 2 8.5c0 2.2 1.3 3.9 2.8 5.4l6.5 6.5a1 1 0 0 0 1.4 0Z")
PENCIL = "M16.3 3.3a2.4 2.4 0 0 1 3.4 0l1 1a2.4 2.4 0 0 1 0 3.4L8.4 20 3 21l1-5.4Z"
COPY = {"f": [rr(8.5, 8.5, 12, 12, 2.6)],
        "s": ["M15.5 5.6v-.3A2.3 2.3 0 0 0 13.2 3H5.3A2.3 2.3 0 0 0 3 5.3v7.9a2.3 2.3 0 0 0 2.3 2.3h.3"]}

ICONS: dict[str, dict] = {
    # --- Bereiche
    "wave": {"f": ["".join(rr(c - 1.3, 12 - h / 2, 2.6, h, 1.3) for c, h in ((4, 5), (8, 11), (12, 17), (16, 9), (20, 5)))]},
    "clock": {"f": [circ(12, 12, 9.5) + "M11 7.5a1 1 0 0 1 2 0v3.97l2.55 1.7a1 1 0 1 1-1.1 1.66l-3-2A1 1 0 0 1 11 12Z"]},
    "stack": {"f": [rr(3, 5, 12, 2.4, 1.2) + rr(3, 10, 12, 2.4, 1.2) + rr(3, 15, 7.5, 2.4, 1.2), circ(16.8, 17.4, 3),
                    rr(17.6, 5, 2.2, 12.5, 1.1)]},
    "compass": {"f": [circ(12, 12, 9.5) + "M15.6 8.4l-2.1 5.1-5.1 2.1 2.1-5.1Z"]},
    "globe": {"s": [circ(12, 12, 9), "M3 12h18", "M12 3c2.5 2.7 3.8 5.7 3.8 9s-1.3 6.3-3.8 9c-2.5-2.7-3.8-5.7-3.8-9S9.5 5.7 12 3Z"]},
    "inbox": {"f": ["M5.6 4.5h12.8a1.5 1.5 0 0 1 1.38.9L22 11v7.5a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V11l2.22-5.6a1.5 1.5 0 0 1 1.38-.9Z"
                    "M4.4 11.4h4.3l1.4 2.6h3.8l1.4-2.6h4.3L17.5 6.7h-11Z"]},
    "chart": {"f": [rr(3.5, 11, 3.4, 9.5, 1.3) + rr(10.3, 3.5, 3.4, 17, 1.3) + rr(17.1, 7.5, 3.4, 13, 1.3)]},
    "grid": {"f": [rr(3.5, 3.5, 7.5, 7.5, 2.2) + rr(13, 3.5, 7.5, 7.5, 2.2) + rr(3.5, 13, 7.5, 7.5, 2.2) + rr(13, 13, 7.5, 7.5, 2.2)]},
    "tag": {"f": ["M3.5 11.3V5A1.5 1.5 0 0 1 5 3.5h6.3a1.5 1.5 0 0 1 1.06.44l7.7 7.7a1.5 1.5 0 0 1 0 2.12l-6.3 6.3"
                  "a1.5 1.5 0 0 1-2.12 0l-7.7-7.7A1.5 1.5 0 0 1 3.5 11.3Z" + circ(8.2, 8.2, 1.6)]},
    "share": {"f": [circ(18, 5.5, 3) + circ(6, 12, 3) + circ(18, 18.5, 3)], "s": ["m8.6 10.6 6.8-3.7", "m8.6 13.4 6.8 3.7"]},
    "transfer": {"s": ["M8 3 4 7l4 4", "M4 7h16", "m16 21 4-4-4-4", "M20 17H4"]},
    "split": {"s": ["M16 3h5v5", "M8 3H3v5", "M12 22v-8.3a4 4 0 0 0-1.17-2.87L3 3", "m15 9 6-6"]},
    "layers": {"f": ["M12 2.5l9.2 4.6a.6.6 0 0 1 0 1.08L12 12.8 2.8 8.18a.6.6 0 0 1 0-1.08Z"],
               "s": ["m3 12.4 9 4.5 9-4.5", "m3 16.9 9 4.5 9-4.5"]},
    "palette": {"f": ["M12 3a9 9 0 1 0 0 18c1.4 0 1.9-1.3 1.1-2.3-.9-1.1-.2-2.7 1.2-2.7H17a4 4 0 0 0 4-4c0-5-4-9-9-9Z"
                      + circ(7.5, 11, 1.5) + circ(10.5, 7, 1.5) + circ(15, 8, 1.5)]},
    "panel": {"f": [rr(2.5, 4, 19, 16, 2.6) + rr(10, 6.2, 9.3, 11.6, 1)]},
    "sliders": {"f": [circ(14.5, 7, 3), circ(9.5, 17, 3)], "s": ["M4 7h7", "M18 7h2", "M4 17h2", "M13 17h7"]},
    "flag": {"f": ["M5 4.5h11.2a.8.8 0 0 1 .7 1.2L15 9l1.9 3.3a.8.8 0 0 1-.7 1.2H5Z"], "s": ["M5 21V3.5"]},
    # --- Wiedergabe
    "play": {"f": [PLAY]},
    "pause": {"f": [rr(6, 4, 4.2, 16, 1.4) + rr(13.8, 4, 4.2, 16, 1.4)]},
    "next": {"f": [rr(17, 5, 2.4, 14, 1.2), "M5 6.2v11.6a1 1 0 0 0 1.55.83l8.6-5.8a1 1 0 0 0 0-1.66l-8.6-5.8A1 1 0 0 0 5 6.2Z"]},
    "prev": {"f": [rr(4.6, 5, 2.4, 14, 1.2), "M19 6.2v11.6a1 1 0 0 1-1.55.83l-8.6-5.8a1 1 0 0 1 0-1.66l8.6-5.8A1 1 0 0 1 19 6.2Z"]},
    "shuffle": {"s": ["m18 14 3.5 3.5L18 21", "m18 3 3.5 3.5L18 10", "M2.5 17.5h1.4a4 4 0 0 0 3.3-1.7l6.1-8.6a4 4 0 0 1 3.3-1.7h4.9",
                      "M2.5 6.5h1.4a4 4 0 0 1 3.1 1.5", "M21.5 17.5h-4.9a4 4 0 0 1-3.1-1.5"]},
    "repeat": {"s": ["m17 2.5 3.5 3.5L17 9.5", "M3.5 11v-1a4 4 0 0 1 4-4h13", "m7 21.5-3.5-3.5L7 14.5", "M20.5 13v1a4 4 0 0 1-4 4h-13"]},
    "volume": {"f": ["M3 9.2A1.2 1.2 0 0 1 4.2 8H7l4.3-3.6A1 1 0 0 1 13 5.2v13.6a1 1 0 0 1-1.7.77L7 16H4.2A1.2 1.2 0 0 1 3 14.8Z"],
               "s": ["M16.5 8.8a4.5 4.5 0 0 1 0 6.4", "M19.4 6a8.5 8.5 0 0 1 0 12"]},
    "disc": {"f": [circ(12, 12, 9.5) + circ(12, 12, 2.6)]},
    "mic": {"f": [rr(8.5, 2, 7, 12.5, 3.5)], "s": ["M19 10.5a7 7 0 0 1-14 0", "M12 17.5v4"]},
    "listen": {"f": [rr(2.8, 12.5, 5.2, 8.5, 2.2), rr(16, 12.5, 5.2, 8.5, 2.2)], "s": ["M4.2 14v-2a7.8 7.8 0 0 1 15.6 0v2"]},
    # --- Aktionen
    "plus": {"f": [circ(12, 12, 9.5) + "M11 7.5h2v3.5h3.5v2H13v3.5h-2V13H7.5v-2H11Z"]},
    "check": {"s": ["M20 6 9 17l-5-5"]},
    "x": {"s": ["M18 6 6 18", "m6 6 12 12"]},
    "trash": {"f": [rr(3, 4.6, 18, 2.4, 1.2), "M9 4.8V3.8A1.3 1.3 0 0 1 10.3 2.5h3.4A1.3 1.3 0 0 1 15 3.8v1Z",
                    "M5.2 8.2h13.6l-.83 11.4a2 2 0 0 1-2 1.86H8.03a2 2 0 0 1-2-1.86Z" + cap(10, 11, 10, 17.5, 1.6) + cap(14, 11, 14, 17.5, 1.6)]},
    "pencil": {"f": [PENCIL]},
    "edit": {"f": [PENCIL], "s": ["M13.5 21h7"]},
    "external": {"f": ["M14.5 2.5h6a1 1 0 0 1 1 1v6a.8.8 0 0 1-1.37.57L13.93 3.87A.8.8 0 0 1 14.5 2.5Z"],
                 "s": ["M18.5 5.5 11 13", "M11 4.5H6.3A3.3 3.3 0 0 0 3 7.8v9.9A3.3 3.3 0 0 0 6.3 21h9.9a3.3 3.3 0 0 0 3.3-3.3V13"]},
    "search": {"s": [circ(10.8, 10.8, 6.6), "m15.8 15.8 4.7 4.7"]},
    "copy": COPY,
    "dupe": COPY,
    "download": {"f": [rr(4, 18.8, 16, 2.4, 1.2)], "s": ["M12 3.5v11", "m7 10 5 5 5-5"]},
    "upload": {"f": [rr(4, 2.8, 16, 2.4, 1.2)], "s": ["M12 20.5v-11", "m7 14 5-5 5 5"]},
    "archive": {"f": [rr(3, 3.5, 18, 5, 1.5), "M4.5 10h15v8.5a2.5 2.5 0 0 1-2.5 2.5H7a2.5 2.5 0 0 1-2.5-2.5Z" + cap(10, 13.6, 14, 13.6, 1.8)]},
    "folder": {"f": ["M2.5 6.5a2 2 0 0 1 2-2h4.3a1.5 1.5 0 0 1 1.1.45l1.7 1.75h7.9a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2h-15a2 2 0 0 1-2-2Z"]},
    "restore": {"s": ["M3.5 12a8.5 8.5 0 1 0 2.8-6.3L3.5 8.2", "M3.5 3.5v4.7h4.7", "M12 8v4l2.8 1.9"]},
    "sync": {"s": ["M20.5 12a8.5 8.5 0 0 1-14.7 5.8L3.5 15.5", "M3.5 12A8.5 8.5 0 0 1 18.2 6.2l2.3 2.3", "M20.5 3.5v5h-5", "M3.5 20.5v-5h5"]},
    "sort": {"s": ["M7 4v16", "m3 8 4-4 4 4", "M17 20V4", "m13 16 4 4 4-4"]},
    "select": {"s": ["m9 11 3 3L22 4", "M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"]},
    "key": {"f": [circ(8, 15.5, 5) + circ(8, 15.5, 1.8)], "s": ["m11.6 11.9 8.4-8.4", "m17 6.5 3 3", "m14.3 9.2 2 2"]},
    "sparkle": {"f": ["M10.5 3c.6 5 2.5 7 7.5 7.5-5 .5-6.9 2.5-7.5 7.5-.6-5-2.5-7-7.5-7.5 5-.5 6.9-2.5 7.5-7.5Z",
                      "M18.5 14c.3 2.1 1.2 3.1 3.5 3.5-2.3.4-3.2 1.4-3.5 3.5-.3-2.1-1.2-3.1-3.5-3.5 2.3-.4 3.2-1.4 3.5-3.5Z"]},
    "chat": {"f": ["M21 12a8.5 8.5 0 0 1-12.4 7.55L3.6 20.6a.6.6 0 0 1-.72-.72l1.05-5A8.5 8.5 0 1 1 21 12Z"
                   + circ(8.9, 12, 1.25) + circ(12.5, 12, 1.25) + circ(16.1, 12, 1.25)]},
    "info": {"f": [circ(12, 12, 9.5) + cap(12, 11, 12, 16.5, 2) + circ(12, 7.6, 1.3)]},
    "heart": {"s": [HEART]},
    "heartFill": {"f": [HEART]},
    "shield": {"f": ["M12 2.5 4 5.7v5.8c0 4.9 3.4 8.9 8 10 4.6-1.1 8-5.1 8-10V5.7Z"
                     "M8.1 12.4l1.4-1.4 1.8 1.8 3.9-3.9 1.4 1.4-5.3 5.3Z"]},
    "qr": {"f": [rr(3, 3, 7.5, 7.5, 1.6) + rr(5.3, 5.3, 2.9, 2.9, .5), rr(13.5, 3, 7.5, 7.5, 1.6) + rr(15.8, 5.3, 2.9, 2.9, .5),
                 rr(3, 13.5, 7.5, 7.5, 1.6) + rr(5.3, 15.8, 2.9, 2.9, .5),
                 rr(13.5, 13.5, 3, 3, .7) + rr(18, 13.5, 3, 3, .7) + rr(13.5, 18, 3, 3, .7) + rr(18, 18, 3, 3, .7)]},
    "monitor": {"f": [rr(2, 3, 20, 13.5, 2.5), rr(7.5, 19, 9, 2.2, 1.1), rr(10.9, 15, 2.2, 5, 0)]},
    "phone": {"f": [rr(6, 2, 12, 20, 3) + cap(10.6, 18.5, 13.4, 18.5, 1.6)]},
    "more": {"f": [circ(12, 5, 1.9) + circ(12, 12, 1.9) + circ(12, 19, 1.9)]},
    # --- Pfeile
    "arrow": {"s": ["M5 12h14", "m13 6 6 6-6 6"]},
    "back": {"s": ["M19 12H5", "m11 18-6-6 6-6"]},
    "chevron": {"s": ["m9 6 6 6-6 6"]},
    "dot": {},
}
# Handy: Kotlin-Namen (Ico.X) der dort benutzten Symbole
ANDROID = ["wave", "clock", "stack", "sliders", "play", "pause", "plus", "check", "x", "shuffle", "next", "prev", "heart",
           "heartFill", "chart", "trash", "external", "search", "mic", "disc", "compass", "info", "arrow", "back", "chevron",
           "repeat", "share", "key", "sparkle", "monitor", "shield", "qr", "sync", "more", "phone", "edit", "download",
           "upload", "select", "listen", "copy"]

JS_BEGIN, JS_END = "/* ICONS:BEGIN – erzeugt von scripts/gen-icons.py, nicht von Hand ändern */", "/* ICONS:END */"
KT_BEGIN, KT_END = "// ICONS:BEGIN – erzeugt von scripts/gen-icons.py, nicht von Hand ändern", "// ICONS:END"


def js_block() -> str:
    rows = [f"  {k}: {json.dumps({x: v[x] for x in ('f', 's') if v.get(x)}, separators=(',', ':'))}," for k, v in ICONS.items()]
    return f"{JS_BEGIN}\nconst ICONS = {{\n" + "\n".join(rows) + f"\n}};\n{JS_END}"


def kt_block() -> str:
    def lst(xs):
        return "listOf(" + ", ".join(json.dumps(x) for x in xs) + ")" if xs else "emptyList()"
    rows = [f"    {k[0].upper() + k[1:]}({lst(ICONS[k].get('f'))},\n        {lst(ICONS[k].get('s'))})" for k in ANDROID]
    return (f"{KT_BEGIN}\nenum class Ico(val fill: List<String>, val stroke: List<String>) {{\n" + ",\n".join(rows)
            + f";\n}}\n{KT_END}")


def replace(text: str, begin: str, end: str, block: str) -> str:
    pat = re.compile(re.escape(begin) + r".*?" + re.escape(end), re.S)
    if not pat.search(text):
        raise SystemExit(f"Markierung {begin!r} nicht gefunden")
    return pat.sub(lambda _: block, text, count=1)


def main() -> int:
    check = "--check" in sys.argv
    stale = []
    for path, begin, end, block in ((JS, JS_BEGIN, JS_END, js_block()), (KT, KT_BEGIN, KT_END, kt_block())):
        old = path.read_text(encoding="utf-8")
        new = replace(old, begin, end, block)
        if new != old:
            stale.append(path.relative_to(ROOT))
            if not check:
                path.write_text(new, encoding="utf-8")
    if check and stale:
        print("Nicht aktuell (python scripts/gen-icons.py ausführen):", *stale)
        return 1
    print("Aktualisiert:" if stale else "Alles aktuell", *stale)
    return 0


if __name__ == "__main__":
    sys.exit(main())

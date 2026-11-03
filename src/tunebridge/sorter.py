"""Playlist sortieren – 6 Stufen, von „passende Mixes“ bis „Mikro-Genre“. Reine Rechnerei, kein Netz.

Eingabe: Songs als dicts mit genre/subgenre/niche/confidence/tags und (optional) Audio-Werten
bpm/camelot/energy (audiofeat). Ausgabe: Gruppen [{name, items:[Index…], info}], innerhalb sinnvoll geordnet.

Stufen
  1 mixes   Passende Mixes: Tempo-Blöcke (~1 Std.), Reihenfolge nach Tempo, Tonart (Camelot) und Energie
  2 mood    Stimmung & Energie: Chill · Groove · Energie · Peak
  3 fine    Feinsäuberlich: Stimmung × Tempobereich, darin mixbar geordnet
  4 family  Genre-Familie: Elektronisch, Hip-Hop & R&B, …
  5 genre   Hauptgenre
  6 micro   Mikro-Genre: Genre – Subgenre (nur wenn sicher genug), darin nach Tempo
Zu kleine Gruppen wandern eine Ebene gröber, damit nichts in Mini-Listen zerfällt.
"""

from __future__ import annotations

from collections import defaultdict

from .audiofeat import camelot_distance

LEVELS = {1: "Passende Mixes", 2: "Stimmung & Energie", 3: "Feinsäuberlich sortiert",
          4: "Genre-Familie", 5: "Genre", 6: "Mikro-Genre"}
UNSORTED = "Unsortiert"
OTHER = "Sonstiges"

FAMILY = {
    **{g: "Elektronisch" for g in ("Drum & Bass", "Breakcore", "Dubstep", "House", "Techno", "UK Garage / Bass",
                                   "Trance", "Hardstyle / Hardcore", "Trap / Future Bass", "Breakbeat",
                                   "IDM / Experimental", "Electronic")},
    "Phonk": "Phonk & Wave", "Synthwave": "Phonk & Wave",
    "Hip-Hop": "Hip-Hop & R&B", "R&B / Soul": "Hip-Hop & R&B",
    "Pop": "Pop", "Hyperpop": "Pop", "Latin": "Latin & Karibik", "Reggae / Dancehall": "Latin & Karibik",
    "Indie / Alternative": "Rock & Indie", "Rock / Metal": "Rock & Indie",
    "Jazz / Funk": "Jazz, Folk & Klassik", "Country / Folk": "Jazz, Folk & Klassik",
    "Classical / Cinematic": "Jazz, Folk & Klassik", "Ambient / Chill": "Ambient & Chill",
}
# Grundstimmung je Genre, falls keine Audio-Werte da sind (0 = ruhig … 1 = Vollgas)
GENRE_ENERGY = {"Ambient / Chill": 0.15, "Classical / Cinematic": 0.2, "Jazz / Funk": 0.4, "Country / Folk": 0.35,
                "R&B / Soul": 0.4, "Indie / Alternative": 0.45, "Pop": 0.55, "Synthwave": 0.55, "Hip-Hop": 0.6,
                "Latin": 0.65, "Reggae / Dancehall": 0.55, "House": 0.65, "Trance": 0.7, "Techno": 0.75,
                "UK Garage / Bass": 0.7, "Phonk": 0.75, "Trap / Future Bass": 0.75, "Dubstep": 0.85,
                "Drum & Bass": 0.85, "Breakcore": 0.9, "Hardstyle / Hardcore": 0.95, "Rock / Metal": 0.75}
MOOD = [(0.0, "Chill"), (0.4, "Groove"), (0.6, "Energie"), (0.78, "Peak")]
CALM_TAGS = {"chill", "chillout", "ambient", "calm", "relaxing", "sad", "mellow", "lo-fi", "lofi", "sleep", "piano"}
HYPE_TAGS = {"aggressive", "hard", "heavy", "energetic", "party", "rage", "brutal", "banger"}
MIX_MINUTES = 60


def energy(it: dict) -> float:
    """Audio-Energie, sonst Genre-Grundwert; Stimmungs-Tags schieben leicht."""
    e = it.get("energy")
    base = GENRE_ENERGY.get(it.get("genre") or "", 0.5)
    if e is not None:   # Audio-Energie liegt real etwa bei 0,15–0,7 -> auf 0–1 strecken; Audio führt, Genre glättet
        e = 0.6 * max(0.0, min(1.0, (float(e) - 0.15) / 0.55)) + 0.4 * base
    else:
        e = base
    tags = {t.lower() for t in (it.get("tags") or [])}
    e += 0.08 * len(tags & HYPE_TAGS) - 0.08 * len(tags & CALM_TAGS)
    return max(0.0, min(1.0, e))


def mood(it: dict) -> str:
    e = energy(it)
    return [name for lo, name in MOOD if e >= lo][-1]


def _bpm(it: dict) -> float | None:
    b = it.get("bpm")
    return float(b) if b else None


def mix_order(items: list[dict], idx: list[int]) -> list[int]:
    """Greedy-Reihenfolge für einen Mix: Start beim ruhigsten Song, dann immer der beste nächste Übergang
    (kleiner Tempo-Sprung, passende Tonart, Energie eher steigend)."""
    if len(idx) <= 2:
        return sorted(idx, key=lambda i: energy(items[i]))
    rest = set(idx)
    cur = min(rest, key=lambda i: (energy(items[i]), _bpm(items[i]) or 0))
    out = [cur]
    rest.discard(cur)
    while rest:
        a = items[cur]

        def cost(j):
            b = items[j]
            ba, bb = _bpm(a), _bpm(b)
            tempo = abs(ba - bb) / max(ba, bb) * 100 if ba and bb else 4.0     # % Tempo-Sprung
            key = camelot_distance(a.get("camelot"), b.get("camelot"))
            de = energy(b) - energy(a)
            return tempo * 1.0 + key * 1.2 + (abs(de) * 6 if de < 0 else de * 2)
        cur = min(rest, key=cost)
        out.append(cur)
        rest.discard(cur)
    return out


def _tempo_band(b: float | None, width: int = 10) -> str:
    if not b:
        return "Tempo unbekannt"
    lo = int(b // width * width)
    return f"{lo}–{lo + width} BPM"


def _label_main(it: dict) -> str:
    return it.get("genre") or UNSORTED


def _label_micro(it: dict) -> str:
    g, s = it.get("genre"), it.get("subgenre")
    if not g:
        return UNSORTED
    if s and (it.get("confidence") is None or it.get("confidence", 1) >= 0.45):
        return f"{g} – {s}"
    return g


def _label_family(it: dict) -> str:
    return FAMILY.get(it.get("genre") or "", OTHER) if it.get("genre") else UNSORTED


def _group(items: list[dict], labels: list, min_size: int) -> dict[str, list[int]]:
    """Gruppieren nach labels[0]; zu kleine Gruppen rutschen Ebene für Ebene gröber (labels[1], labels[2] …).
    Was auf der gröbsten Ebene immer noch zu klein ist -> „Sonstiges“, damit keine Mini-Listen entstehen."""
    level_of = [0] * len(items)
    while True:
        g: dict[str, list[int]] = defaultdict(list)
        for i, it in enumerate(items):
            g[labels[level_of[i]](it)].append(i)
        if min_size <= 1:
            return g
        moved = False
        for name, idx in g.items():
            if len(idx) < min_size and name not in (UNSORTED, OTHER):
                for i in idx:
                    if level_of[i] + 1 < len(labels):
                        level_of[i] += 1
                        moved = True
        if not moved:
            break
    out: dict[str, list[int]] = defaultdict(list)
    for name, idx in g.items():
        out[name if len(idx) >= min_size or name == UNSORTED else OTHER] += idx
    return out


def _mixes(items: list[dict], min_size: int) -> list[tuple[str, list[int], dict]]:
    """Nach Tempo sortieren, bei großen Sprüngen (>8 %) oder nach ~1 Std. einen neuen Mix beginnen."""
    known = sorted((i for i, it in enumerate(items) if _bpm(it)), key=lambda i: (_bpm(items[i]), energy(items[i])))
    unknown = [i for i, it in enumerate(items) if not _bpm(it)]
    blocks: list[list[int]] = []
    cur: list[int] = []
    dur = 0.0
    for i in known:
        d = (items[i].get("duration_ms") or 210_000) / 60000
        if cur:
            prev = _bpm(items[cur[-1]])
            jump = (_bpm(items[i]) - prev) / prev
            if (jump > 0.08 and len(cur) >= min_size) or dur + d > MIX_MINUTES * 1.25:
                blocks.append(cur)
                cur, dur = [], 0.0
        cur.append(i)
        dur += d
    if cur:
        if blocks and len(cur) < min_size:
            blocks[-1] += cur
        else:
            blocks.append(cur)
    out = []
    for n, b in enumerate(blocks, 1):
        bpms = [_bpm(items[i]) for i in b]
        mins = round(sum((items[i].get("duration_ms") or 210_000) for i in b) / 60000)
        out.append((f"Mix {n} · {round(min(bpms))}–{round(max(bpms))} BPM", mix_order(items, b),
                    {"minuten": mins}))
    if unknown:
        out.append(("Tempo unbekannt", unknown, {}))
    return out


def sort(items: list[dict], level: int, min_size: int = 3) -> list[dict]:
    """-> [{name, items:[Index…], info}] größte Gruppe zuerst (Mixes in Tempo-Reihenfolge)."""
    level = max(1, min(6, int(level)))
    if level == 1:
        groups = _mixes(items, min_size)
    else:
        tempo = lambda it: f"{mood(it)} · {_tempo_band(_bpm(it))}"  # noqa: E731
        chains = {2: [mood], 3: [tempo, mood], 4: [_label_family], 5: [_label_main, _label_family],
                  6: [_label_micro, _label_main, _label_family]}
        g = _group(items, chains[level], min_size)
        order = (lambda idx: mix_order(items, idx)) if level in (2, 3) else \
            (lambda idx: sorted(idx, key=lambda i: (_bpm(items[i]) or 999, items[i].get("artist") or "")))
        tail = {UNSORTED: 2, OTHER: 1}
        groups = [(n, order(idx), {}) for n, idx in
                  sorted(g.items(), key=lambda kv: (tail.get(kv[0], 0), -len(kv[1]), kv[0]))]
    res = []
    for name, idx, info in groups:
        bpms = [b for i in idx if (b := _bpm(items[i]))]
        res.append({"name": name, "items": idx, "info": {
            **info, "anzahl": len(idx),
            "bpm": [round(min(bpms)), round(max(bpms))] if bpms else None,
            "energie": round(sum(energy(items[i]) for i in idx) / len(idx), 2) if idx else None}})
    return res

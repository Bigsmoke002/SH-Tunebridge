"""Mikro-Genre-Prüfstand, Stufe 3: Methoden vergleichen.
Aufruf: uv run python scripts/genre_bench/micro_score.py micro.json micro_audio.json"""
import json
import sys
from collections import defaultdict

from tunebridge.genres import classify

meta = json.load(open(sys.argv[1], encoding="utf-8"))
audio = {(r["artist"], r["title"]): r for r in json.load(open(sys.argv[2], encoding="utf-8"))}


def norm(d: dict, top: float = 100.0) -> dict:
    m = max(d.values(), default=0)
    return {k: v / m * top for k, v in d.items()} if m else {}


def mb_tags(r) -> dict:
    mb = r.get("mb") or {}
    out: dict = {}
    for part, w in (("recording", 100), ("release_group", 70), ("artist", 40)):
        for k, v in norm(mb.get(part) or {}, w).items():
            out[k] = max(out.get(k, 0), v)
    return out


def audio_tags(r, min_act: float = 0.05) -> dict:
    st = (audio.get((r["artist"], r["title"])) or {}).get("styles") or []
    return {s.split("---")[-1].lower(): a * 100 for s, a in st if a >= min_act}


def merge(*parts) -> dict:
    out: dict = {}
    for p in parts:
        for k, v in p.items():
            out[k] = out.get(k, 0) + v
    return out


def methods(r) -> dict:
    hint = r.get("apple")
    lf = r.get("lastfm_tags") or {}
    mb, au = mb_tags(r), audio_tags(r)
    res = {"1 Tags (jetzt)": tuple(r["m1"][:2])}
    for name, tags in (("2 MusicBrainz", mb), ("3 Audio", au), ("4 Tags+MB", merge(lf, mb)),
                       ("5 Tags+MB+Audio", merge(lf, mb, {k: v * 0.6 for k, v in au.items()}))):
        c = classify(tags, hint) if tags else None
        res[name] = (c.genre, c.subgenre) if c else (None, None)
    return res


stats = defaultdict(lambda: [0, 0, 0])      # Haupt richtig, Sub richtig, Sub überhaupt geliefert
per_sub = defaultdict(lambda: defaultdict(int))
fails = defaultdict(list)
for r in meta:
    for name, (g, s) in methods(r).items():
        st = stats[name]
        st[0] += g == r["main"]
        st[1] += s == r["sub"]
        st[2] += s is not None
        per_sub[r["sub"]][name] += s == r["sub"]
        if s != r["sub"]:
            fails[name].append(f"{r['sub']}: {r['artist']} – {r['title']} -> {g}/{s}")

n = len(meta)
print(f"{n} Songs, {len(per_sub)} Mikro-Genres\n")
print(f"{'Methode':22} {'Hauptgenre':>12} {'Mikro-Genre':>12} {'Mikro geliefert':>16}")
for name, (g, s, d) in sorted(stats.items()):
    print(f"{name:22} {g:>5}/{n} {100*g/n:3.0f}% {s:>5}/{n} {100*s/n:3.0f}% {d:>9}/{n}")
best = max(stats, key=lambda k: stats[k][1])
print(f"\nMikro-Genres, die mit der besten Methode ({best}) nie stimmen:")
print(", ".join(sorted(s for s, d in per_sub.items() if not d[best])))
if "-v" in sys.argv:
    for name in sorted(fails):
        print(f"\n## {name}")
        print("\n".join(fails[name]))

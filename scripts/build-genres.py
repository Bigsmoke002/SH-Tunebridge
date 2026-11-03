#!/usr/bin/env python3
"""Erzeugt src/tunebridge/genres/catalog.json – den großen Genre-Katalog.

Quelle: Wikidata (CC0) – alle Musikgenres inkl. der 2 200 MusicBrainz-Genres, mit Synonymen
und „Untergenre von“-Beziehungen. Jedes Genre wird über seine Eltern-Kette einer der
Hauptfamilien aus taxonomy.py zugeordnet (kürzester Weg gewinnt).

Ergebnis je Genre: Hauptfamilie, Subgenre (Ebene direkt unter der Familie) und das Genre selbst
als „Nische“. Die App lädt nur die fertige Datei, zur Laufzeit gibt es keine Netzaufrufe.

Aufruf:  uv run python scripts/build-genres.py        (dauert ~1 min)
"""

from __future__ import annotations

import json
import re
import sys
import urllib.parse
import urllib.request
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "src/tunebridge/genres/catalog.json"
UA = "SH-Tunebridge-genre-builder/1.0 (https://github.com/Bigsmoke002/SH-Tunebridge)"

QUERY = """
SELECT ?g ?label ?mb (GROUP_CONCAT(DISTINCT ?alt; separator="|") AS ?alts)
       (GROUP_CONCAT(DISTINCT ?p; separator="|") AS ?parents) WHERE {
  { ?g wdt:P31 wd:Q188451 } UNION { ?g wdt:P8052 ?mb0 }
  ?g rdfs:label ?label FILTER(lang(?label) = "en")
  OPTIONAL { ?g wdt:P8052 ?mb }
  OPTIONAL { ?g skos:altLabel ?alt FILTER(lang(?alt) = "en") }
  OPTIONAL { ?g wdt:P279 ?p }
} GROUP BY ?g ?label ?mb
"""

# Wikidata-ID -> Hauptfamilie (Reihenfolge = Vorrang bei gleich langem Weg: spezifisch vor allgemein)
ANCHORS: list[tuple[str, str]] = [
    ("Q903735", "Breakcore"), ("Q90568328", "Phonk"), ("Q104695865", "Hyperpop"),
    ("Q188994", "Drum & Bass"), ("Q1102161", "Drum & Bass"),
    ("Q20474", "Dubstep"), ("Q22908553", "Trap / Future Bass"), ("Q111628716", "Trap / Future Bass"),
    ("Q106369996", "Trap / Future Bass"),
    ("Q20502", "House"), ("Q170611", "Techno"), ("Q170435", "Trance"),
    ("Q223840", "Hardstyle / Hardcore"), ("Q388906", "Hardstyle / Hardcore"),
    ("Q1165777", "UK Garage / Bass"), ("Q2346991", "UK Garage / Bass"),
    ("Q663519", "Breakbeat"), ("Q19938910", "Synthwave"), ("Q15733887", "Synthwave"),
    ("Q660984", "IDM / Experimental"), ("Q1640319", "IDM / Experimental"), ("Q726239", "IDM / Experimental"),
    ("Q487965", "IDM / Experimental"),
    ("Q11401", "Hip-Hop"), ("Q2913982", "Hip-Hop"),
    ("Q45981", "R&B / Soul"), ("Q850412", "R&B / Soul"), ("Q131272", "R&B / Soul"), ("Q180268", "R&B / Soul"),
    ("Q202930", "Latin"), ("Q18345375", "Latin"),
    ("Q9794", "Reggae / Dancehall"), ("Q474027", "Reggae / Dancehall"), ("Q54365", "Reggae / Dancehall"),
    ("Q8341", "Jazz / Funk"), ("Q164444", "Jazz / Funk"), ("Q58339", "Jazz / Funk"),
    ("Q9759", "Blues"),
    ("Q492264", "Classical / Cinematic"), ("Q1062702", "Classical / Cinematic"), ("Q9730", "Classical / Cinematic"),
    ("Q193207", "Ambient / Chill"), ("Q251192", "Ambient / Chill"), ("Q1507298", "Ambient / Chill"),
    ("Q213121", "Ambient / Chill"),
    ("Q183504", "Indie / Alternative"), ("Q11366", "Indie / Alternative"), ("Q272167", "Indie / Alternative"),
    ("Q38848", "Rock / Metal"), ("Q10922", "Rock / Metal"), ("Q11399", "Rock / Metal"), ("Q11365", "Rock / Metal"),
    ("Q10926", "Rock / Metal"),
    ("Q213665", "Pop"), ("Q131578", "Pop"), ("Q188450", "Pop"), ("Q37073", "Pop"),
    ("Q83440", "Folk / Country / World"), ("Q43343", "Folk / Country / World"), ("Q205049", "Folk / Country / World"),
    ("Q201022", "Folk / Country / World"), ("Q943929", "Folk / Country / World"), ("Q16555308", "Folk / Country / World"),
    ("Q17176998", "Folk / Country / World"), ("Q108821603", "Folk / Country / World"),
    ("Q10264148", "Folk / Country / World"), ("Q11639", "Folk / Country / World"),
    ("Q207628", "Classical / Cinematic"), ("Q178122", "Classical / Cinematic"),
    ("Q1065742", "Religious"), ("Q6452410", "Religious"),
    ("Q2389651", "Kinder & Sonstiges"),
    ("Q851213", "Electronic"), ("Q9778", "Electronic"), ("Q316930", "Electronic"), ("Q96740854", "Electronic"),
]
# Einzelne Genres, deren Wikidata-Eltern in die Irre führen
OVERRIDE = {
    "Q120484427": ("Breakcore", "Mashcore / Dariacore"),   # dariacore (Wikidata: nur „EDM“)
    "Q125455905": ("Phonk", "Brazilian Phonk"),
    "Q112997482": ("Phonk", "Drift Phonk"),
}
# keine Anzeige / kein Abgleich (anstößige oder nichtssagende Bezeichnungen)
SKIP_LABELS = {"lolicore", "music", "song", "instrumental", "remix", "cover version"}

_SMALL = {"and", "n", "of", "the", "in", "a", "de", "la", "do", "da", "du", "y", "e", "con", "à"}


def title(s: str) -> str:
    """„atmospheric breakcore“ -> „Atmospheric Breakcore“, „UK garage“ bleibt „UK Garage“."""
    out = []
    for i, w in enumerate(s.split(" ")):
        if w.lower() in _SMALL and i:
            out.append(w)
        elif w[:1].islower():
            out.append("-".join(p[:1].upper() + p[1:] for p in w.split("-")))
        else:
            out.append(w)
    return " ".join(out)


def fetch() -> list[dict]:
    url = "https://query.wikidata.org/sparql?" + urllib.parse.urlencode({"query": QUERY})
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/sparql-results+json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.load(r)["results"]["bindings"]


def build(rows: list[dict]) -> dict:
    sys.path.insert(0, str(ROOT / "src"))
    from tunebridge.genres.taxonomy import TAXONOMY
    from tunebridge.matching import normalize

    qid = lambda u: u.rsplit("/", 1)[1]  # noqa: E731
    nodes: dict[str, dict] = {}
    for b in rows:
        q = qid(b["g"]["value"])
        nodes[q] = {"label": b["label"]["value"], "mb": "mb" in b,
                    "alts": [a for a in b["alts"]["value"].split("|") if a],
                    "parents": [qid(p) for p in b["parents"]["value"].split("|") if p]}
    anchor_rank = {q: i for i, (q, _) in enumerate(ANCHORS)}
    anchor_main = dict(ANCHORS)
    # Kuratierte Subgenres (taxonomy.py) per Name wiederfinden
    curated: dict[str, tuple[str, str]] = {}
    for main, subs in TAXONOMY.items():
        for sub, aliases in subs.items():
            if sub != "_":
                for a in [sub, *aliases]:
                    curated.setdefault(normalize(a), (main, sub))

    out: dict[str, dict] = {}
    stats = {"total": 0, "mapped": 0, "unmapped": 0}
    for q, n in nodes.items():
        if n["label"].lower() in SKIP_LABELS or re.fullmatch(r"Q\d+", n["label"]):
            continue
        stats["total"] += 1
        if q in OVERRIDE:
            main, sub = OVERRIDE[q]
        else:
            # Breitensuche nach oben bis zur nächsten Hauptfamilie; Weg merken
            best = None
            seen = {q: None}
            dq = deque([(q, 0)])
            while dq:
                cur, dist = dq.popleft()
                if best and dist > best[1]:
                    break
                if cur in anchor_main:
                    cand = (cur, dist)
                    if not best or anchor_rank[cur] < anchor_rank[best[0]]:
                        best = cand
                    continue
                for p in nodes.get(cur, {}).get("parents", []):
                    if p not in seen:
                        seen[p] = cur
                        dq.append((p, dist + 1))
            if not best:
                # ohne Familie trotzdem aufnehmen: wird dann als Nische angezeigt
                stats["unmapped"] += 1
                for name in {normalize(n["label"]), *(normalize(a) for a in n["alts"] if len(a) > 2)}:
                    if name and name not in out:
                        out[name] = {"main": None, "sub": None, "niche": title(n["label"]), "mb": n["mb"]}
                continue
            main = anchor_main[best[0]]
            # Ebene direkt unter dem Anker = Subgenre
            path, cur = [], best[0]
            while cur is not None:
                path.append(cur)
                cur = seen.get(cur)
            # path: Anker ... q
            sub = title(nodes[path[1]]["label"]) if len(path) > 1 else None
            for node in reversed(path[1:]):          # kuratierte Namen bevorzugen (spezifischstes zuerst)
                hit = curated.get(normalize(nodes[node]["label"]))
                if hit and hit[0] == main:
                    sub = hit[1]
                    break
        stats["mapped"] += 1
        label = title(n["label"])
        niche = label if (sub is None or normalize(label) != normalize(sub)) and q not in anchor_main else None
        names = {normalize(n["label"]), *(normalize(a) for a in n["alts"] if len(a) > 2)}
        for name in names:
            if not name or (name in out and out[name]["main"] and out[name].get("mb")):
                continue           # MusicBrainz-Genres haben bei Namensgleichheit Vorrang
            out[name] = {"main": main, "sub": sub, "niche": niche, "mb": n["mb"]}
    return {"source": "Wikidata (CC0) inkl. MusicBrainz-Genres (CC0)", "stats": stats,
            "genres": {k: [v["main"], v["sub"], v["niche"]] for k, v in sorted(out.items())}}


def main() -> None:
    # optional: --from datei.json (gespeicherte Wikidata-Antwort, z. B. zum Nachbauen ohne Netz)
    if len(sys.argv) > 2 and sys.argv[1] == "--from":
        rows = json.loads(Path(sys.argv[2]).read_text())["results"]["bindings"]
    else:
        rows = fetch()
    data = build(rows)
    OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")))
    s = data["stats"]
    print(f"{s['total']} Genres, {s['mapped']} zugeordnet, {s['unmapped']} ohne Familie, "
          f"{len(data['genres'])} Namen/Synonyme -> {OUT.relative_to(ROOT)} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()

"""Tags (mit Gewicht) -> Hauptgenre + Subgenre.

Quellen für Tags (siehe genres/sources/): Last.fm (sehr gut für Subgenres
wie "liquid funk", "neurofunk"), dazu grobe Genres der Erkennungsdienste.

Ablauf
  1. exakte Tag-Treffer im Genre-Baum (volles Gewicht)
  2. Tags, die auf ein bekanntes Genre *enden* („emo breakcore“, „russian phonk“) – 60 % Gewicht
  3. Nischen-Genres bekommen einen Bonus (siehe taxonomy.PRIORITY)
  4. passt gar nichts, aber Tags wie „electronic“/„dance“ sind da -> „Electronic“ (geringe Sicherheit)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from ..matching import normalize
from .taxonomy import FALLBACK, FAMILIES, HIPHOP_SIGNALS, IGNORED_TAGS, PRIORITY, TAXONOMY, WEAK_TAGS

# Synonym -> (Hauptgenre|None, Subgenre|None, Nische|None)
# 1. großer Katalog (Wikidata/MusicBrainz, ~6 400 Genres, scripts/build-genres.py)
# 2. darüber die handgepflegte Taxonomie – sie hat immer Vorrang
_INDEX: dict[str, tuple[str | None, str | None, str | None]] = {}
_CATALOG = Path(__file__).with_name("catalog.json")
CATALOG_STATS: dict = {}
if _CATALOG.exists():
    _cat = json.loads(_CATALOG.read_text(encoding="utf-8"))
    CATALOG_STATS = _cat.get("stats", {})
    for _name, (_m, _s, _n) in _cat["genres"].items():
        _INDEX[_name] = (_m, _s, _n)
    del _cat
for _main, _subs in TAXONOMY.items():
    for _sub, _aliases in _subs.items():
        for _alias in _aliases:
            _key = normalize(_alias)
            _niche = _INDEX.get(_key, (None, None, None))[2]
            _INDEX[_key] = (_main, None if _sub == "_" else _sub, _niche if _INDEX.get(_key, ("",))[0] == _main else None)
_IGNORED = {normalize(t) for t in IGNORED_TAGS}
_WEAK = {normalize(k): v for k, v in WEAK_TAGS.items()}
_HIPHOP = {normalize(t) for t in HIPHOP_SIGNALS}
# Hauptgenres aus dem großen Katalog, die nicht in unserer Liste stehen („Electronic“ als Sammelbegriff),
# zählen nur schwach – ein konkretes Tag wie „wave“ soll gegen „witch house -> Electronic“ gewinnen
GENERIC_FACTOR = 0.3
_FALLBACK = {normalize(k): v for k, v in FALLBACK.items()}
# zu kurz/mehrdeutig, um als Wortende zu zählen („new wave“ ist kein Wave, „dub“ kein Dubstep)
_NO_SUFFIX = {"wave", "dub", "140", "goa", "drift", "drill", "minimal", "garage", "breaks", "neuro", "rollers",
              "liquid", "score", "ost", "epic", "piano", "drone", "chill", "dreamy", "soul", "funk", "anime",
              "memphis", "disco", "folk", "rap", "pop", "rock", "metal", "punk", "jungle", "house", "trap"}


# selbst gelernte Genres (genres/learn.py) – werden beim ersten classify() aus der DB geladen
_LEARNED: dict[str, tuple[str | None, str | None, str | None]] | None = None


def set_learned(d: dict) -> None:
    global _LEARNED
    _LEARNED = dict(d)


def _learned() -> dict:
    global _LEARNED
    if _LEARNED is None:
        try:
            from .learn import learned_index
            _LEARNED = learned_index()
        except Exception:
            _LEARNED = {}
    return _LEARNED


def _lookup(key: str) -> tuple[tuple[str | None, str | None, str | None] | None, float]:
    lr = _learned()
    if key in lr:
        return lr[key], 1.0
    if key in _INDEX:
        return _INDEX[key], 1.0
    words = key.split()
    for i in range(1, len(words)):  # längstes passendes Wortende
        tail = " ".join(words[i:])
        if tail in _INDEX and tail not in _NO_SUFFIX:
            return _INDEX[tail], 0.6
    return None, 0.0


@dataclass
class Classification:
    genre: str | None
    subgenre: str | None
    confidence: float  # 0..1
    scores: dict[str, float] = field(default_factory=dict)
    niche: str | None = None                     # spezifischstes erkanntes Genre („Dariacore“)
    matched: dict[str, str] = field(default_factory=dict)   # Tag -> Treffer (für das Debug-Protokoll)
    unmatched: list[str] = field(default_factory=list)      # Tags ohne Treffer (Kandidaten zum Dazulernen)


# Genre-Namen der Erkennungsdienste (Shazam = Apple-Genres), die nicht direkt in unserer Liste stehen
_SERVICE = {normalize(k): v for k, v in {
    "Hip-Hop/Rap": "Hip-Hop", "Rap": "Hip-Hop", "R&B/Soul": "R&B / Soul", "Alternative": "Indie / Alternative",
    "Indie Pop": "Indie / Alternative", "Hard Rock": "Rock / Metal", "Metal": "Rock / Metal", "Punk": "Rock / Metal",
    "Singer/Songwriter": "Country / Folk", "Soundtrack": "Classical / Cinematic", "Urbano latino": "Latin",
    "Música Mexicana": "Latin", "Afrobeats": "Pop", "K-Pop": "Pop", "J-Pop": "Pop",
}.items()}
FAMILY_MARGIN = 0.5   # Kandidat aus der passenden Familie gewinnt, wenn er mind. halb so stark ist


def classify(tags: dict[str, float], hint: str | None = None) -> Classification:
    """tags: {"liquid funk": 100, "drum and bass": 80, ...} (Last.fm-Gewichte 0..100).
    hint: grobes Genre des Erkennungsdienstes für genau diesen Song („Electronic“, „Hip-Hop/Rap“)."""
    main_scores: dict[str, float] = {}
    sub_scores: dict[tuple[str, str], float] = {}
    niche_scores: dict[tuple[str | None, str], float] = {}
    fallback: dict[str, float] = {}
    matched: dict[str, str] = {}
    unmatched: list[str] = []

    # Phonk wird oft zusätzlich mit „hip hop“/„trap“ getaggt – dann bleibt „trap“ beim Phonk-Umfeld
    # „trap“ zählt nur als Rap, wenn die Rap-Tags nennenswert sind (TroyBoi: trap 50, hip-hop 1 = EDM-Trap)
    trap_w = sum(w for t, w in tags.items() if normalize(t) == "trap")
    rap_w = sum(w for t, w in tags.items() if normalize(t) in _HIPHOP)
    hiphop = rap_w >= 0.2 * trap_w and rap_w > 0 and not any("phonk" in normalize(t) for t in tags)
    for tag, weight in tags.items():
        key = normalize(tag)
        if key in _FALLBACK:
            fallback[_FALLBACK[key]] = fallback.get(_FALLBACK[key], 0) + weight
        if key in _IGNORED:
            continue
        hit, factor = _lookup(key)
        if not hit:
            if key not in _FALLBACK:
                unmatched.append(tag)
            continue
        main, sub, niche = hit
        if key == "trap" and hiphop:
            main, sub, niche = "Hip-Hop", "Trap Rap", None
        matched[tag] = " › ".join(x for x in (main or "?", sub, niche) if x)
        w = weight * factor * PRIORITY.get(main, 1.0) * _WEAK.get(key, 1.0)
        if main and main not in TAXONOMY:
            w *= GENERIC_FACTOR
        if niche:
            niche_scores[(main, niche)] = niche_scores.get((main, niche), 0) + w
        if not main:
            continue
        main_scores[main] = main_scores.get(main, 0) + w
        if sub:
            sub_scores[(main, sub)] = sub_scores.get((main, sub), 0) + w

    def pick_niche(genre: str | None) -> str | None:
        cands = {n: v for (m, n), v in niche_scores.items() if m == genre or m is None}
        return max(cands, key=cands.get) if cands else None

    if not main_scores:
        if fallback:
            return Classification(max(fallback, key=fallback.get), None, 0.2, fallback,
                                  niche=pick_niche(None), matched=matched, unmatched=unmatched)
        return Classification(None, None, 0.0, niche=pick_niche(None), matched=matched, unmatched=unmatched)

    genre = max(main_scores, key=main_scores.get)
    family = _family(hint)
    if family and genre not in family:
        alts = {g: v for g, v in main_scores.items() if g in family}
        if alts and max(alts.values()) >= FAMILY_MARGIN * main_scores[genre]:
            genre = max(alts, key=alts.get)
    total = sum(main_scores.values())
    subs = {s: v for (m, s), v in sub_scores.items() if m == genre}
    subgenre = max(subs, key=subs.get) if subs else None
    niche = pick_niche(genre)
    if niche and subgenre and (normalize(subgenre) in normalize(niche) or normalize(niche) in normalize(subgenre)):
        niche = None   # „Liquid“ / „Liquid Drum and Bass“ – nichts Neues
    return Classification(genre, subgenre, round(main_scores[genre] / total, 2), main_scores,
                          niche=niche, matched=matched, unmatched=unmatched)


def service_main(hint: str | None) -> str | None:
    """Grobes Dienst-Genre („Hip-Hop/Rap“, „Dubstep“, „Electro“) -> unser Hauptgenre oder None."""
    if not hint:
        return None
    key = normalize(hint)
    main = _SERVICE.get(key) or _FALLBACK.get(key)
    if not main:
        hit, _ = _lookup(key)
        main = hit[0] if hit else None
    return main


def _family(hint: str | None) -> set[str] | None:
    """Grobes Dienst-Genre -> Familie unserer Hauptgenres (oder None, wenn unbekannt/zu allgemein)."""
    main = service_main(hint)
    return FAMILIES.get(main) if main else None


def services_agree(a: str, b: str) -> bool | None:
    """Passt Dienst-Genre a in die Familie von Dienst-Genre b? None = nicht beurteilbar.
    Absichtlich Hauptgenre-in-Familie statt Familien-Überschneidung: „Pop“ und „Electro“ teilen sich
    Synthwave/Hyperpop, sind aber kein gegenseitiger Beleg."""
    ma, fb = service_main(a), _family(b)
    if not ma or fb is None:
        return None
    return ma in fb

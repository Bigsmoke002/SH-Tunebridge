"""Songs plattformübergreifend wiederfinden.

1. ISRC gleich  -> sicherer Treffer (Spotify, Tidal, Apple, Deezer liefern ISRC)
2. sonst Fuzzy-Vergleich von Titel + Künstler + Dauer
   (YouTube/SoundCloud haben keine ISRC und "kreative" Titel wie
   "Artist - Song [Official Video] (OUT NOW)").
Wichtig: Remix/VIP/Edit-Angaben bleiben erhalten – ein "VIP" ist ein anderer Song!
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from rapidfuzz import fuzz

from .models import Track

# Rauschen, das bei YouTube/SoundCloud gern im Titel steht
_NOISE = re.compile(
    r"[\(\[](official\s*(music\s*)?(video|audio|visuali[sz]er)|lyric(s)?\s*video|"
    r"out\s*now|free\s*(download|dl)|hd|hq|4k|premiere|clip officiel)[\)\]]",
    re.I,
)
# \b: „ft“ nur als eigenes Wort – sonst würde aus „Drift Phonk“ „Dri“ und aus „Lift Me Up“ „Li“
_FEAT = re.compile(r"[\(\[]?\s*\b(feat\.?|ft\.?|featuring)\s+[^\)\]\-]+[\)\]]?", re.I)
_VERSION = re.compile(r"\b(remix|vip|edit|bootleg|flip|rework|dub|refix|remaster(ed)?|live|acoustic|extended|radio)\b", re.I)


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = _NOISE.sub(" ", text)
    text = _FEAT.sub(" ", text)
    text = text.replace("&", " and ")
    text = re.sub(r"[^\w\s]", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()


def version_tags(title: str) -> set[str]:
    return {m.group(0).lower() for m in _VERSION.finditer(title)}


@dataclass
class Match:
    candidate: Track
    score: float  # 0..100
    reason: str


def score(src: Track, cand: Track) -> Match:
    if src.isrc and cand.isrc and src.isrc.upper() == cand.isrc.upper():
        return Match(cand, 100.0, "isrc")

    t = fuzz.token_set_ratio(normalize(src.title), normalize(cand.title))
    a = fuzz.token_set_ratio(normalize(src.artist), normalize(cand.artist))
    # YouTube: Künstler steht oft nur im Titel ("Artist - Song")
    combined = fuzz.token_set_ratio(
        normalize(f"{src.artist} {src.title}"), normalize(f"{cand.artist} {cand.title}")
    )
    s = max(0.55 * t + 0.45 * a, combined * 0.95)

    # Remix vs. Original nicht verwechseln
    if version_tags(src.title) != version_tags(cand.title):
        s -= 15

    if src.duration_ms and cand.duration_ms:
        diff = abs(src.duration_ms - cand.duration_ms) / 1000
        if diff <= 3:
            s += 5
        elif diff > 20:
            s -= min(25, diff / 4)

    return Match(cand, max(0.0, min(99.0, s)), "fuzzy")


def best_match(src: Track, candidates: list[Track], threshold: float = 80) -> Match | None:
    """Bester Kandidat oder None, wenn nichts sicher genug ist (-> manuell prüfen)."""
    if not candidates:
        return None
    best = max((score(src, c) for c in candidates), key=lambda m: m.score)
    return best if best.score >= threshold else None

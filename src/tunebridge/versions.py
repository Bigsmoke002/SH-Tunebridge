"""Slowed-/Sped-up-/Nightcore-Versionen erkennen.

Solche Uploads („Song (Slowed + Reverb)“, Künstler „xyz, slowed“) haben selbst kaum Tags oder
ähnliche Songs. Für Genre, Hörprobe und Empfehlungen nehmen wir deshalb das Original
und zeigen die Version nur als Hinweis an.
"""

from __future__ import annotations

import re

_PARTS = (
    r"super\s*slowed|ultra\s*slowed|slowed(?:\s*(?:\+|&|and|n|x|/)?\s*reverb(?:ed)?)?(?:\s*(?:\+|&|and)\s*bass\s*boosted)?"
    r"|reverb(?:ed)?(?:\s*(?:\+|&|and)\s*slowed)?|sped\s*up|speed\s*up|nightcore|daycore|8d(?:\s*audio)?"
    r"|bass\s*boosted|tiktok\s*version|pitched(?:\s*(?:up|down))?"
)
# „(Slowed + Reverb)“, „[sped up]“, „- slowed“, „| nightcore“
_IN_TITLE = re.compile(rf"\s*(?:[\(\[]\s*(?:{_PARTS})(?:\s*(?:version|ver\.?|edit|remix|mix))?\s*[\)\]]"
                       rf"|\s[-–|~]\s*(?:{_PARTS})(?:\s*(?:version|ver\.?))?\s*$)", re.I)
_BARE = re.compile(rf"^(?:{_PARTS})$", re.I)
_LABEL = [
    (re.compile(r"super\s*slowed|ultra\s*slowed", re.I), "Super Slowed"),
    (re.compile(r"slowed|reverb|daycore", re.I), "Slowed + Reverb"),
    (re.compile(r"sped\s*up|speed\s*up|pitched\s*up", re.I), "Sped Up"),
    (re.compile(r"nightcore", re.I), "Nightcore"),
    (re.compile(r"8d", re.I), "8D Audio"),
    (re.compile(r"bass\s*boosted", re.I), "Bass Boosted"),
]


def _label(text: str) -> str | None:
    return next((name for rx, name in _LABEL if rx.search(text)), None)


def split_version(title: str, artists: list[str]) -> tuple[str, list[str], str | None]:
    """-> (Originaltitel, Original-Künstler, Versionsname oder None)."""
    found = None
    clean = title or ""
    for m in list(_IN_TITLE.finditer(clean)):
        found = found or _label(m.group(0))
    clean = _IN_TITLE.sub("", clean).strip() or title
    arts = []
    for a in artists or []:
        # „Künstler, slowed“ / „slowed“ als eigener Künstler / „Künstler (slowed)“
        parts = [p.strip() for p in re.split(r",|\s+x\s+|\s+&\s+", a)]
        keep = [p for p in parts if p and not _BARE.match(p)]
        if len(keep) < len(parts):
            found = found or _label(a)
        a2 = _IN_TITLE.sub("", ", ".join(keep)).strip() if keep else ""
        if a2 != ", ".join(keep):
            found = found or _label(", ".join(keep))
        if a2:
            arts.append(a2)
    return clean, arts or list(artists or []), found


def speed_label(factor: float) -> str:
    """Abspielfaktor der Aufnahme relativ zum Original (0.85 = 85 % Tempo)."""
    return f"{'Slowed' if factor < 1 else 'Sped Up'} (~{round(factor * 100)} % Tempo)"


_SPLIT = re.compile(r"\s*(?:/|,|&|\s+x\s+|\s+feat\.?\s+|\s+ft\.?\s+|\s+vs\.?\s+)\s*", re.I)


def main_artist(artist: str) -> str:
    """„trapeia/entris“ -> „trapeia“, „A & B“ -> „A“ (für Nachschlagen bei Last.fm & Co.)."""
    first = _SPLIT.split(artist or "")[0].strip()
    return first or artist

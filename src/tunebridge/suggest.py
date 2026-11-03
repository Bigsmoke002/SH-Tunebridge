"""Welche Playlist passt am besten zu einem Song?

Profil je Playlist: Verteilung von Genre/Subgenre, Künstler und Tags ihrer Songs.
Dazu zählt der Playlist-Name (z.B. "Liquid Vibes" -> DnB/Liquid), damit auch
neue/leere Playlists vorgeschlagen werden.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass

from .genres.classify import _INDEX
from .matching import normalize
from .models import Playlist, Track


@dataclass
class Suggestion:
    playlist: str
    score: float  # 0..1
    reason: str
    new: bool = False
    origin: str = "lokal"


def _name_hint(name: str) -> tuple[str | None, str | None]:
    n = f" {normalize(name)} "
    best = None
    for alias, (g, s, _niche) in _INDEX.items():
        if g and len(alias) > 2 and f" {alias} " in n and (best is None or len(alias) > len(best[0])):
            best = (alias, (g, s))
    return best[1] if best else (None, None)


def _cos(a: dict[str, float], b: dict[str, float]) -> float:
    dot = sum(v * b.get(k, 0) for k, v in a.items())
    na, nb = math.sqrt(sum(v * v for v in a.values())), math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0


def score_playlist(track: Track, pl: Playlist) -> tuple[float, str]:
    n = len(pl.tracks)
    reasons, s = [], 0.0
    if n:
        genres = Counter(t.genre for t in pl.tracks if t.genre)
        subs = Counter((t.genre, t.subgenre) for t in pl.tracks if t.subgenre)
        artists = Counter(a.lower() for t in pl.tracks for a in t.artists)
        tags: Counter = Counter()
        for t in pl.tracks:
            tags.update(t.tags)
        if track.genre and genres:
            g = genres[track.genre] / sum(genres.values())
            s += 0.30 * g
            if g > 0.3:
                reasons.append(f"{g:.0%} {track.genre}")
        if track.subgenre and subs:
            sg = subs[(track.genre, track.subgenre)] / sum(subs.values())
            s += 0.35 * sg
            if sg > 0.2:
                reasons.append(f"{sg:.0%} {track.subgenre}")
        hits = [a for a in track.artists if a.lower() in artists]
        if hits:
            s += 0.20
            reasons.append(f"enthält schon {hits[0]}")
        if track.tags and tags:
            c = _cos(track.tags, dict(tags))
            s += 0.15 * c
    g, sub = _name_hint(pl.name)
    if g and g == track.genre:
        bonus = 0.35 if (sub and sub == track.subgenre) else (0.2 if not sub else 0.0)
        if bonus:
            s += bonus
            reasons.append("Name passt")
    return min(1.0, s), ", ".join(reasons)


def suggest(track: Track, playlists: list[Playlist], top: int = 5) -> list[Suggestion]:
    out = []
    for pl in playlists:
        sc, why = score_playlist(track, pl)
        if sc > 0.05:
            out.append(Suggestion(pl.name, round(sc, 2), why, origin=pl.ids.get("source", "lokal")))
    out.sort(key=lambda x: -x.score)
    out = out[:top]
    # Neue Genre-Playlist vorschlagen, wenn nichts richtig passt
    if track.genre and (not out or out[0].score < 0.5):
        name = f"{track.genre} – {track.subgenre}" if track.subgenre else track.genre
        if name not in {s.playlist for s in out}:
            out.append(Suggestion(name, 0.0, "neue Genre-Playlist", new=True))
    return out

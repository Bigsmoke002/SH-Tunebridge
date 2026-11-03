"""Große Playlist -> Genre-Playlists (grob oder nach Subgenre)."""

from __future__ import annotations

from collections import defaultdict

from .models import Playlist, Track

UNSORTED = "Unsortiert"


def split_by_genre(tracks: list[Track], detail: str = "sub", prefix: str = "") -> list[Playlist]:
    """detail="main" -> 'Drum & Bass'; detail="sub" -> 'Drum & Bass – Liquid'."""
    buckets: dict[str, list[Track]] = defaultdict(list)
    for t in tracks:
        if not t.genre:
            name = UNSORTED
        elif detail == "sub" and t.subgenre:
            name = f"{t.genre} – {t.subgenre}"
        else:
            name = t.genre
        buckets[prefix + name].append(t)
    return [Playlist(name=n, tracks=ts) for n, ts in sorted(buckets.items(), key=lambda kv: -len(kv[1]))]

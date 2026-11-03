"""Plattformunabhängiges Datenmodell.

Jede Übertragung läuft über dieses Format:
  Quelle --export--> Snapshot (JSON) --match--> Ziel --import-->
So kann man jederzeit nachsehen/korrigieren, was übertragen wird.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class Track:
    title: str
    artists: list[str]
    album: str | None = None
    duration_ms: int | None = None
    isrc: str | None = None  # wichtigster Schlüssel für exakten Abgleich
    # IDs je Plattform, z.B. {"spotify": "3n3Ppam7vgaVa1iaRUc9Lp"}
    ids: dict[str, str] = field(default_factory=dict)
    # Genre-Infos (werden von `classify` gefüllt)
    tags: dict[str, float] = field(default_factory=dict)
    genre: str | None = None
    subgenre: str | None = None
    niche: str | None = None  # spezifischstes Genre aus dem großen Katalog („Dariacore“)
    # Anzeige
    cover: str | None = None
    preview_url: str | None = None

    @property
    def artist(self) -> str:
        return ", ".join(self.artists)

    def __str__(self) -> str:
        return f"{self.artist} – {self.title}"


@dataclass
class Playlist:
    name: str
    tracks: list[Track] = field(default_factory=list)
    description: str = ""
    ids: dict[str, str] = field(default_factory=dict)


@dataclass
class Library:
    """Kompletter Export eines Kontos: alle Playlists + Likes/Favoriten."""

    source: str
    playlists: list[Playlist] = field(default_factory=list)
    liked: list[Track] = field(default_factory=list)

    def save(self, path: Path) -> None:
        """Export als JSON – ohne Cover- und Hörproben-Adressen (die gehören den Anbietern und werden
        bei Bedarf frisch nachgeschlagen; Exportdateien sollen nur die eigene Songliste enthalten)."""
        def strip(t: dict) -> dict:
            return {k: v for k, v in t.items() if k not in ("cover", "preview_url")}
        d = asdict(self)
        d["liked"] = [strip(t) for t in d["liked"]]
        for p in d["playlists"]:
            p["tracks"] = [strip(t) for t in p.get("tracks", [])]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "Library":
        raw = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            source=raw["source"],
            playlists=[
                Playlist(
                    name=p["name"],
                    description=p.get("description", ""),
                    ids=p.get("ids", {}),
                    tracks=[Track(**t) for t in p["tracks"]],
                )
                for p in raw["playlists"]
            ],
            liked=[Track(**t) for t in raw["liked"]],
        )

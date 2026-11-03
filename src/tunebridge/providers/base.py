"""Gemeinsame Schnittstelle für alle Streaming-Dienste."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import Library, Playlist, Track


class NotImplementedYet(NotImplementedError):
    pass


class Provider(ABC):
    #: Kurzname, z.B. "spotify"
    name: str
    #: Liefert die Plattform ISRCs? (dann ist der Abgleich fast immer exakt)
    has_isrc: bool = False

    @abstractmethod
    def login(self) -> None:
        """Anmeldung (OAuth o.ä.), Token in data/tokens/<name>.json ablegen."""

    # --- lesen ---------------------------------------------------------
    @abstractmethod
    def playlists(self) -> list[Playlist]: ...

    @abstractmethod
    def liked(self) -> list[Track]: ...

    @abstractmethod
    def search(self, track: Track, limit: int = 5) -> list[Track]:
        """Kandidaten für einen Song suchen (ISRC zuerst, sonst Text)."""

    # --- schreiben -----------------------------------------------------
    @abstractmethod
    def create_playlist(self, name: str, description: str = "") -> str:
        """Legt Playlist an, gibt deren ID zurück."""

    @abstractmethod
    def add_to_playlist(self, playlist_id: str, tracks: list[Track]) -> None: ...

    @abstractmethod
    def like(self, tracks: list[Track]) -> None: ...

    # --- Hilfen --------------------------------------------------------
    def export(self) -> Library:
        return Library(source=self.name, playlists=self.playlists(), liked=self.liked())

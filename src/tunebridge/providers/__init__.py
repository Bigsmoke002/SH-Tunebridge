"""Plattform-Registry."""

from __future__ import annotations

from .base import Provider

# id -> (Name, Status/Hinweis, verfügbar?)
PROVIDERS: dict[str, tuple[str, str, bool]] = {
    "tidal": ("TIDAL", "Login im Browser bestätigen – kein Entwickler-Key nötig.", True),
    "spotify": ("Spotify", "Offizielle API mit deiner eigenen Spotify-App (Client-ID, App-Besitzer braucht Premium). "
                "Nur eigene Playlists lesbar.", True),
    "youtube": ("YouTube / YouTube Music", "Google-Login über die offizielle YouTube Data API mit deiner eigenen "
                "OAuth-App (Desktop-App). Playlists und „Mag ich“ lesen; Übertragen nach extra Freigabe (ca. 60–70 Songs/Tag).", True),
    "soundcloud": ("SoundCloud", "Login über die offizielle SoundCloud API mit deiner eigenen App (Artist Pro nötig). "
                   "Playlists und Likes lesen, private Playlists anlegen.", True),
    "apple": ("Apple Music", "Offiziell nur mit Apple Developer Program (99 $/Jahr).", False),
}

__all__ = ["PROVIDERS", "Provider", "get_provider"]
_instances: dict[str, Provider] = {}


def get_provider(name: str) -> Provider:
    if name not in PROVIDERS or not PROVIDERS[name][2]:
        raise NotImplementedError(f"{PROVIDERS.get(name, (name,))[0]} ist noch nicht angebunden.")
    if name not in _instances:
        if name == "tidal":
            from .tidal import Tidal
            _instances[name] = Tidal()
        elif name == "spotify":
            from .spotify import Spotify
            _instances[name] = Spotify()
        elif name == "youtube":
            from .youtube import YouTube
            _instances[name] = YouTube()
        elif name == "soundcloud":
            from .soundcloud import SoundCloud
            _instances[name] = SoundCloud()
    return _instances[name]

"""SH-Tunebridge (Paket: tunebridge) – Playlists & Likes zwischen Streaming-Diensten übertragen,
Songs nach (Sub-)Genre einordnen und passende neue Songs finden."""

try:
    from importlib.metadata import version as _version

    __version__ = _version("tunebridge")
except Exception:  # pragma: no cover
    __version__ = "0.0.0"

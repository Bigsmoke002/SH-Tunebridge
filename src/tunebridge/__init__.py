"""SH-Tunebridge (Paket: tunebridge) – Playlists & Likes zwischen Streaming-Diensten übertragen,
Songs nach (Sub-)Genre einordnen und passende neue Songs finden."""


def _find_version() -> str:
    """Die eine maßgebliche Versionsnummer für die ganze App (Status, Updater, Debug-Bericht, Sicherungen …).

    Läuft das Paket aus dem Quellordner (Entwickler-/editable-Installation), zählt pyproject.toml – die
    Paket-Metadaten stammen dann vom ersten Installieren und veralten (sonst meldet die App z. B. 0.10.2,
    obwohl 0.13.0 läuft). Sonst (AppImage, Windows, macOS, uv tool) gelten die Metadaten."""
    import re
    from pathlib import Path

    try:
        py = Path(__file__).resolve().parents[2] / "pyproject.toml"
        if py.is_file():
            text = py.read_text(encoding="utf-8")
            if re.search(r'^name\s*=\s*"tunebridge"', text, re.M):
                m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.M)
                if m:
                    return m.group(1)
    except OSError:  # pragma: no cover
        pass
    try:
        from importlib.metadata import version

        return version("tunebridge")
    except Exception:  # pragma: no cover
        return "0.0.0"


__version__ = _find_version()

"""Konfiguration – gleich auf jedem Rechner.

Schlüssel/Tokens:  ~/.config/tunebridge/config.env   (KEY=wert, eine Zeile pro Eintrag)
                   (zusätzlich wird ein .env im Projektordner gelesen – praktisch beim Entwickeln)
Daten (DB, Cache, Exporte): $TUNEBRIDGE_DATA, sonst ~/.local/share/tunebridge
"""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
from .osutil import config_dir, data_dir  # noqa: E402

CONFIG_DIR = config_dir()
CONFIG_FILE = CONFIG_DIR / "config.env"


def _load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            if v.strip():
                os.environ.setdefault(k.strip(), v.strip().strip('"'))


_load_env(CONFIG_FILE)
_load_env(ROOT / ".env")

DATA = data_dir()
DATA.mkdir(parents=True, exist_ok=True)


def private(path: Path, mode: int = 0o600) -> None:
    """Nur für den eigenen Benutzer lesbar machen (Linux/macOS; unter Windows regeln das die Benutzerordner)."""
    if os.name != "posix":
        return
    try:
        if path.exists() and path.stat().st_uid == os.getuid() and (path.stat().st_mode & 0o777) != mode:
            path.chmod(mode)
    except OSError:
        pass


private(DATA, 0o700)   # Datenbank, Tokens, Sicherungs-Schlüssel: andere Benutzer des Rechners haben hier nichts zu suchen


def opt(key: str) -> str | None:
    return os.environ.get(key) or None


def get(key: str) -> str:
    val = opt(key)
    if not val:
        raise SystemExit(f"{key} fehlt – bitte in {CONFIG_FILE} eintragen (Vorlage: config.env.example)")
    return val


def set_value(key: str, value: str) -> None:
    """Schreibt KEY=wert in config.env (Kommentare/Reihenfolge bleiben erhalten)."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    lines = CONFIG_FILE.read_text(encoding="utf-8").splitlines() if CONFIG_FILE.exists() else []
    for i, line in enumerate(lines):
        if line.split("=", 1)[0].strip() == key and not line.lstrip().startswith("#"):
            lines[i] = f"{key}={value}"
            break
    else:
        lines.append(f"{key}={value}")
    CONFIG_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    CONFIG_FILE.chmod(0o600)
    if value:
        os.environ[key] = value
    else:
        os.environ.pop(key, None)

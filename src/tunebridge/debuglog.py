"""Debug-Protokoll – damit Nutzer bei Problemen einen aussagekräftigen Bericht schicken können.

* Standardmäßig AUS. Ein-/Ausschalter in den Einstellungen (gilt pro Rechner).
* Nur lokal: <Daten>/logs/debug.log, max. 3 × 2 MB, ältere Teile werden überschrieben.
* Nichts wird automatisch verschickt. „Debug-Bericht speichern“ legt eine Textdatei in den
  Download-Ordner; die schickt der Nutzer selbst (z. B. als Anhang an ein GitHub-Issue).
* Geschwärzt werden: alle Schlüssel/Tokens aus config.env, Benutzername, Rechnername, Home-Pfad.
  Songtitel, Tags und Gerätenamen bleiben drin – genau die braucht man zur Fehlersuche.
"""

from __future__ import annotations

import getpass
import json
import logging
import os
import platform
import re
import socket
import subprocess
import sys
import time
import traceback
from logging.handlers import RotatingFileHandler
from pathlib import Path

from . import config

LOG_DIR = config.DATA / "logs"
LOG_FILE = LOG_DIR / "debug.log"
_KEY = "debug"
log = logging.getLogger("tunebridge")
log.propagate = False
_handler: RotatingFileHandler | None = None
_enabled: bool | None = None


# ------------------------------------------------------------------ Schalter
def _meta_key() -> str:
    from . import store
    return f"{_KEY}:{store.HOST}"


def enabled() -> bool:
    global _enabled
    if _enabled is None:
        from . import store
        try:
            raw = store.meta_get(_meta_key())
            _enabled = bool(raw and json.loads(raw).get("enabled"))
        except Exception:
            _enabled = False
        _apply()
    return _enabled


def set_enabled(on: bool) -> dict:
    global _enabled
    from . import store
    store.meta_set(_meta_key(), json.dumps({"enabled": bool(on), "since": time.time() if on else None}))
    _enabled = bool(on)
    _apply()
    if on:
        event("debug", "Debug-Protokoll eingeschaltet", **system_info())
    return status()


def _apply() -> None:
    global _handler
    if _enabled and _handler is None:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        _handler = RotatingFileHandler(LOG_FILE, maxBytes=2_000_000, backupCount=2, encoding="utf-8")
        _handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-5s %(message)s", "%Y-%m-%d %H:%M:%S"))
        log.addHandler(_handler)
        log.setLevel(logging.DEBUG)
        os.chmod(LOG_FILE, 0o600)
    elif not _enabled and _handler is not None:
        log.removeHandler(_handler)
        _handler.close()
        _handler = None
        log.setLevel(logging.CRITICAL + 1)
    elif not _enabled:
        log.setLevel(logging.CRITICAL + 1)


def status() -> dict:
    files = sorted(LOG_DIR.glob("debug.log*")) if LOG_DIR.exists() else []
    return {"enabled": enabled(), "size": sum(f.stat().st_size for f in files), "path": _redact(str(LOG_FILE))}


def clear() -> None:
    if _handler:
        _handler.acquire()
        try:
            _handler.stream.truncate(0)
            _handler.stream.seek(0)
        finally:
            _handler.release()
    for f in LOG_DIR.glob("debug.log*") if LOG_DIR.exists() else []:
        if f != LOG_FILE or not _handler:
            f.unlink(missing_ok=True)


# ------------------------------------------------------------------ Schreiben
_SECRET_KEY = re.compile(r"KEY|TOKEN|SECRET|PASS|_ID$|HOST|AUTH", re.I)

def _redact(text: str) -> str:
    secrets = []
    if config.CONFIG_FILE.exists():
        for line in config.CONFIG_FILE.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = (x.strip().strip('"') for x in line.split("=", 1))
                # nur echte Geheimnisse/Kennungen – Pfade wie TUNEBRIDGE_DATA bleiben lesbar
                if len(v) >= 6 and _SECRET_KEY.search(k) and not k.endswith("_PATH"):
                    secrets.append(v)
    for v in sorted(set(secrets), key=len, reverse=True):
        text = text.replace(v, "«geschwärzt»")
    home = str(Path.home())
    text = text.replace(home, "~")
    for name, repl in ((getpass.getuser(), "«nutzer»"), (socket.gethostname(), "«rechner»")):
        if name and len(name) >= 3:
            text = re.sub(rf"(?<![\w-]){re.escape(name)}(?![\w-])", repl, text)
    # Tokens in URLs/Parametern
    text = re.sub(r"(?i)(api_key|api_token|token|access_key|signature|secret)=([^&\s\"']+)", r"\1=«geschwärzt»", text)
    return text


def _fmt(v) -> str:
    if isinstance(v, (dict, list, tuple)):
        s = json.dumps(v, ensure_ascii=False, default=str)
    else:
        s = str(v)
    return s if len(s) <= 1500 else s[:1500] + " …"


def event(area: str, msg: str, level: int = logging.INFO, **data) -> None:
    """Ein Eintrag: Bereich, Text, beliebige Zusatzdaten. Tut nichts, wenn Debug aus ist."""
    if not enabled():
        return
    extra = " ".join(f"{k}={_fmt(v)}" for k, v in data.items() if v not in (None, "", [], {}))
    log.log(level, _redact(f"[{area}] {msg}" + (f" | {extra}" if extra else "")))


def problem(area: str, msg: str, **data) -> None:
    """Etwas ist schiefgelaufen oder unvollständig (z. B. „Genre unbekannt“)."""
    event(area, msg, logging.WARNING, **data)


def error(area: str, msg: str, exc: BaseException | None = None, **data) -> None:
    from . import outbox
    outbox.note_error(area, msg, exc)      # nur mit Einwilligung „Fehlerberichte senden“
    if exc is not None:
        data["fehler"] = f"{type(exc).__name__}: {exc}"
        data["traceback"] = "".join(traceback.format_exception(exc))[-4000:]
    event(area, msg, logging.ERROR, **data)


# ------------------------------------------------------------------ Bericht
def _cmd(*args: str) -> str:
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=4).stdout.strip()
    except Exception:
        return ""


def system_info() -> dict:
    from . import __version__
    from .recognize.capture import pipewire_ok
    from .recognize.engines import available

    osr = {}
    try:
        for line in Path("/etc/os-release").read_text(encoding="utf-8").splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                osr[k] = v.strip('"')
    except OSError:
        pass
    from . import osutil
    server = next((ln.split(":", 1)[1].strip() for ln in _cmd("pactl", "info").splitlines()
                   if ln.startswith("Server Name")), "?") if osutil.LINUX else osutil.NAME
    return {
        "version": __version__, "art": "AppImage" if os.environ.get("APPIMAGE") else "uv/Python",
        "system": osr.get("PRETTY_NAME", f"{platform.system()} {platform.version()}"), "kernel": platform.release(),
        "python": sys.version.split()[0], "desktop": os.environ.get("XDG_CURRENT_DESKTOP", "?"),
        "sitzung": os.environ.get("XDG_SESSION_TYPE", "?"), "audio": server, "pipewire_apps": pipewire_ok(),
        "dienste": available(), "lastfm": bool(config.opt("LASTFM_API_KEY")),
    }


def report() -> str:
    """Kompletter Bericht als Text (geschwärzt)."""
    from . import llm, store

    lines = ["SH-Tunebridge – Debug-Bericht", f"Erstellt: {time.strftime('%Y-%m-%d %H:%M:%S')}", "",
             "== System =="]
    lines += [f"{k}: {v}" for k, v in system_info().items()]
    try:
        s = llm.settings()
        lines.append(f"lokales LLM: {'an' if s['enabled'] else 'aus'} · Modell {s.get('model')} · {s.get('device')}")
    except Exception as e:
        lines.append(f"lokales LLM: ? ({e})")
    try:
        lines.append(f"Datenbank: {store.stats()}")
        prefs = json.loads(store.meta_get(f"prefs:{store.HOST}") or "{}")
        lines.append(f"Einstellungen: {json.dumps(prefs, ensure_ascii=False)}")
    except Exception as e:
        lines.append(f"Datenbank: ? ({e})")
    try:
        lines += ["", "== Letzte Erkennungen =="]
        for h in store.history(limit=15):
            t, x = h["track"], h["extra"]
            lines.append(f"{time.strftime('%m-%d %H:%M', time.localtime(h['ts']))} {h['engine']:<14} "
                         f"{', '.join(t['artists'])} – {t['title']} | Genre: {t.get('genre') or 'UNBEKANNT'}"
                         f" / {t.get('subgenre') or '-'} / {t.get('niche') or '-'} ({x.get('genre_source')}, "
                         f"{x.get('confidence')}) {('· ' + x['version']) if x.get('version') else ''}")
    except Exception as e:
        lines.append(f"? ({e})")
    lines += ["", "== Protokoll =="]
    files = sorted(LOG_DIR.glob("debug.log*"), key=lambda p: p.stat().st_mtime) if LOG_DIR.exists() else []
    if not files:
        lines.append("(leer – Debug-Protokoll war nicht eingeschaltet)")
    for f in files:
        lines.append(f.read_text(encoding="utf-8", errors="replace"))
    return _redact("\n".join(lines))


def downloads_dir() -> Path:
    from .osutil import downloads_dir as _d
    return _d()


def export() -> Path:
    out = downloads_dir() / f"SH-Tunebridge-Debug-{time.strftime('%Y%m%d-%H%M%S')}.txt"
    out.write_text(report(), encoding="utf-8")
    os.chmod(out, 0o600)
    return out

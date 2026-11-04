"""Last.fm-Login über die offizielle Web-Anmeldung (last.fm/api/webauth).

Ablauf: Browser öffnet last.fm/api/auth mit deinem API-Key → du erlaubst den Zugriff → Last.fm schickt den
Browser mit einem Einmal-Token zurück an SH-Tunebridge (127.0.0.1) → daraus wird mit API-Key und Shared Secret
(beides aus DEINEM Last.fm-API-Konto) ein Sitzungsschlüssel. Dein Passwort sieht SH-Tunebridge nie.
Gespeichert wird nur der Sitzungsschlüssel und dein Benutzername in <Daten>/tokens/lastfm.json (nur für dich lesbar).
Kein Server dazwischen.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import time
from urllib.parse import urlencode

import httpx

from . import config

API = "https://ws.audioscrobbler.com/2.0/"
AUTH_URL = "https://www.last.fm/api/auth/"


class LastfmError(RuntimeError):
    pass


def callback_base() -> str:
    port = os.environ.get("TUNEBRIDGE_PORT") or "8765"
    return f"http://127.0.0.1:{port}/api/lastfm/callback"


def sign(params: dict, secret: str) -> str:
    """Last.fm-Signatur: Parameter alphabetisch, Name+Wert aneinander, Secret dran, MD5 (format/callback zählen nicht)."""
    raw = "".join(f"{k}{params[k]}" for k in sorted(params) if k not in ("format", "callback"))
    return hashlib.md5((raw + secret).encode("utf-8")).hexdigest()


class LastfmLogin:
    def __init__(self):
        self._login: dict = {}

    @staticmethod
    def _path():
        return config.DATA / "tokens" / "lastfm.json"

    def session(self) -> dict:
        try:
            return json.loads(self._path().read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def configured(self) -> bool:
        return bool(config.opt("LASTFM_API_KEY") and config.opt("LASTFM_SHARED_SECRET"))

    def login(self) -> dict:
        if not self.configured():
            raise LastfmError("Für die Anmeldung fehlen API key und Shared secret deines Last.fm-API-Kontos – "
                              "bitte die Einrichtung durchgehen.")
        state = secrets.token_urlsafe(16)
        url = AUTH_URL + "?" + urlencode({"api_key": config.opt("LASTFM_API_KEY"), "cb": f"{callback_base()}/{state}"})
        self._login = {"state": "waiting", "url": url, "csrf": state, "expires": time.time() + 600}
        return {"state": "waiting", "url": url}

    def login_state(self) -> dict:
        st = {k: v for k, v in self._login.items() if k in ("state", "url", "error")} or {"state": "idle"}
        if st.get("state") == "waiting" and time.time() > self._login.get("expires", 0):
            st["state"] = "expired"
        return st

    def finish_login(self, token: str, state: str) -> str:
        """Einmal-Token gegen Sitzungsschlüssel tauschen. Gibt den Last.fm-Benutzernamen zurück."""
        if not self._login or not secrets.compare_digest(state, self._login.get("csrf", "")) \
                or time.time() > self._login.get("expires", 0):
            raise LastfmError("Anmeldung abgelaufen oder ungültig – bitte erneut anmelden")
        if not token:
            raise LastfmError("Last.fm hat keinen Anmelde-Token geschickt")
        key, secret = config.opt("LASTFM_API_KEY") or "", config.opt("LASTFM_SHARED_SECRET") or ""
        params = {"method": "auth.getSession", "api_key": key, "token": token}
        try:
            r = httpx.get(API, timeout=20, params={**params, "api_sig": sign(params, secret), "format": "json"})
            d = r.json()
        except (httpx.HTTPError, ValueError) as e:
            self._login = {"state": "failed", "error": "Last.fm nicht erreichbar"}
            raise LastfmError("Last.fm nicht erreichbar – bitte später erneut") from e
        if "error" in d or "session" not in d:
            msg = d.get("message") or "unbekannter Fehler"
            if d.get("error") in (4, 13, 26):     # 4 = Auth/Token, 13 = Signatur, 26 = Key gesperrt
                msg = (f"{msg} – meist ist das Shared secret falsch kopiert (oder mit dem API key vertauscht). "
                       "Bitte „Einrichtung ändern“ und beide Werte neu kopieren.")
            self._login = {"state": "failed", "error": f"Last.fm: {msg}"}
            raise LastfmError(f"Last.fm: {msg}")
        s = d["session"]
        p = self._path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"name": s["name"], "key": s["key"], "since": time.time()}))
        os.chmod(p, 0o600)
        self._login = {"state": "connected"}
        return s["name"]

    def fail_login(self, msg: str) -> None:
        self._login = {"state": "failed", "error": msg}

    def logout(self) -> None:
        self._path().unlink(missing_ok=True)
        self._login = {}


LOGIN = LastfmLogin()

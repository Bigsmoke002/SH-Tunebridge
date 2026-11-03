"""Gemeinsamer OAuth-Login (Autorisierungscode + PKCE) für Dienste mit eigener App des Nutzers.

Der Nutzer legt beim Dienst selbst eine App an und trägt deren Client-ID (und – wo der Dienst es verlangt –
das Client-Secret) in SH-Tunebridge ein. Angemeldet wird im Browser beim Dienst; SH-Tunebridge sieht das
Passwort nie. Die Rückleitung landet auf diesem Rechner (http://127.0.0.1:8765/api/oauth/<dienst>/callback).
Token liegen in <Daten>/tokens/<dienst>.json (nur für dich lesbar). Kein Server dazwischen.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import time
from urllib.parse import urlencode

import httpx

from .. import config
from ..models import Playlist, Track
from .base import Provider


class OAuthError(RuntimeError):
    pass


class OAuthProvider(Provider):
    name = ""
    title = ""
    AUTH_URL = ""
    TOKEN_URL = ""
    SCOPES = ""
    CLIENT_ID_KEY = ""
    CLIENT_SECRET_KEY = ""          # leer = Dienst braucht kein Secret
    SECRET_REQUIRED = False
    EXTRA_AUTH: dict = {}

    def __init__(self):
        self.tok: dict = {}
        self._login: dict = {}
        self._acc: str | None = None
        p = self._path()
        if p.exists():
            try:
                self.tok = json.loads(p.read_text(encoding="utf-8"))
            except ValueError:
                self.tok = {}

    # ------------------------------------------------------------ Einstellungen
    @classmethod
    def redirect(cls) -> str:
        port = os.environ.get("TUNEBRIDGE_PORT") or "8765"
        return f"http://127.0.0.1:{port}/api/oauth/{cls.name}/callback"

    def _path(self):
        return config.DATA / "tokens" / f"{self.name}.json"

    def client_id(self) -> str | None:
        return config.opt(self.CLIENT_ID_KEY)

    def client_secret(self) -> str | None:
        return config.opt(self.CLIENT_SECRET_KEY) if self.CLIENT_SECRET_KEY else None

    def configured(self) -> bool:
        return bool(self.client_id()) and (not self.SECRET_REQUIRED or bool(self.client_secret()))

    def _save(self) -> None:
        p = self._path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.tok))
        os.chmod(p, 0o600)

    def _client_auth(self) -> dict:
        d = {"client_id": self.client_id()}
        if self.client_secret():
            d["client_secret"] = self.client_secret()
        return d

    # ------------------------------------------------------------ Login
    def login(self) -> dict:
        if not self.configured():
            raise OAuthError(f"Bitte zuerst die Client-ID{' und das Client-Secret' if self.SECRET_REQUIRED else ''} "
                             f"deiner {self.title}-App eintragen")
        verifier = secrets.token_urlsafe(64)[:100]
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        state = secrets.token_urlsafe(16)
        url = self.AUTH_URL + "?" + urlencode({
            "client_id": self.client_id(), "response_type": "code", "redirect_uri": self.redirect(),
            **({"scope": self.SCOPES} if self.SCOPES else {}), "code_challenge_method": "S256",
            "code_challenge": challenge, "state": state, **self.EXTRA_AUTH})
        self._login = {"state": "waiting", "url": url, "verifier": verifier, "csrf": state,
                       "expires": time.time() + 600}
        return {"state": "waiting", "url": url}

    def finish_login(self, code: str, state: str) -> None:
        if not self._login or state != self._login.get("csrf") or time.time() > self._login.get("expires", 0):
            raise OAuthError("Anmeldung abgelaufen oder ungültig – bitte erneut verbinden")
        r = httpx.post(self.TOKEN_URL, timeout=20, headers={"Accept": "application/json"}, data={
            "grant_type": "authorization_code", "code": code, "redirect_uri": self.redirect(),
            "code_verifier": self._login["verifier"], **self._client_auth()})
        if r.status_code >= 400:
            self._login.update(state="failed", error=r.text[:200])
            raise OAuthError(f"{self.title} lehnt ab: {r.text[:200]}")
        d = r.json()
        self.tok = {"access_token": d["access_token"], "refresh_token": d.get("refresh_token"),
                    "expires": time.time() + int(d.get("expires_in") or 3600) - 60}
        self._save()
        self._acc = None
        self._login = {"state": "connected"}

    def fail_login(self, msg: str) -> None:
        self._login.update(state="failed", error=msg)

    def login_state(self) -> dict:
        st = {k: v for k, v in self._login.items() if k in ("state", "url", "error")} or {"state": "idle"}
        if st.get("state") == "waiting" and time.time() > self._login.get("expires", 0):
            st["state"] = "expired"
        return st

    def logout(self) -> None:
        self._path().unlink(missing_ok=True)
        self.tok, self._login, self._acc = {}, {}, None

    def _access(self) -> str:
        if not self.tok.get("access_token"):
            raise OAuthError(f"{self.title} ist nicht verbunden")
        if time.time() > self.tok.get("expires", 0):
            if not self.tok.get("refresh_token"):
                raise OAuthError(f"{self.title}-Anmeldung abgelaufen – bitte neu verbinden")
            r = httpx.post(self.TOKEN_URL, timeout=20, headers={"Accept": "application/json"}, data={
                "grant_type": "refresh_token", "refresh_token": self.tok["refresh_token"], **self._client_auth()})
            if r.status_code >= 400:
                raise OAuthError(f"{self.title}-Anmeldung abgelaufen – bitte neu verbinden")
            d = r.json()
            self.tok.update(access_token=d["access_token"], expires=time.time() + int(d.get("expires_in") or 3600) - 60,
                            refresh_token=d.get("refresh_token") or self.tok["refresh_token"])   # SoundCloud: nur einmal gültig
            self._save()
        return self.tok["access_token"]

    def connected(self) -> bool:
        if not self.tok.get("access_token") or not self.configured():
            return False
        try:
            return bool(self.account())
        except Exception:  # noqa: BLE001
            return False

    # ------------------------------------------------------------ Schreiben: (noch) nicht angeboten
    def search(self, track: Track, limit: int = 5) -> list[Track]:
        raise NotImplementedError(f"{self.title}: Suchen/Übertragen ist (noch) nicht angebunden – nur Lesen")

    def find(self, track: Track) -> Track | None:
        raise NotImplementedError(f"{self.title}: Übertragen ist (noch) nicht angebunden – nur Lesen")

    def create_playlist(self, name: str, description: str = "") -> str:
        raise NotImplementedError(f"{self.title}: Playlists anlegen ist nicht angebunden – nur Lesen")

    def add_to_playlist(self, playlist_id: str, tracks: list[Track]) -> None:
        raise NotImplementedError(f"{self.title}: nur Lesen")

    def like(self, tracks: list[Track]) -> None:
        raise NotImplementedError(f"{self.title}: nur Lesen")

    def playlists(self) -> list[Playlist]:
        return [Playlist(name=p["name"], tracks=self.playlist_tracks(p["id"]), ids={self.name: p["id"]})
                for p in self.playlist_list()]

    # von Unterklassen: account(), playlist_list(), playlist_tracks(pid), liked(), liked_count()

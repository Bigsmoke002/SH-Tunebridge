"""Spotify über die offizielle Web API – mit deiner eigenen (kostenlosen) Spotify-App.

Warum eine eigene App? Spotify lässt Drittprogramme nur so zu (Development Mode). Seit Februar 2026 gilt:
* Der App-Besitzer braucht Spotify Premium, höchstens 5 Nutzer pro App.
* Playlist-Inhalte gibt es nur für eigene oder gemeinsam bearbeitete Playlists.
* Neue Pfade: /me/playlists, /playlists/{id}/items, /me/library (siehe Spotify-Migrationsleitfaden).

Login: OAuth mit PKCE – kein Client-Secret nötig. Du meldest dich auf accounts.spotify.com selbst an;
SH-Tunebridge sieht dein Passwort nie. Token in <Daten>/tokens/spotify.json (nur für dich lesbar).
Einrichtung: developer.spotify.com/dashboard → „Create app“ → Redirect-URI
  http://127.0.0.1:8765/api/spotify/callback  eintragen → „Web API“ anhaken → Client-ID kopieren.
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
from ..matching import best_match
from ..models import Playlist, Track
from .base import Provider

API = "https://api.spotify.com/v1"
REDIRECT = "http://127.0.0.1:8765/api/spotify/callback"
SCOPES = ("playlist-read-private playlist-read-collaborative user-library-read user-library-modify "
          "playlist-modify-private playlist-modify-public")
_TOKEN = lambda: config.DATA / "tokens" / "spotify.json"  # noqa: E731


class SpotifyError(RuntimeError):
    pass


def to_track(t: dict) -> Track:
    alb = t.get("album") or {}
    imgs = alb.get("images") or []
    return Track(title=t.get("name") or "", artists=[a["name"] for a in t.get("artists") or [] if a.get("name")],
                 album=alb.get("name"), duration_ms=t.get("duration_ms"),
                 isrc=(t.get("external_ids") or {}).get("isrc"), ids={"spotify": t["id"]} if t.get("id") else {},
                 cover=imgs[0]["url"] if imgs else None, preview_url=t.get("preview_url"))


class Spotify(Provider):
    name = "spotify"
    title = "Spotify"
    has_isrc = True

    def __init__(self):
        self.tok: dict = {}
        self._login: dict = {}
        p = _TOKEN()
        if p.exists():
            try:
                self.tok = json.loads(p.read_text(encoding="utf-8"))
            except ValueError:
                self.tok = {}

    # ------------------------------------------------------------ Login
    @staticmethod
    def client_id() -> str | None:
        return config.opt("SPOTIFY_CLIENT_ID")

    def _save(self) -> None:
        p = _TOKEN()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.tok))
        os.chmod(p, 0o600)

    def login(self) -> dict:
        cid = self.client_id()
        if not cid:
            raise SpotifyError("Bitte zuerst die Client-ID deiner Spotify-App eintragen")
        verifier = secrets.token_urlsafe(64)[:100]
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        state = secrets.token_urlsafe(16)
        url = "https://accounts.spotify.com/authorize?" + urlencode({
            "client_id": cid, "response_type": "code", "redirect_uri": REDIRECT, "scope": SCOPES,
            "code_challenge_method": "S256", "code_challenge": challenge, "state": state})
        self._login = {"state": "waiting", "url": url, "verifier": verifier, "csrf": state,
                       "expires": time.time() + 600}
        return {"state": "waiting", "url": url}

    def finish_login(self, code: str, state: str) -> None:
        if not self._login or state != self._login.get("csrf") or time.time() > self._login.get("expires", 0):
            raise SpotifyError("Anmeldung abgelaufen oder ungültig – bitte erneut verbinden")
        r = httpx.post("https://accounts.spotify.com/api/token", timeout=20, data={
            "grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT,
            "client_id": self.client_id(), "code_verifier": self._login["verifier"]})
        if r.status_code >= 400:
            self._login["state"] = "failed"
            raise SpotifyError(f"Spotify lehnt ab: {r.text[:200]}")
        d = r.json()
        self.tok = {"access_token": d["access_token"], "refresh_token": d.get("refresh_token"),
                    "expires": time.time() + d.get("expires_in", 3600) - 60}
        self._save()
        self._login = {"state": "connected"}

    def login_state(self) -> dict:
        st = {k: v for k, v in self._login.items() if k in ("state", "url")} or {"state": "idle"}
        if st.get("state") == "waiting" and time.time() > self._login.get("expires", 0):
            st["state"] = "expired"
        return st

    def logout(self) -> None:
        _TOKEN().unlink(missing_ok=True)
        self.tok, self._login = {}, {}

    def _access(self) -> str:
        if not self.tok.get("access_token"):
            raise SpotifyError("Spotify ist nicht verbunden")
        if time.time() > self.tok.get("expires", 0) and self.tok.get("refresh_token"):
            r = httpx.post("https://accounts.spotify.com/api/token", timeout=20, data={
                "grant_type": "refresh_token", "refresh_token": self.tok["refresh_token"],
                "client_id": self.client_id()})
            if r.status_code >= 400:
                raise SpotifyError("Spotify-Anmeldung abgelaufen – bitte neu verbinden")
            d = r.json()
            self.tok.update(access_token=d["access_token"], expires=time.time() + d.get("expires_in", 3600) - 60,
                            refresh_token=d.get("refresh_token") or self.tok["refresh_token"])
            self._save()
        return self.tok["access_token"]

    def _req(self, method: str, path: str, **kw) -> dict:
        for _ in range(3):
            r = httpx.request(method, path if path.startswith("http") else API + path, timeout=30,
                              headers={"Authorization": f"Bearer {self._access()}"}, **kw)
            if r.status_code == 429:
                wait = min(int(r.headers.get("Retry-After", "5")), 30)
                time.sleep(wait)
                continue
            if r.status_code >= 400:
                try:
                    msg = r.json().get("error", {}).get("message")
                except ValueError:
                    msg = r.text[:200]
                if r.status_code == 403:
                    msg = f"{msg} – Spotify erlaubt das im Development Mode nur für eigene Playlists"
                raise SpotifyError(f"Spotify: {msg or r.status_code}")
            return r.json() if r.content else {}
        raise SpotifyError("Spotify: Anfrage-Limit erreicht – bitte später erneut")

    def _pages(self, path: str, **params) -> list[dict]:
        out, url = [], path
        while url:
            d = self._req("GET", url, params=params if url == path else None)
            out += d.get("items", [])
            url = d.get("next")
        return out

    def connected(self) -> bool:
        try:
            return bool(self.tok.get("access_token")) and bool(self._req("GET", "/me").get("id"))
        except Exception:
            return False

    def account(self) -> str | None:
        try:
            me = self._req("GET", "/me")
            return me.get("display_name") or me.get("id")
        except Exception:
            return None

    # ------------------------------------------------------------ Lesen
    def playlist_list(self) -> list[dict]:
        me = self._req("GET", "/me").get("id")
        return [{"id": p["id"], "name": p["name"], "count": (p.get("items") or p.get("tracks") or {}).get("total"),
                 "own": (p.get("owner") or {}).get("id") == me}
                for p in self._pages("/me/playlists", limit=50) if p]

    def playlist_tracks(self, pid: str) -> list[Track]:
        items = self._pages(f"/playlists/{pid}/items", limit=50)
        return [to_track(i.get("item") or i.get("track")) for i in items
                if (i.get("item") or i.get("track") or {}).get("type", "track") == "track"
                and (i.get("item") or i.get("track") or {}).get("id")]

    def playlists(self) -> list[Playlist]:
        return [Playlist(name=p["name"], tracks=self.playlist_tracks(p["id"]), ids={"spotify": p["id"]})
                for p in self.playlist_list() if p["own"]]

    def liked(self) -> list[Track]:
        return [to_track(i["track"]) for i in self._pages("/me/tracks", limit=50) if i.get("track")]

    def liked_count(self) -> int:
        try:
            return self._req("GET", "/me/tracks", params={"limit": 1}).get("total", 0)
        except Exception:
            return 0

    def track(self, tid: str) -> Track:
        return to_track(self._req("GET", f"/tracks/{tid}"))

    def album_tracks(self, aid: str) -> tuple[str, list[Track]]:
        a = self._req("GET", f"/albums/{aid}")
        items = self._pages(f"/albums/{aid}/tracks", limit=50)
        return a.get("name", ""), [to_track({**t, "album": a}) for t in items if t.get("id")]

    def playlist_name(self, pid: str) -> str:
        return self._req("GET", f"/playlists/{pid}", params={"fields": "name"}).get("name", "")

    def search(self, track: Track, limit: int = 10) -> list[Track]:
        q = f"isrc:{track.isrc}" if track.isrc else f"track:{track.title} artist:{(track.artists or [''])[0]}"
        res = self._req("GET", "/search", params={"q": q, "type": "track", "limit": min(limit, 10)})
        hits = [to_track(t) for t in (res.get("tracks") or {}).get("items", []) if t]
        if not hits and track.isrc:
            return self.search(Track(title=track.title, artists=track.artists), limit)
        return hits

    def find(self, track: Track) -> Track | None:
        cands = self.search(track)
        if track.isrc and any(c.isrc == track.isrc for c in cands):
            return next(c for c in cands if c.isrc == track.isrc)
        m = best_match(track, cands, threshold=80)
        return m.candidate if m else None

    # ------------------------------------------------------------ Schreiben
    def create_playlist(self, name: str, description: str = "") -> str:
        return self._req("POST", "/me/playlists", json={
            "name": name, "public": False, "description": description or "Erstellt mit SH-Tunebridge"})["id"]

    def add_to_playlist(self, playlist_id: str, tracks: list[Track]) -> None:
        uris = [f"spotify:track:{t.ids['spotify']}" for t in tracks if t.ids.get("spotify")]
        for i in range(0, len(uris), 100):
            self._req("POST", f"/playlists/{playlist_id}/items", json={"uris": uris[i:i + 100]})

    def like(self, tracks: list[Track]) -> None:
        uris = [f"spotify:track:{t.ids['spotify']}" for t in tracks if t.ids.get("spotify")]
        for i in range(0, len(uris), 40):
            self._req("PUT", "/me/library", params={"uris": ",".join(uris[i:i + 40])})

    def playlist_url(self, pid: str) -> str:
        return f"https://open.spotify.com/playlist/{pid}"

    def track_url(self, tid: str) -> str:
        return f"https://open.spotify.com/track/{tid}"

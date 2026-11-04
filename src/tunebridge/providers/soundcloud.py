"""SoundCloud über die offizielle SoundCloud API – mit deiner eigenen SoundCloud-App (nur Lesen).

Einrichtung (einmalig): SoundCloud lässt seit Mai 2026 Apps per Selbstbedienung anmelden, dafür braucht das
Konto ein Artist-Pro-Abo. developers.soundcloud.com → „Create a new application“ → Redirect-URI
  http://127.0.0.1:8765/api/oauth/soundcloud/callback  eintragen → Client-ID und Client-Secret hier eintragen.
SoundCloud behandelt alle Apps als „vertraulich“, deshalb ist das Secret nötig. Es ist DEIN Secret und bleibt
nur auf deinem Rechner – kein Server dazwischen. Login: OAuth 2.1 mit PKCE auf secure.soundcloud.com.
Gelesen werden deine Playlists und Likes (Titel, Künstler, Cover-Adresse) – nie Musik.
"""

from __future__ import annotations

import httpx

from ..models import Track
from .oauth import OAuthError, OAuthProvider

API = "https://api.soundcloud.com"
MAX_ITEMS = 2000


def to_track(t: dict) -> Track:
    from ..linkimport import split_title
    user = (t.get("user") or {}).get("username") or ""
    pm = t.get("publisher_metadata") or {}
    if pm.get("artist") and t.get("title"):
        artists, title = [pm["artist"]], t["title"]
    else:
        artists, title = split_title(t.get("title") or "", user)
    art = t.get("artwork_url") or (t.get("user") or {}).get("avatar_url")
    if art:
        art = art.replace("-large.", "-t300x300.")
    return Track(title=title, artists=artists, duration_ms=t.get("duration"), isrc=pm.get("isrc") or None,
                 cover=art, ids={"soundcloud": t.get("permalink_url") or str(t.get("id") or "")})


class SoundCloud(OAuthProvider):
    name = "soundcloud"
    title = "SoundCloud"
    AUTH_URL = "https://secure.soundcloud.com/authorize"
    TOKEN_URL = "https://secure.soundcloud.com/oauth/token"
    SCOPES = ""
    CLIENT_ID_KEY = "SOUNDCLOUD_CLIENT_ID"
    CLIENT_SECRET_KEY = "SOUNDCLOUD_CLIENT_SECRET"
    SECRET_REQUIRED = True

    def check_credentials(self) -> None:
        """Client-ID/Secret vorab bei SoundCloud prüfen. Mit falschen Daten zeigt SoundClouds Anmeldeseite nur
        eine leere weiße Seite – deshalb vor dem Öffnen des Browsers klar melden, was nicht stimmt."""
        try:
            r = httpx.post(self.TOKEN_URL, timeout=15, auth=(self.client_id() or "", self.client_secret() or ""),
                           headers={"Accept": "application/json"}, data={"grant_type": "client_credentials"})
        except httpx.HTTPError:
            return                      # SoundCloud nicht erreichbar: Anmeldung trotzdem versuchen
        if r.status_code in (400, 401, 403):
            try:
                err = (r.json() or {}).get("error", "")
            except ValueError:
                err = ""
            if err in ("invalid_client", "unauthorized_client") or r.status_code == 401:
                raise OAuthError("SoundCloud kennt diese Zugangsdaten nicht: Client ID oder Client Secret stimmt nicht "
                                 "(vertauscht, unvollständig kopiert oder Leerzeichen dabei). Bitte in deiner SoundCloud-App "
                                 "neu kopieren – „Einrichtung wiederholen“.")

    def login(self) -> dict:
        if self.configured():
            self.check_credentials()
        return super().login()

    def _get(self, url: str, **params) -> dict | list:
        if not url.startswith("http"):
            url = API + url
        r = httpx.get(url, params=params or None, timeout=20, follow_redirects=True,
                      headers={"Authorization": f"OAuth {self._access()}", "Accept": "application/json; charset=utf-8"})
        if r.status_code == 401:
            raise OAuthError("SoundCloud-Anmeldung abgelaufen – bitte neu verbinden")
        if r.status_code >= 400:
            raise OAuthError(f"SoundCloud: {r.text[:200]}")
        return r.json()

    def _pages(self, path: str, **params) -> list[dict]:
        out: list[dict] = []
        d = self._get(path, linked_partitioning="true", limit=200, **params)
        while True:
            if isinstance(d, list):
                out += d
                break
            out += d.get("collection") or []
            nxt = d.get("next_href")
            if not nxt or len(out) >= MAX_ITEMS:
                break
            d = self._get(nxt)
        return out[:MAX_ITEMS]

    def account(self) -> str | None:
        if self._acc is None:
            me = self._get("/me")
            self._acc = me.get("username") or me.get("full_name") or "SoundCloud-Konto"
        return self._acc

    def playlist_list(self) -> list[dict]:
        out = []
        for p in self._pages("/me/playlists", show_tracks="false"):
            out.append({"id": str(p["id"]), "name": p.get("title") or "", "count": p.get("track_count"),
                        "cover": (p.get("artwork_url") or "").replace("-large.", "-t300x300.") or None, "own": True})
        return out

    def playlist_tracks(self, pid: str) -> list[Track]:
        return [to_track(t) for t in self._pages(f"/playlists/{pid}/tracks") if t.get("title")]

    def liked(self) -> list[Track]:
        return [to_track(t) for t in self._pages("/me/likes/tracks") if t.get("title")]

    def liked_count(self) -> int | None:
        try:
            return self._get("/me").get("public_favorites_count")
        except OAuthError:
            return None

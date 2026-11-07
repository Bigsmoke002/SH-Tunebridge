"""SoundCloud über die offizielle SoundCloud API – mit deiner eigenen SoundCloud-App.

Einrichtung (einmalig): SoundCloud lässt seit Mai 2026 Apps per Selbstbedienung anmelden, dafür braucht das
Konto ein Artist-Pro-Abo. developers.soundcloud.com → „Create a new application“ → Redirect-URI
  http://127.0.0.1:8765/api/oauth/soundcloud/callback  eintragen → Client-ID und Client-Secret hier eintragen.
SoundCloud behandelt alle Apps als „vertraulich“, deshalb ist das Secret nötig. Es ist DEIN Secret und bleibt
nur auf deinem Rechner – kein Server dazwischen. Login: OAuth 2.1 mit PKCE auf secure.soundcloud.com.
Gelesen werden deine Playlists und Likes (Titel, Künstler, Cover-Adresse) – nie Musik.
Übertragen: Songs per Titel/Künstler suchen, private Playlist anlegen oder in eine bestehende eigene Playlist
einfügen (höchstens 500 Songs pro Playlist – Grenze von SoundCloud), Songs liken.
"""

from __future__ import annotations

import httpx

from ..models import Track
from .oauth import OAuthError, OAuthProvider

API = "https://api.soundcloud.com"
MAX_ITEMS = 2000
MAX_PLAYLIST = 500          # SoundCloud nimmt nicht mehr Songs pro Playlist an


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

    def __init__(self):
        super().__init__()
        self._sc_ids: dict[str, int] = {}     # Permalink -> Track-ID (aus Suchtreffern, spart /resolve)
        self._pl_urls: dict[str, str] = {}

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
        return self._req("GET", url, params=params or None)

    def _req(self, method: str, url: str, params: dict | None = None, json: dict | None = None) -> dict | list:
        if not url.startswith("http"):
            url = API + url
        h = {"Authorization": f"OAuth {self._access()}", "Accept": "application/json; charset=utf-8"}
        r = (httpx.get(url, params=params, timeout=30, follow_redirects=True, headers=h) if method == "GET"
             else httpx.request(method, url, params=params, json=json, timeout=30, follow_redirects=True, headers=h))
        if r.status_code == 429:
            raise OAuthError("SoundCloud bittet um eine Pause (zu viele Anfragen) – in ein paar Minuten erneut übertragen")
        if r.status_code == 401:
            raise OAuthError("SoundCloud-Anmeldung abgelaufen – bitte neu verbinden")
        if r.status_code >= 400:
            raise OAuthError(f"SoundCloud: {r.text[:200]}")
        return {} if r.status_code == 204 or not getattr(r, "text", "x") else r.json()

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

    # ------------------------------------------------------------ Übertragen
    def search(self, track: Track, limit: int = 8) -> list[Track]:
        q = f"{', '.join(track.artists[:2])} {track.title}".strip()
        d = self._get("/tracks", q=q, limit=limit, linked_partitioning="true")
        out = []
        for t in (d.get("collection") if isinstance(d, dict) else d) or []:
            if not t.get("title") or not t.get("id"):
                continue
            tr = to_track(t)
            self._sc_ids[tr.ids["soundcloud"]] = int(t["id"])
            out.append(tr)
        return out

    def find(self, track: Track) -> Track | None:
        from ..matching import best_match
        cands = self.search(track)
        if track.isrc and any(c.isrc == track.isrc for c in cands):
            return next(c for c in cands if c.isrc == track.isrc)
        m = best_match(track, cands, threshold=80)
        return m.candidate if m else None

    def _track_id(self, t: Track) -> int | None:
        ref = t.ids.get("soundcloud") or ""
        if not ref:
            return None
        if ref.isdigit():
            return int(ref)
        if ref not in self._sc_ids:
            try:
                d = self._get("/resolve", url=ref)
                self._sc_ids[ref] = int(d["id"]) if isinstance(d, dict) and d.get("id") else 0
            except OAuthError:
                self._sc_ids[ref] = 0
        return self._sc_ids[ref] or None

    def create_playlist(self, name: str, description: str = "") -> str:
        d = self._req("POST", "/playlists", json={"playlist": {
            "title": name[:100], "sharing": "private", "description": description or "Erstellt mit SH-Tunebridge"}})
        pid = str(d["id"])
        if d.get("permalink_url"):
            self._pl_urls[pid] = d["permalink_url"]
        return pid

    def add_to_playlist(self, playlist_id: str, tracks: list[Track]) -> None:
        """SoundCloud ersetzt beim Speichern die ganze Liste – deshalb vorhandene Songs mitschicken, Doppelte weglassen."""
        cur = self._get(f"/playlists/{playlist_id}", show_tracks="true")
        ids = [int(t["id"]) for t in (cur.get("tracks") or []) if t.get("id")] if isinstance(cur, dict) else []
        if isinstance(cur, dict) and cur.get("permalink_url"):
            self._pl_urls[playlist_id] = cur["permalink_url"]
        have = set(ids)
        for t in tracks:
            tid = self._track_id(t)
            if tid and tid not in have:
                ids.append(tid)
                have.add(tid)
        if len(ids) > MAX_PLAYLIST:
            ids = ids[:MAX_PLAYLIST]
        self._req("PUT", f"/playlists/{playlist_id}", json={"playlist": {"tracks": [{"id": i} for i in ids]}})

    def like(self, tracks: list[Track]) -> None:
        for t in tracks:
            tid = self._track_id(t)
            if tid:
                self._req("POST", f"/likes/tracks/{tid}")

    def playlist_url(self, pid: str) -> str | None:
        return self._pl_urls.get(pid)

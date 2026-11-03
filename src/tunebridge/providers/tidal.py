"""TIDAL über tidalapi – Gerätelogin (wie beim Fernseher), kein eigener Entwickler-Key nötig.

Login: SH-Tunebridge holt einen Code, du bestätigst ihn auf link.tidal.com im Browser.
Das Token liegt in <Daten>/tokens/tidal.json (nur für dich lesbar) und wird automatisch erneuert.
"""

from __future__ import annotations

import json
import os
import threading
import time

import tidalapi

from .. import config
from ..matching import best_match
from ..models import Playlist, Track
from .base import Provider

_TOKEN = lambda: config.DATA / "tokens" / "tidal.json"  # noqa: E731


def _to_track(t) -> Track:
    album = getattr(t, "album", None)
    cover = None
    try:
        cover = album.image(320) if album else None
    except Exception:
        pass
    return Track(title=t.name or "", artists=[a.name for a in (getattr(t, "artists", None) or []) if a.name],
                 album=getattr(album, "name", None), duration_ms=(t.duration or 0) * 1000 or None,
                 isrc=getattr(t, "isrc", None), ids={"tidal": str(t.id)}, cover=cover)


class Tidal(Provider):
    name = "tidal"
    title = "TIDAL"
    has_isrc = True

    def __init__(self):
        self.s = tidalapi.Session()
        self._login: dict = {}
        self._load()

    # ------------------------------------------------------------ Login
    def _load(self) -> None:
        p = _TOKEN()
        if not p.exists():
            return
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            self.s.load_oauth_session(d["token_type"], d["access_token"], d.get("refresh_token"),
                                      _dt(d.get("expiry_time")))
        except Exception:
            pass

    def _save(self) -> None:
        p = _TOKEN()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"token_type": self.s.token_type, "access_token": self.s.access_token,
                                 "refresh_token": self.s.refresh_token,
                                 "expiry_time": self.s.expiry_time.timestamp() if self.s.expiry_time else None}))
        os.chmod(p, 0o600)

    def connected(self) -> bool:
        try:
            return bool(self.s.access_token) and self.s.check_login()
        except Exception:
            return False

    def account(self) -> str | None:
        try:
            u = self.s.user
            return getattr(u, "username", None) or getattr(u, "email", None) or str(u.id)
        except Exception:
            return None

    def login(self) -> dict:
        """Startet den Gerätelogin -> {url, code}. Ergebnis per login_state() abfragen."""
        if self._login.get("state") == "waiting" and time.time() < self._login.get("expires", 0):
            return self._login
        link, future = self.s.login_oauth()
        url = link.verification_uri_complete
        url = url if url.startswith("http") else "https://" + url
        self._login = {"state": "waiting", "url": url, "code": link.user_code,
                       "expires": time.time() + link.expires_in}

        def wait():
            try:
                future.result()
                if self.s.check_login():
                    self._save()
                    self._login["state"] = "connected"
                else:
                    self._login["state"] = "failed"
            except Exception as e:
                self._login.update(state="failed", error=str(e))
        threading.Thread(target=wait, daemon=True).start()
        return self._login

    def login_state(self) -> dict:
        st = dict(self._login) if self._login else {"state": "idle"}
        if st.get("state") == "waiting" and time.time() > st.get("expires", 0):
            st["state"] = "expired"
        return st

    def logout(self) -> None:
        _TOKEN().unlink(missing_ok=True)
        self.s = tidalapi.Session()
        self._login = {}

    # ------------------------------------------------------------ Lesen
    def playlist_list(self) -> list[dict]:
        """Nur Namen/Anzahl – ohne alle Songs zu laden (spart Aufrufe)."""
        out = []
        for p in self.s.user.playlist_and_favorite_playlists():
            try:   # nur die Bild-Adresse – das Bild lädt der Browser direkt bei TIDAL
                cover = p.image(320)
            except Exception:  # noqa: BLE001 – Playlist ohne Bild
                cover = None
            out.append({"id": str(p.id), "name": p.name, "count": p.num_tracks, "cover": cover,
                        "own": getattr(getattr(p, "creator", None), "id", None) == self.s.user.id})
        return out

    def playlist_tracks(self, pid: str) -> list[Track]:
        return [_to_track(t) for t in self.s.playlist(pid).tracks_paginated()]

    def playlists(self) -> list[Playlist]:
        return [Playlist(name=p["name"], tracks=self.playlist_tracks(p["id"]), ids={"tidal": p["id"]})
                for p in self.playlist_list()]

    def liked(self) -> list[Track]:
        return [_to_track(t) for t in self.s.user.favorites.tracks_paginated()]

    def liked_count(self) -> int:
        try:
            return self.s.user.favorites.get_tracks_count()
        except Exception:
            return 0

    def search(self, track: Track, limit: int = 8) -> list[Track]:
        if track.isrc:
            try:
                hits = self.s.get_tracks_by_isrc(track.isrc)
                if hits:
                    return [_to_track(t) for t in hits[:limit]]
            except Exception:
                pass
        q = f"{(track.artists or [''])[0]} {track.title}".strip()
        res = self.s.search(q, models=[tidalapi.media.Track], limit=limit)
        return [_to_track(t) for t in res.get("tracks", [])]

    def find(self, track: Track) -> Track | None:
        cands = self.search(track)
        if track.isrc and any(c.isrc == track.isrc for c in cands):
            return next(c for c in cands if c.isrc == track.isrc)
        m = best_match(track, cands, threshold=80)
        return m.candidate if m else None

    # ------------------------------------------------------------ Schreiben
    def create_playlist(self, name: str, description: str = "") -> str:
        return str(self.s.user.create_playlist(name, description or "Erstellt mit SH-Tunebridge").id)

    def add_to_playlist(self, playlist_id: str, tracks: list[Track]) -> None:
        ids = [t.ids["tidal"] for t in tracks if t.ids.get("tidal")]
        if ids:
            self.s.playlist(playlist_id).add(ids, allow_duplicates=False)

    def like(self, tracks: list[Track]) -> None:
        for t in tracks:
            if t.ids.get("tidal"):
                self.s.user.favorites.add_track(t.ids["tidal"])

    def playlist_url(self, pid: str) -> str:
        return f"https://tidal.com/browse/playlist/{pid}"

    def track_url(self, tid: str) -> str:
        return f"https://tidal.com/browse/track/{tid}"


def _dt(ts):
    from datetime import datetime
    return datetime.fromtimestamp(ts) if ts else None

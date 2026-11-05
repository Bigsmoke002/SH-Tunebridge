"""YouTube / YouTube Music über die offizielle YouTube Data API v3 – mit deinem Google-Konto (nur Lesen).

Einrichtung (einmalig, kostenlos): console.cloud.google.com → Projekt → „YouTube Data API v3“ aktivieren →
OAuth-Zustimmungsbildschirm (extern, dich selbst als Testnutzer eintragen) → Anmeldedaten → OAuth-Client-ID
vom Typ „Desktop-App“ → Client-ID und Client-Secret hier eintragen. Bei Desktop-Apps ist das Secret laut Google
kein echtes Geheimnis; es bleibt trotzdem nur auf deinem Rechner.
Gelesen werden: deine Playlists (auch private) und „Mag ich“-Videos (darin landen meist auch Likes aus
YouTube Music). Die YouTube-Music-eigene Bibliothek (Alben, Uploads) bietet die offizielle API nicht an.
Hinweis: Solange die Google-App im Testmodus ist, läuft die Anmeldung nach 7 Tagen ab (dann neu verbinden).
"""

from __future__ import annotations

import httpx

from ..models import Track
from .oauth import OAuthError, OAuthProvider

API = "https://www.googleapis.com/youtube/v3"
MAX_ITEMS = 2000
NO_MUSIC = "_keine_musik"     # Markierung in Track.tags: YouTube sagt, das Video ist keine Musik


def mark_non_music(tracks: list[Track], get) -> int:
    """„Mag ich“ enthält alle gelikten Videos (Shorts, Gaming, Doku …). YouTube liefert pro Video eine Kategorie;
    Musik = Kategorie 10 oder ein automatischer „… - Topic“-Kanal. Alles andere bekommt die Markierung NO_MUSIC
    und wird beim Sortieren nicht als Song nachgeschlagen. get(path, **params) -> dict. Gibt die Anzahl zurück.
    Fehlt die Antwort (Fehler, Kontingent), bleibt alles unmarkiert – lieber ein Video zu viel als ein Song zu wenig."""
    by_id = {t.ids.get("youtube"): t for t in tracks if t.ids.get("youtube")}
    ids, n = list(by_id), 0
    for k in range(0, len(ids), 50):
        try:
            d = get("videos", part="snippet", id=",".join(ids[k:k + 50]), maxResults=50)
        except Exception:  # noqa: BLE001
            return n
        for it in d.get("items") or []:
            sn = it.get("snippet") or {}
            if sn.get("categoryId") != "10" and not (sn.get("channelTitle") or "").endswith(" - Topic"):
                t = by_id.get(it.get("id"))
                if t is not None:
                    t.tags = {**(t.tags or {}), NO_MUSIC: 1.0}
                    n += 1
    return n


class YouTube(OAuthProvider):
    name = "youtube"
    title = "YouTube"
    AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    SCOPES = "https://www.googleapis.com/auth/youtube.readonly"
    CLIENT_ID_KEY = "YOUTUBE_OAUTH_CLIENT_ID"
    CLIENT_SECRET_KEY = "YOUTUBE_OAUTH_CLIENT_SECRET"
    SECRET_REQUIRED = True
    EXTRA_AUTH = {"access_type": "offline", "prompt": "consent"}

    def _get(self, path: str, **params) -> dict:
        r = httpx.get(f"{API}/{path}", params=params, timeout=20,
                      headers={"Authorization": f"Bearer {self._access()}"})
        if r.status_code >= 400:
            try:
                msg = r.json()["error"]["message"]
            except Exception:  # noqa: BLE001
                msg = r.text[:200]
            raise OAuthError(f"YouTube: {msg}")
        return r.json()

    def account(self) -> str | None:
        if self._acc is None:
            items = self._get("channels", part="snippet", mine="true").get("items") or []
            self._acc = (items[0]["snippet"]["title"] if items else "") or "Google-Konto"
        return self._acc

    def playlist_list(self) -> list[dict]:
        out, token = [], None
        while len(out) < 500:
            d = self._get("playlists", part="snippet,contentDetails", mine="true", maxResults=50,
                          **({"pageToken": token} if token else {}))
            out += [{"id": x["id"], "name": x["snippet"]["title"],
                     "count": (x.get("contentDetails") or {}).get("itemCount"),
                     "cover": ((x["snippet"].get("thumbnails") or {}).get("medium") or {}).get("url"), "own": True}
                    for x in d.get("items", [])]
            token = d.get("nextPageToken")
            if not token:
                break
        return out

    def playlist_tracks(self, pid: str) -> list[Track]:
        from ..linkimport import split_title
        out, token = [], None
        while len(out) < MAX_ITEMS:
            d = self._get("playlistItems", part="snippet", playlistId=pid, maxResults=50,
                          **({"pageToken": token} if token else {}))
            for it in d.get("items", []):
                sn = it.get("snippet") or {}
                if sn.get("title") in ("Private video", "Deleted video"):
                    continue
                artists, title = split_title(sn.get("title", ""), sn.get("videoOwnerChannelTitle", ""))
                vid = (sn.get("resourceId") or {}).get("videoId", "")
                th = (sn.get("thumbnails") or {})
                out.append(Track(title=title, artists=artists, ids={"youtube": vid} if vid else {},
                                 cover=(th.get("medium") or th.get("default") or {}).get("url")))
            token = d.get("nextPageToken")
            if not token:
                break
        mark_non_music(out, self._get)
        return out

    def liked(self) -> list[Track]:
        # „LL“ = Mag-ich-Playlist des angemeldeten Kontos
        return [t for t in self.playlist_tracks("LL")]

    def liked_count(self) -> int | None:
        try:
            d = self._get("playlists", part="contentDetails", id="LL")
            items = d.get("items") or []
            return (items[0].get("contentDetails") or {}).get("itemCount") if items else None
        except OAuthError:
            return None

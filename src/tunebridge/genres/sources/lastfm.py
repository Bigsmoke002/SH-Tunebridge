"""Last.fm: Tags + ähnliche Songs. Kostenloser API-Key: https://www.last.fm/api/account/create

Alle Antworten werden in der Datenbank gecacht (Tags 30 Tage, Ähnliche 7 Tage) –
jeder Song kostet also höchstens einmal Aufrufe.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import httpx

from ... import config
from ...models import Track
from ...versions import main_artist, split_version

API = "https://ws.audioscrobbler.com/2.0/"
_TAGS_TTL = 30 * 86400
_SIM_TTL = 7 * 86400


def lookup_track(track: Track) -> Track:
    """Für Last.fm nachschlagbare Form: Original statt Slowed-Version, nur Hauptkünstler."""
    title, artists, _ = split_version(track.title, track.artists)
    return Track(title=title, artists=[main_artist(artists[0] if artists else "")])


def same_song(t: Track, artist: str, title: str) -> bool:
    """Passen Künstler und Titel beide zu unserem Song? (Schreibweisen/Feat. werden toleriert)"""
    from ...matching import normalize
    from rapidfuzz import fuzz
    a = fuzz.token_set_ratio(normalize(t.artist), normalize(artist))
    b = fuzz.token_set_ratio(normalize(t.title), normalize(title))
    return a >= 80 and b >= 80


class LastFM:
    def __init__(self, api_key: str | None = None):
        self.key = api_key or config.get("LASTFM_API_KEY")
        from ... import ratelimit
        self.http = httpx.Client(timeout=15, headers={"User-Agent": "tunebridge/0.1"},
                                 event_hooks=ratelimit.httpx_hooks("lastfm", max_wait=3))

    def _call(self, method: str, **params) -> dict:
        """Wirft ratelimit.LimitReached, wenn Last.fm gerade pausiert – Aufrufer cachen dann nichts."""
        from ... import ratelimit
        import time
        for attempt in range(2):   # Last.fm liefert gelegentlich eine Fehlerseite statt JSON -> 1× wiederholen
            r = self.http.get(API, params={"method": method, "api_key": self.key, "format": "json",
                                           "autocorrect": 1, **params})
            if r.status_code == 429:
                raise ratelimit.LimitReached("lastfm", ratelimit.paused("lastfm"), "Last.fm-Limit erreicht")
            try:
                data = r.json() if r.content else {}
                break
            except ValueError:
                if attempt:
                    raise httpx.HTTPError(f"Last.fm: ungültige Antwort (HTTP {r.status_code})") from None
                time.sleep(1.0)
        if data.get("error") == 29:   # Last.fm: „Rate limit exceeded“
            p = ratelimit.blocked("lastfm", None, "Fehler 29: Rate limit exceeded")
            raise ratelimit.LimitReached("lastfm", p, f"Last.fm-Limit erreicht – Pause {round(p)} s")
        if r.status_code >= 500:
            r.raise_for_status()
        if "error" in data:
            return {}
        return data

    # ------------------------------------------------------------ Tags
    def tags(self, track: Track) -> dict[str, float]:
        """Track-Tags (30 Tage gecacht). Fallback auf Künstler-Tags bei unbekannten Songs."""
        from ... import store

        lt = lookup_track(track)
        key = f"{lt.artist.lower()}|{lt.title.lower()}"
        if (hit := store.cache_get("lastfm_tags", key, max_age=_TAGS_TTL)) is not None:
            return hit
        tags = self._tags(lt)
        store.cache_set("lastfm_tags", key, tags)
        return tags

    def song_tags(self, track: Track) -> dict[str, float]:
        """Nur die Tags des Songs selbst – OHNE Rückgriff auf den Künstler (30 Tage gecacht).
        Wichtig bei Namensvettern: „Poni“ ist bei Last.fm auch eine albanische Popsängerin."""
        from ... import store

        lt = lookup_track(track)
        key = f"{lt.artist.lower()}|{lt.title.lower()}"
        if (hit := store.cache_get("lastfm_song_tags2", key, max_age=_TAGS_TTL)) is not None:
            return hit
        data = self._call("track.getTopTags", artist=lt.artist, track=lt.title)
        tags = {t["name"].lower(): float(t["count"])
                for t in data.get("toptags", {}).get("tag", []) if int(t["count"]) > 0}
        # Künstler UND Titel gegenprüfen: Last.fm „korrigiert“ Namen automatisch und landet dann
        # manchmal bei einem anderen Song – dessen Tags gelten nicht für unseren.
        attr = data.get("toptags", {}).get("@attr") or {}
        if tags and attr and not same_song(lt, attr.get("artist", ""), attr.get("track", "")):
            tags = {}
        store.cache_set("lastfm_song_tags2", key, tags)
        return tags

    def _tags(self, track: Track) -> dict[str, float]:
        data = self._call("track.getTopTags", artist=track.artist, track=track.title)
        tags = {t["name"].lower(): float(t["count"])
                for t in data.get("toptags", {}).get("tag", []) if int(t["count"]) > 0}
        if len(tags) < 2:
            for k, v in self.artist_tags(track.artist).items():
                tags.setdefault(k, v * 0.5)
        return tags

    def artist_tags(self, artist: str) -> dict[str, float]:
        from ... import store

        key = main_artist(artist).lower()
        if (hit := store.cache_get("lastfm_artist_tags", key, max_age=_TAGS_TTL)) is not None:
            return hit
        data = self._call("artist.getTopTags", artist=main_artist(artist))
        tags = {t["name"].lower(): float(t["count"]) for t in data.get("toptags", {}).get("tag", [])[:15]
                if int(t["count"]) > 0}
        store.cache_set("lastfm_artist_tags", key, tags)
        return tags

    # ------------------------------------------------------------ Ähnliche Songs
    def similar(self, track: Track, limit: int = 20) -> list[tuple[Track, float]]:
        """Erst ähnliche *Songs*; bei kleinen Künstlern (dort hat Last.fm meist keine) ähnliche
        *Künstler* mit ihrem bekanntesten Song."""
        from ... import store

        lt = lookup_track(track)
        key = f"{lt.artist.lower()}|{lt.title.lower()}|{limit}"
        if hit := store.cache_get("lastfm_similar", key, max_age=_SIM_TTL):   # leer = nicht gemerkt
            return [(Track(**t), m) for t, m in hit]
        out = self._similar_tracks(lt, limit)
        if len(out) < min(limit, 8):
            have = {(t.artists[0].lower(), t.title.lower()) for t, _ in out}
            for t, m in self._via_artists(lt, limit - len(out)):
                if (t.artists[0].lower(), t.title.lower()) not in have:
                    out.append((t, m))
        if out:   # leere Antworten nicht merken – Last.fm liefert seit Okt. 2026 oft gar nichts (Störung)
            from dataclasses import asdict
            store.cache_set("lastfm_similar", key, [(asdict(t), m) for t, m in out])
        return out

    def _similar_tracks(self, track: Track, limit: int) -> list[tuple[Track, float]]:
        data = self._call("track.getSimilar", artist=track.artist, track=track.title, limit=limit)
        out = []
        for t in data.get("similartracks", {}).get("track", []):
            out.append((Track(title=t["name"], artists=[t["artist"]["name"]],
                              duration_ms=(int(t.get("duration") or 0) * 1000) or None),
                        float(t.get("match", 0))))
        return out

    def _via_artists(self, track: Track, limit: int) -> list[tuple[Track, float]]:
        if limit <= 0:
            return []
        data = self._call("artist.getSimilar", artist=track.artist, limit=limit)
        arts = [(a["name"], float(a.get("match", 0))) for a in data.get("similarartists", {}).get("artist", [])]

        def top(a: tuple[str, float]):
            d = self._call("artist.getTopTracks", artist=a[0], limit=1)
            ts = d.get("toptracks", {}).get("track", [])
            # Künstler-Ähnlichkeit etwas abwerten – es ist nicht genau dieser Song
            return (Track(title=ts[0]["name"], artists=[a[0]]), round(a[1] * 0.9, 3)) if ts else None

        with ThreadPoolExecutor(6) as ex:
            return [r for r in ex.map(top, arts) if r]

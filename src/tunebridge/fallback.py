"""Ersatz-Hörprobe: offizieller YouTube- bzw. Spotify-Player (eingebettet, sichtbar), wenn Deezer/Apple keine
Hörprobe haben.

Erlaubt ist nur der offizielle Player, sichtbar und unverändert (YouTube-API-Richtlinien: kein Ton ohne Bild, keine
Wiedergabe im Hintergrund, nichts herunterladen). Diese Datei sucht deshalb nur die *Kennung* des Videos bzw.
Spotify-Songs; abgespielt wird im eingebetteten Player direkt beim Anbieter.

Nur nach ausdrücklicher Einwilligung je Anbieter (Standard: aus) – geprüft hier am Server, nicht nur in der Oberfläche.
Reihenfolge der Quellen (jeweils nur, wenn die vorige nichts liefert):
1. schon bekannte Kennungen/Links des Songs (aus Erkennung und Abgleich) – keine Anfrage,
2. YouTube: offizielle Suche mit deinem eigenen YOUTUBE_API_KEY bzw. deiner verbundenen YouTube-App;
   Spotify: Suche über deine verbundene Spotify-App.
(song.link/Odesli wäre bequemer, hat die öffentliche Schnittstelle ohne Key aber 2026 abgeschaltet.)
Treffer bleiben höchstens 30 Tage im lokalen Zwischenspeicher (YouTube-Richtlinien: API-Daten nach spätestens
30 Tagen auffrischen oder löschen).
"""
from __future__ import annotations

import json
import re
import time

import httpx

from . import config, store
from .models import Track

KINDS = ("youtube", "spotify")
TTL = 30 * 86400
_KEY = "fallback_player"
_YT_ID = re.compile(r"^[\w-]{11}$")
_SP_ID = re.compile(r"^[A-Za-z0-9]{22}$")
_http = httpx.Client(timeout=12, headers={"User-Agent": "SH-Tunebridge"}, follow_redirects=True)


class NotAllowed(PermissionError):
    pass


# ------------------------------------------------------------------ Einwilligung
def settings() -> dict:
    raw = store.meta_get(_KEY)
    d = json.loads(raw) if raw else {}
    return {k: bool(d.get(k)) for k in KINDS} | {"at": {k: d.get(f"{k}_at") for k in KINDS}}


def save(data: dict) -> dict:
    raw = store.meta_get(_KEY)
    d = json.loads(raw) if raw else {}
    for k in KINDS:
        if k in data:
            on = bool(data[k])
            if on and not d.get(k):
                d[f"{k}_at"] = time.time()
            if not on:
                d.pop(f"{k}_at", None)
            d[k] = on
    store.meta_set(_KEY, json.dumps(d))
    if not any(d.get(k) for k in KINDS):
        store.clear_cache("fallback")             # widerrufen: gemerkte Kennungen gleich mit löschen
    return settings()


def sources() -> dict:
    """Was zum Suchen zur Verfügung steht (für den Hinweis in der Oberfläche)."""
    def connected(name: str) -> bool:          # nur gespeicherte Anmeldung prüfen – ohne Anfrage
        try:
            from .providers import get_provider
            return bool(get_provider(name).tok.get("access_token"))
        except Exception:  # noqa: BLE001
            return False
    return {"youtube_key": bool(config.opt("YOUTUBE_API_KEY")), "youtube_app": connected("youtube"),
            "spotify_app": connected("spotify")}


# ------------------------------------------------------------------ Suche
def _youtube_search(t: Track) -> str | None:
    """Offizielle YouTube-Suche (Musik-Kategorie) mit eigenem Key bzw. eigener verbundener YouTube-App."""
    from .linkimport import split_title
    from .matching import best_match
    key = config.opt("YOUTUBE_API_KEY")
    if key:
        q = f"{', '.join(t.artists[:2])} {t.title}".strip()
        r = _http.get("https://www.googleapis.com/youtube/v3/search", params={
            "part": "snippet", "type": "video", "videoCategoryId": "10", "videoEmbeddable": "true", "q": q,
            "maxResults": 5, "key": key})
        if r.status_code != 200:
            return None
        cands = []
        for it in r.json().get("items") or []:
            sn, vid = it.get("snippet") or {}, (it.get("id") or {}).get("videoId")
            if not vid:
                continue
            artists, title = split_title(_unescape(sn.get("title") or ""), (sn.get("channelTitle") or "").removesuffix(" - Topic"))
            cands.append(Track(title=title, artists=artists, ids={"youtube": vid}))
        m = best_match(t, cands, threshold=75)
        return m.candidate.ids["youtube"] if m else None
    try:
        from .providers import get_provider
        p = get_provider("youtube")
        if p.connected() and (hit := p.find(t)):
            return hit.ids.get("youtube")
    except Exception:  # noqa: BLE001
        pass
    return None


def _spotify_search(t: Track) -> str | None:
    try:
        from .providers import get_provider
        p = get_provider("spotify")
        if p.connected() and (hit := p.find(t)):
            return hit.ids.get("spotify")
    except Exception:  # noqa: BLE001
        pass
    return None


def _unescape(s: str) -> str:
    import html
    return html.unescape(s)


def resolve(t: Track, known: dict | None = None, kinds: list[str] | None = None) -> dict:
    """-> {"youtube": Video-ID|None, "spotify": Track-ID|None, "via": {...}} – nur für eingewilligte Anbieter.
    [kinds]: vom Handy – dort hat der Nutzer eingewilligt (die Anfrage nennt die Anbieter ausdrücklich).
    Wirft NotAllowed, wenn keiner eingewilligt ist."""
    on = settings()
    want = [k for k in KINDS if (k in kinds if kinds is not None else on[k])]
    if not want:
        raise NotAllowed("Ersatz-Player ist aus – erst unter Einstellungen › Datenschutz erlauben.")
    known = {k: v for k, v in (known or {}).items() if v}
    out: dict = {k: None for k in KINDS}
    via: dict = {}
    for k in want:
        v = known.get(k) or t.ids.get(k)
        if v and (_YT_ID if k == "youtube" else _SP_ID).match(str(v)):
            out[k], via[k] = str(v), "bekannt"
    ck = f"{(t.artists[0] if t.artists else '').lower()}|{t.title.lower()}"
    if any(out[k] is None for k in want) and (hit := store.cache_get("fallback", ck, max_age=TTL)) is not None:
        for k in want:
            if out[k] is None and hit.get(k):
                out[k], via[k] = hit[k], hit.get("via", {}).get(k, "gemerkt")
    if any(out[k] is None for k in want):
        if "youtube" in want and out["youtube"] is None and (v := _youtube_search(t)):
            out["youtube"], via["youtube"] = v, "YouTube-Suche"
        if "spotify" in want and out["spotify"] is None and (v := _spotify_search(t)):
            out["spotify"], via["spotify"] = v, "Spotify-Suche"
        if any(out[k] for k in want):
            store.cache_set("fallback", ck, {**{k: out[k] for k in want}, "via": via})
    return {**out, "via": via}

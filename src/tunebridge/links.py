"""Song auf den Plattformen öffnen – mit möglichst wenig API-Aufrufen.

Strategie
  1. Direkte Links, die wir ohnehin schon haben (kostet nichts):
     Erkennungsdienste (Shazam/ACRCloud liefern z.T. Spotify/YouTube/Deezer-IDs), Deezer-Abgleich.
  2. Höchstens EIN zusätzlicher Aufruf: iTunes-Suche (frei, ohne Key) für den direkten Apple-Music-Link.
     Ergebnis wird dauerhaft in der Datenbank gespeichert -> pro Song nur einmal.
  3. Für alle anderen Dienste: Such-Link mit „Künstler Titel“ (0 Aufrufe). Der Song steht dort
     praktisch immer ganz oben. Sobald ein Konto verbunden ist, kann der Provider das später durch
     direkte Links ersetzen.
"""

from __future__ import annotations

from urllib.parse import quote, quote_plus

import httpx

from . import ratelimit, store
from .matching import best_match
from .models import Track

PLATFORMS = [
    # id, Name, Such-URL ({q} = "Künstler Titel")
    ("spotify", "Spotify", "https://open.spotify.com/search/{qp}"),
    ("applemusic", "Apple Music", "https://music.apple.com/de/search?term={q}"),
    ("youtubemusic", "YouTube Music", "https://music.youtube.com/search?q={q}"),
    ("youtube", "YouTube", "https://www.youtube.com/results?search_query={q}"),
    ("tidal", "TIDAL", "https://listen.tidal.com/search?q={q}"),
    ("soundcloud", "SoundCloud", "https://soundcloud.com/search/sounds?q={q}"),
    ("deezer", "Deezer", "https://www.deezer.com/search/{qp}"),
    ("beatport", "Beatport", "https://www.beatport.com/search/tracks?q={q}"),
    ("bandcamp", "Bandcamp", "https://bandcamp.com/search?q={q}&item_type=t"),
]
_ALIASES = {"apple": "applemusic", "itunes": "applemusic", "apple music": "applemusic", "youtube music": "youtubemusic"}


_itunes_http = httpx.Client(timeout=8, event_hooks=ratelimit.httpx_hooks("itunes", max_wait=2))


def _query(t: Track) -> str:
    main_artist = (t.artists or [""])[0]
    return f"{main_artist} {t.title}".strip()


def itunes_song(t: Track) -> dict | None:
    """Song bei der freien iTunes-Suche (1 Aufruf, danach gecacht) -> {"url", "genre"} oder None.
    Das Genre ist Apples eigene Einordnung des Songs (z. B. „Dubstep“) – dieselbe, die Shazam mitliefert."""
    key = store.track_key(t)
    cached = store.cache_get("itunes_song", key)
    if cached is not None:
        return cached or None
    hit: dict = {}
    try:
        res = _itunes_http.get("https://itunes.apple.com/search", params={
            "term": _query(t), "entity": "song", "limit": 8, "country": "DE"}).json().get("results", [])
        cands = [Track(title=r["trackName"], artists=[r["artistName"]], duration_ms=r.get("trackTimeMillis"),
                       ids={"url": r["trackViewUrl"], "genre": r.get("primaryGenreName") or ""})
                 for r in res if r.get("trackViewUrl")]
        if (m := best_match(t, cands, threshold=82)):
            hit = {"url": m.candidate.ids["url"].split("&uo=")[0], "genre": m.candidate.ids["genre"] or None}
    except (httpx.HTTPError, ValueError, KeyError, ratelimit.LimitReached):
        return None  # Netzfehler/Limit: nicht cachen, später erneut versuchen
    store.cache_set("itunes_song", key, hit)
    return hit or None


def _itunes(t: Track) -> str | None:
    """Direkter Apple-Music-Link per freier iTunes-Suche."""
    if (cached := store.cache_get("links_itunes", store.track_key(t))):   # ältere Einträge (nur Link)
        return cached
    return (itunes_song(t) or {}).get("url")


def links(t: Track, known: dict[str, str] | None = None, lookup: bool = True) -> list[dict]:
    """-> [{id, name, url, direct}] in fester Reihenfolge."""
    direct: dict[str, str] = {}
    for k, u in (known or {}).items():
        k = _ALIASES.get(k.lower(), k.lower())
        if isinstance(u, str) and u.startswith("http"):
            direct.setdefault(k, u)
    if t.ids.get("deezer"):
        direct.setdefault("deezer", f"https://www.deezer.com/track/{t.ids['deezer']}")
    if t.ids.get("spotify"):
        direct.setdefault("spotify", f"https://open.spotify.com/track/{t.ids['spotify']}")
    if t.ids.get("youtube"):
        direct.setdefault("youtube", f"https://youtu.be/{t.ids['youtube']}")
    hit = store.cache_get("match:tidal", store.track_key(t))  # aus früheren Übertragungen, kostet nichts
    if hit and (hit.get("ids") or {}).get("tidal"):
        direct.setdefault("tidal", f"https://tidal.com/browse/track/{hit['ids']['tidal']}")
    if lookup and "applemusic" not in direct and t.title and t.artists:
        if (u := _itunes(t)):
            direct["applemusic"] = u

    q = _query(t)
    out = []
    for pid, name, tmpl in PLATFORMS:
        if pid in direct:
            out.append({"id": pid, "name": name, "url": direct[pid], "direct": True})
        else:
            out.append({"id": pid, "name": name, "direct": False,
                        "url": tmpl.format(q=quote_plus(q), qp=quote(q, safe=""))})
    return out


# ------------------------------------------------------------------ Kaufen (Künstler unterstützen)
# Nur normale Shop-/Such-Links OHNE Affiliate-/Partner-Parameter – niemand verdient daran mit.
# Reihenfolge nach dem, was erfahrungsgemäß am meisten bei Künstlern ankommt (Bandcamp zuerst).
# Kauf-Shops, sortiert nach bester erreichbarer Qualität (Hi-Res -> verlustfrei -> verlustbehaftet).
# (id, Name, Such-URL, Hinweis, Stufe, Format) – die tatsächliche Qualität hängt vom jeweiligen Release ab.
SHOPS = [
    ("qobuz", "Qobuz", "https://www.qobuz.com/de-de/search?q={q}&type=tracks",
     "Größte Hi-Res-Auswahl", "hires", "FLAC bis 24 Bit / 192 kHz"),
    ("bandcamp", "Bandcamp", "https://bandcamp.com/search?q={q}&item_type=t",
     "Geht größtenteils direkt an Künstler/Label", "lossless", "FLAC, ALAC, WAV – teils 24 Bit"),
    ("beatport", "Beatport", "https://www.beatport.com/search/tracks?q={q}",
     "Elektronische Musik in DJ-Qualität", "lossless", "WAV, AIFF, FLAC oder MP3 320"),
    ("7digital", "7digital", "https://de.7digital.com/search?q={q}&searchtype=track",
     "Download-Shop", "lossless", "FLAC (teils 24 Bit) oder MP3 320"),
    ("itunes", "iTunes Store", "https://music.apple.com/de/search?term={q}",
     "Song als Download kaufen", "lossy", "AAC 256 kbit/s"),
    ("amazon", "Amazon Musik-Downloads", "https://www.amazon.de/s?k={q}&i=digital-music",
     "MP3-Download", "lossy", "MP3, meist 256 kbit/s"),
]
TIERS = {"hires": "Hi-Res", "lossless": "Verlustfrei (CD-Qualität)", "lossy": "Verlustbehaftet (MP3/AAC)"}


def buy_links(t: Track) -> list[dict]:
    """-> [{id, name, url, hint, direct}] – iTunes direkt, wenn schon bekannt (Cache), sonst Suche."""
    q = _query(t)
    out = []
    itunes = store.cache_get("links_itunes", store.track_key(t))
    for sid, name, tmpl, hint, tier, fmt in SHOPS:
        base = {"id": sid, "name": name, "hint": hint, "tier": tier, "tier_name": TIERS[tier], "format": fmt}
        if sid == "itunes" and itunes:
            out.append({**base, "url": itunes + ("&" if "?" in itunes else "?") + "app=itunes", "direct": True})
            continue
        out.append({**base, "url": tmpl.format(q=quote_plus(q)), "direct": False})
    return out

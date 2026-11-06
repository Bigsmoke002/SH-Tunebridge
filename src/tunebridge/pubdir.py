"""Öffentliches Playlist-Verzeichnis – Playlists für alle sichtbar veröffentlichen, stöbern, übernehmen, melden.

* Nur mit Einwilligung „verzeichnis“ (Einstellungen › Datenschutz) – auch das Stöbern, weil dabei der Server
  des Entwicklers (shtunebridge.bs002.de) kontaktiert wird.
* Veröffentlicht wird immer nur eine einzelne Playlist, nach ausdrücklicher Bestätigung in der App.
* Sichtbar für alle: Name, selbst gewähltes Pseudonym, Genre, kurze Beschreibung und die Song-Metadaten
  (Titel, Künstler, Album, ISRC, Länge, Dienst-IDs). Keine Cover, keine Musik, kein Konto, kein Rechnername.
* Der Server kennt dich nur als Hash deines Installations-Schlüssels (wie beim Senden) – damit kannst nur du
  deine Playlists ändern und löschen. Löschung automatisch nach 12 Monaten ohne Aktualisierung.
* In Texten sind Links, E-Mail-Adressen und Telefonnummern nicht erlaubt (Schutz vor Spam und persönlichen Daten).
* Melden (DSA Art. 16): ab 3 Meldungen verschiedener Installationen wird automatisch ausgeblendet, bis der
  Betreiber geprüft hat. Du siehst bei deinen Playlists Status und Grund.
"""

from __future__ import annotations

import json
import re
import time

import httpx

from . import consent, store, upload
from . import debuglog as dbg
from .models import Track
from .share import _tr

MAX_TRACKS = 500
REASONS = {
    "rechtswidrig": "Rechtswidriger Inhalt",
    "beleidigend": "Beleidigend / Hass",
    "spam": "Spam / Werbung",
    "persoenliche_daten": "Persönliche Daten",
    "urheberrecht": "Urheber- oder Markenrecht",
    "sonstiges": "Sonstiges",
}
_MAP = "pubdir:map"            # lokaler Playlist-Name -> veröffentlichte ID
_ALIAS = "pubdir:alias"
_CACHE_S = 300
_cache: dict[str, tuple[float, dict]] = {}

_URL = re.compile(r"https?://|www\.|\b[\w-]+\.(com|de|net|org|io|ly|me|tv|gg|app|xyz|info|link|to|at|ch|eu|co|ru|cn|shop|site|online)\b", re.I)
_MAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
_PHONE = re.compile(r"(?:\+\d|\b0\d)(?:[ \-/()]?\d){7,}")


class PubError(RuntimeError):
    pass


def _need() -> None:
    if not consent.server("verzeichnis"):
        raise PermissionError("Das öffentliche Verzeichnis ist aus – Einstellungen › Datenschutz › "
                              "„Öffentliches Playlist-Verzeichnis“ einschalten")


def check_text(value: str, feld: str, lo: int, hi: int) -> str:
    """Wie der Server: Länge, keine Links / Mail-Adressen / Telefonnummern (frühe, verständliche Fehlermeldung)."""
    s = re.sub(r"[\x00-\x1f\x7f​-‏ -‮⁠-⁯﻿]", "", (value or "")).strip()
    if not lo <= len(s) <= hi:
        raise PubError(f"{feld}: {lo} bis {hi} Zeichen")
    if _URL.search(s):
        raise PubError(f"{feld}: bitte keine Links")
    if _MAIL.search(s):
        raise PubError(f"{feld}: bitte keine E-Mail-Adressen")
    if _PHONE.search(s):
        raise PubError(f"{feld}: bitte keine Telefonnummern")
    return s


def _get(path: str, params: dict | None = None) -> dict:
    key = path + json.dumps(params or {}, sort_keys=True)
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < _CACHE_S:
        return hit[1]
    try:
        r = httpx.get(upload.URL + path, params=params, timeout=15, headers={"User-Agent": "SH-Tunebridge"})
    except httpx.HTTPError as e:
        raise PubError(f"Server nicht erreichbar: {e}") from e
    try:
        data = r.json()
    except ValueError:
        data = {}
    if r.status_code >= 400:
        raise PubError(data.get("error") or f"HTTP {r.status_code}")
    _cache[key] = (time.time(), data)
    return data


def _post(path: str, payload: dict) -> dict:
    try:
        return upload._signed_post(path, payload)
    except upload.UploadError as e:
        raise PubError(str(e)) from e


def _map() -> dict:
    try:
        return json.loads(store.meta_get(_MAP) or "{}")
    except ValueError:
        return {}


def _set_map(m: dict) -> None:
    store.meta_set(_MAP, json.dumps(m))


# ------------------------------------------------------------------ Stöbern
def browse(q: str = "", genre: str = "", page: int = 0) -> dict:
    _need()
    return _get("/v1/pub/list", {"q": (q or "")[:80], "genre": (genre or "")[:60], "page": max(0, int(page))})


def genres() -> list[dict]:
    _need()
    return _get("/v1/pub/genres").get("genres", [])


def get(pid: str) -> dict:
    _need()
    if not re.fullmatch(r"[0-9a-f]{24}", pid or ""):
        raise PubError("Ungültige ID")
    return _get(f"/v1/pub/{pid}")


def tracks_of(p: dict) -> list[Track]:
    return [Track(title=t.get("title", ""), artists=t.get("artists") or [], album=t.get("album"), isrc=t.get("isrc"),
                  ids=t.get("ids") or {}, duration_ms=t.get("duration_ms"), genre=t.get("genre"))
            for t in p.get("tracks") or []]


def copy(pid: str, name: str = "") -> dict:
    """Veröffentlichte Playlist als eigene lokale Playlist übernehmen."""
    p = get(pid)
    target = (name or p["name"]).strip()[:120] or "Aus dem Verzeichnis"
    n = 0
    for t in tracks_of(p):
        n += bool(store.add_to_playlist(target, t))
    dbg.event("verzeichnis", "Playlist übernommen", songs=n)
    return {"name": target, "count": n}


def report(pid: str, grund: str, text: str = "") -> dict:
    _need()
    if grund not in REASONS:
        raise PubError("Bitte einen Grund wählen")
    r = _post(f"/v1/pub/{pid}/report", {"grund": grund, "text": (text or "").strip()[:500]})
    _cache.clear()
    return r


# ------------------------------------------------------------------ Eigene Playlists
def alias() -> str:
    return store.meta_get(_ALIAS) or ""


def mine() -> dict:
    _need()
    if not upload.KEY_FILE.exists():
        return {"playlists": [], "map": {}, "alias": alias(), "max": 20}
    r = _post("/v1/pub/mine", {})
    ids = {p["id"] for p in r.get("playlists", [])}
    m = {k: v for k, v in _map().items() if v in ids}       # serverseitig gelöschte (Frist/Betreiber) austragen
    _set_map(m)
    return {**r, "map": m, "alias": alias()}


def publish(name: str, alias_: str, genre: str = "", info: str = "", confirm: bool = False) -> dict:
    """Eine lokale Playlist veröffentlichen (oder aktualisieren). confirm muss ausdrücklich True sein."""
    _need()
    if confirm is not True:
        raise PubError("Bitte die Veröffentlichung ausdrücklich bestätigen")
    pl = next((p for p in store.local_playlists() if p.name == name), None)
    if pl is None:
        raise PubError(f"Playlist „{name}“ nicht gefunden")
    if not pl.tracks:
        raise PubError("Die Playlist ist leer")
    payload = {"format": 1, "name": check_text(name, "Name", 2, 80), "alias": check_text(alias_, "Pseudonym", 2, 32),
               "genre": check_text(genre, "Genre", 0, 60), "info": check_text(info, "Beschreibung", 0, 300),
               "tracks": [_pub_track(t) for t in pl.tracks[:MAX_TRACKS]]}
    m = _map()
    if m.get(name):
        payload["id"] = m[name]
    try:
        r = _post("/v1/pub/publish", payload)
    except PubError as e:
        if "id" in payload and "Nicht (mehr) vorhanden" in str(e):
            payload.pop("id")
            r = _post("/v1/pub/publish", payload)
        else:
            raise
    m[name] = r["id"]
    _set_map(m)
    store.meta_set(_ALIAS, payload["alias"])
    _cache.clear()
    dbg.event("verzeichnis", "Playlist veröffentlicht", songs=r.get("n"))
    return {**r, "name": name, "gekappt": len(pl.tracks) > MAX_TRACKS}


def _pub_track(t: Track) -> dict:
    d = _tr(t)
    d.pop("subgenre", None)
    if d.get("ids"):
        d["ids"] = {k: v for k, v in d["ids"].items() if k != "isrc"}
        if not d["ids"]:
            d.pop("ids")
    if not d.get("artists"):
        d["artists"] = ["Unbekannt"]
    return d


def unpublish(pid: str | None = None, all_: bool = False) -> dict:
    if not all_:                  # alles löschen geht immer – auch nach Widerruf der Einwilligung
        _need()
    if not upload.KEY_FILE.exists():
        return {"geloescht": 0}
    r = _post("/v1/pub/delete", {"alle": True} if all_ else {"id": pid})
    m = {} if all_ else {k: v for k, v in _map().items() if v != pid}
    _set_map(m)
    _cache.clear()
    return r

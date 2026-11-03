"""Einwilligungen – einmal beim ersten Start abgefragt, jederzeit in den Einstellungen änderbar.

Grundsatz: nur anonym bzw. pseudonym und nur das Nötigste.
* Lokale Funktionen (bleiben auf diesem Rechner) sind vorbelegt, lassen sich aber abschalten.
* Alles, was an den Server des Entwicklers geht, ist AUS, bis der Nutzer es ausdrücklich erlaubt –
  und zusätzlich die genaue Ziel-Domain bestätigt hat.
* Ohne bestätigte Datenschutzerklärung wird nichts gesendet (auch nicht auf Klick).
"""

from __future__ import annotations

import json
import time

from . import store

VERSION = 2                       # erhöhen, wenn sich Datenschutzerklärung/Kategorien wesentlich ändern
DOMAIN = "shtunebridge.bs002.de"
_KEY = "consent"

LOCAL = ("misses", "player", "cache")          # lokal speichern
SERVER = ("misses", "fehler", "songs", "genres", "genredb")   # mit dem Server des Entwicklers (genredb = laden)

DEFAULTS = {
    "version": 0, "privacy_at": None,
    "local": {"misses": True, "player": True, "cache": True},
    "server": {"domain": False, "misses": False, "fehler": False, "songs": False, "genres": False, "genredb": False},
}


def get() -> dict:
    try:
        raw = store.meta_get(_KEY)
        cur = json.loads(raw) if raw else {}
    except Exception:
        cur = {}
    return {"version": cur.get("version", 0), "privacy_at": cur.get("privacy_at"),
            "local": {**DEFAULTS["local"], **{k: bool(v) for k, v in (cur.get("local") or {}).items() if k in LOCAL}},
            "server": {**DEFAULTS["server"], **{k: bool(v) for k, v in (cur.get("server") or {}).items()
                                                if k in (*SERVER, "domain")}},
            "domain": DOMAIN, "current_version": VERSION, "needs_onboarding": cur.get("version", 0) < VERSION}


def save(data: dict) -> dict:
    """data: {privacy: bool, local: {...}, server: {...}}. Ohne bestätigte Datenschutzerklärung -> Fehler."""
    cur = get()
    if data.get("privacy") is not True and not cur["privacy_at"]:
        raise ValueError("Bitte zuerst die Datenschutzerklärung bestätigen")
    local = {**cur["local"], **{k: bool(v) for k, v in (data.get("local") or {}).items() if k in LOCAL}}
    server = {**cur["server"], **{k: bool(v) for k, v in (data.get("server") or {}).items()
                                  if k in (*SERVER, "domain")}}
    if not server["domain"]:                 # ohne Domain-Bestätigung keine Sende-Erlaubnis
        server = {k: False for k in server}
    now = time.time()
    for k in ("songs", "misses", "genres"):   # automatisch nur, was NACH der Einwilligung entsteht
        if server[k] and not (cur["server"][k] and cur["server"]["domain"]):
            store.meta_set(f"outbox:{k}_since", str(now))
    out = {"version": VERSION, "privacy_at": cur["privacy_at"] or now, "local": local, "server": server}
    store.meta_set(_KEY, json.dumps(out))
    return get()


def local(what: str) -> bool:
    return get()["local"].get(what, True)


def server(what: str) -> bool:
    c = get()
    return bool(c["privacy_at"] and c["version"] >= VERSION and c["server"]["domain"] and c["server"].get(what))


def server_any() -> bool:
    return any(server(k) for k in SERVER)

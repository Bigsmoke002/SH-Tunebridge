"""Was spielt gerade? – über MPRIS (die Mediensteuerung von Linux), rein lokal.

Browser (YouTube, YouTube Music, SoundCloud …), Spotify, VLC usw. melden dem System Titel,
Künstler, Länge und Position. SH-Tunebridge liest das nur auf deinem Rechner:
* als Hinweis in der Liste „Nicht erkannt“ (was lief laut Player?)
* im Dauer-Modus, um einen Songwechsel sofort zu bemerken – ohne Online-Abfrage.
Gesendet wird davon nur etwas, wenn du es erlaubt hast (Einwilligungen, siehe consent.py).
"""

from __future__ import annotations

import json
import shutil
import subprocess

_IFACE = "org.mpris.MediaPlayer2.Player"


def _busctl(*args: str) -> str:
    try:
        return subprocess.run(["busctl", "--user", "--json=short", *args], capture_output=True,
                              text=True, timeout=2).stdout
    except (subprocess.SubprocessError, OSError):
        return ""


def _val(v):
    return v.get("data") if isinstance(v, dict) else v


def now_playing() -> list[dict]:
    """[{player, status, title, artist, album, url, length_s, position_s, trackid}] – Spielende zuerst."""
    if not shutil.which("busctl"):
        return []
    try:
        names = json.loads(_busctl("list") or "[]")
    except ValueError:
        return []
    out = []
    for n in names:
        name = n.get("name", "")
        if not name.startswith("org.mpris.MediaPlayer2."):
            continue
        try:
            meta = json.loads(_busctl("get-property", name, "/org/mpris/MediaPlayer2", _IFACE, "Metadata") or "{}")
            meta = meta.get("data") or {}
            status = json.loads(_busctl("get-property", name, "/org/mpris/MediaPlayer2", _IFACE,
                                        "PlaybackStatus") or "{}").get("data")
            pos = json.loads(_busctl("get-property", name, "/org/mpris/MediaPlayer2", _IFACE,
                                     "Position") or "{}").get("data")
        except ValueError:
            continue
        artist = _val(meta.get("xesam:artist")) or []
        artist = ", ".join(a for a in artist if a) if isinstance(artist, list) else str(artist)
        title = _val(meta.get("xesam:title")) or ""
        if not title:
            continue
        length = _val(meta.get("mpris:length"))
        out.append({"player": name.split(".", 3)[3].split(".instance")[0], "status": status,
                    "title": title, "artist": artist, "album": _val(meta.get("xesam:album")) or "",
                    "url": _val(meta.get("xesam:url")) or "",
                    "length_s": round(length / 1e6, 1) if length else None,
                    "position_s": round(pos / 1e6, 1) if isinstance(pos, (int, float)) and pos else None,
                    "trackid": str(_val(meta.get("mpris:trackid")) or "")})
    # Doppelte (Browser meldet sich oft zweimal: direkt + Plasma-Integration) – die vollständigere behalten
    best: dict[str, dict] = {}
    for p in out:
        k = p["title"].split(" | ")[0].strip().lower()
        if k not in best or (len(p["artist"]) + len(p["url"])) > (len(best[k]["artist"]) + len(best[k]["url"])):
            best[k] = p
    return sorted(best.values(), key=lambda p: p["status"] != "Playing")


def current() -> dict | None:
    """Der eine Player, der gerade spielt (oder None)."""
    playing = [p for p in now_playing() if p["status"] == "Playing"]
    return playing[0] if len(playing) == 1 else (playing[0] if playing else None)


def signature() -> str:
    """Kurzer Wert, der sich ändert, sobald irgendwo ein anderer Song läuft."""
    return "|".join(sorted(f"{p['player']}:{p['title']}:{p['artist']}" for p in now_playing()
                           if p["status"] == "Playing"))


_KEEP_QUERY = {"youtube.com": {"v"}, "www.youtube.com": {"v"}, "music.youtube.com": {"v"}, "m.youtube.com": {"v"}}


def clean_url(url: str) -> str:
    """Nur öffentliche Web-Adressen, ohne Tracking-/Sitzungs-Parameter. Lokale Dateipfade fallen weg
    (die würden z. B. den Benutzernamen verraten)."""
    from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
    try:
        u = urlsplit(url or "")
    except ValueError:
        return ""
    if u.scheme not in ("http", "https") or not u.hostname:
        return ""
    keep = _KEEP_QUERY.get(u.hostname.lower(), set())
    q = urlencode([(k, v) for k, v in parse_qsl(u.query) if k in keep])
    return urlunsplit((u.scheme, u.hostname.lower(), u.path, q, ""))


def minimal(p: dict | None) -> dict | None:
    """Datensparsame Fassung für die Liste „Nicht erkannt“: kein trackid, keine lokalen Pfade."""
    if not p:
        return None
    return {"player": p.get("player", "")[:40], "title": (p.get("title") or "")[:200],
            "artist": (p.get("artist") or "")[:200], "album": (p.get("album") or "")[:200],
            "url": clean_url(p.get("url", "")), "length_s": p.get("length_s"), "position_s": p.get("position_s")}

"""Playlist-Dateien einlesen – die Export-Funktionen der Dienste selbst, also der rechtlich saubere Weg.

* Apple Music / iTunes: „Datei › Bibliothek › Playlist exportieren“ -> .xml (Plist) oder .txt (Tabulator, UTF-16)
* YouTube Music: Google Takeout -> CSV mit „Video-ID“ (Titel kommen dann per offiziellem oEmbed)
* Spotify & Co.: CSV aus Exportify, TuneMyMusic, Soundiiz … (Spalten Titel/Künstler werden erkannt)
* .m3u / .m3u8: Playlists aus Playern (VLC, foobar, Winamp …) – nur die #EXTINF-Angaben, keine Dateipfade
Gelesen werden nur Titel, Künstler, Album, ISRC, Dauer. Die Datei selbst wird nicht gespeichert.
"""

from __future__ import annotations

import csv
import io
import plistlib
import re
from pathlib import PurePath

from .models import Track

MAX_BYTES = 5 * 1024 * 1024
MAX_TRACKS = 2000


class FileError(ValueError):
    pass


def _text(data: bytes) -> str:
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return data.decode("utf-16")
    if data[:3] == b"\xef\xbb\xbf":
        return data[3:].decode("utf-8")
    for enc in ("utf-8", "cp1252"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1")


_COLS = {
    "title": ("track name", "title", "titel", "name", "song", "song name", "song title", "track", "track title",
              "songtitel"),
    "artist": ("artist name(s)", "artist names", "artist", "artists", "interpret", "künstler", "kunstler",
               "creator", "artist name", "album artist", "interpreten"),
    "album": ("album name", "album", "album title", "albumtitel", "release"),
    "isrc": ("isrc",),
    "video": ("video id", "video-id", "videoid"),
    "ms": ("duration (ms)", "track duration (ms)", "duration_ms"),
}


def _col(header: list[str], kind: str) -> int | None:
    h = [c.strip().lower().lstrip("﻿") for c in header]
    for name in _COLS[kind]:
        if name in h:
            return h.index(name)
    return None


def _split_artists(s: str) -> list[str]:
    parts = [p.strip() for p in re.split(r"\s*(?:;|,(?=\s*\S)|\s&\s|\sfeat\.?\s|\sft\.?\s)\s*", s or "") if p.strip()]
    return parts or ([s.strip()] if s and s.strip() else [])


def _rows(text: str, delimiter: str | None = None) -> list[list[str]]:
    if delimiter is None:
        try:
            delimiter = csv.Sniffer().sniff(text[:4096], delimiters=",;\t").delimiter
        except csv.Error:
            delimiter = ","
    return [r for r in csv.reader(io.StringIO(text), delimiter=delimiter) if any(c.strip() for c in r)]


def _table(rows: list[list[str]]) -> list[Track]:
    if not rows:
        return []
    header, body = rows[0], rows[1:]
    ti, ai, al, isrc, ms = (_col(header, k) for k in ("title", "artist", "album", "isrc", "ms"))
    if ti is None:
        raise FileError("Keine Spalte für den Titel gefunden (erwartet z. B. „Track Name“, „Title“, „Name“)")
    out = []
    for r in body:
        get = (lambda i: r[i].strip() if i is not None and i < len(r) else "")
        if not get(ti):
            continue
        dur = get(ms)
        out.append(Track(title=get(ti), artists=_split_artists(get(ai)), album=get(al) or None,
                         isrc=get(isrc) or None, duration_ms=int(float(dur)) if re.fullmatch(r"\d+(\.\d+)?", dur) else None))
    return out


def _youtube_ids(rows: list[list[str]]) -> list[Track]:
    from .linkimport import LinkError, _youtube
    vi = _col(rows[0], "video")
    out = []
    for r in rows[1:MAX_TRACKS + 1]:
        vid = r[vi].strip() if vi is not None and vi < len(r) else ""
        if not re.fullmatch(r"[\w-]{11}", vid):
            continue
        try:
            out += _youtube("track", vid)[1]      # offizielles oEmbed: Titel + Kanal
        except LinkError:
            continue                               # privat/gelöscht
    return out


def _plist(data: bytes) -> tuple[str, list[Track]]:
    try:
        pl = plistlib.loads(data)
    except Exception as e:
        raise FileError("XML-Datei ist keine iTunes/Apple-Music-Playlist") from e
    tracks = pl.get("Tracks") or {}
    lists = pl.get("Playlists") or []
    order = [str(i.get("Track ID")) for i in (lists[0].get("Playlist Items") or [])] if lists else list(tracks)
    out = []
    for tid in order:
        t = tracks.get(tid)
        if not t or not t.get("Name"):
            continue
        out.append(Track(title=t["Name"], artists=_split_artists(t.get("Artist", "")), album=t.get("Album"),
                         duration_ms=t.get("Total Time")))
    name = (lists[0].get("Name") if lists else None) or "Apple-Music-Playlist"
    return name, out


def _m3u(text: str) -> list[Track]:
    out = []
    for line in text.splitlines():
        m = re.match(r"#EXTINF:(-?\d+)[^,]*,(.*)$", line.strip())
        if not m:
            continue
        raw = m[2].strip()
        a, sep, t = raw.partition(" - ")
        out.append(Track(title=(t if sep else raw).strip(), artists=_split_artists(a) if sep else [],
                         duration_ms=int(m[1]) * 1000 if int(m[1]) > 0 else None))
    return out


def parse(filename: str, data: bytes) -> tuple[str, list[Track]]:
    """-> (Playlist-Name, Songs). Wirft FileError bei unbekanntem Format."""
    if len(data) > MAX_BYTES:
        raise FileError("Datei ist zu groß (max. 5 MB)")
    name = PurePath(filename or "Playlist").stem or "Playlist"
    ext = PurePath(filename or "").suffix.lower()
    head = data[:200].lstrip()
    if ext == ".xml" or head.startswith(b"<?xml") or head.startswith(b"<plist"):
        name, tracks = _plist(data)
    else:
        text = _text(data)
        if ext in (".m3u", ".m3u8") or text.lstrip().startswith("#EXTM3U"):
            tracks = _m3u(text)
        elif ext == ".txt" and "\t" in text.split("\n", 1)[0]:
            tracks = _table(_rows(text, "\t"))       # Apple Music / iTunes „Textdatei“
        else:
            rows = _rows(text)
            if not rows:
                raise FileError("Datei ist leer")
            tracks = _youtube_ids(rows) if _col(rows[0], "video") is not None and _col(rows[0], "title") is None \
                else _table(rows)
    tracks = [t for t in tracks if t.title][:MAX_TRACKS]
    if not tracks:
        raise FileError("Keine Songs in der Datei gefunden. Unterstützt: Apple Music/iTunes (.xml/.txt), "
                        ".m3u/.m3u8, CSV (Exportify, TuneMyMusic, Soundiiz, Google Takeout)")
    return name, tracks

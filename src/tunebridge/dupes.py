"""Doppelte Songs in deinen lokalen Playlists finden.

Drei Arten:
  doppelt   – derselbe Song steht in EINER Playlist mehrfach (z. B. einmal mit ISRC, einmal ohne). Immer überflüssig.
  mehrfach  – derselbe Song steht in mehreren Playlists. Kann gewollt sein – du entscheidest.
  versionen – Original und Remix/Edit/Slowed … desselben Songs. Nur zur Info („ist ein anderer Song“).

„Derselbe Song“ = gleiche ISRC oder gleicher Hauptkünstler + Titel (normalisiert, ohne „feat.“, „Official Video“ …).
Alles läuft lokal auf der eigenen Datenbank.
"""

from __future__ import annotations

import re
from collections import defaultdict

from . import store
from .matching import hard_version, normalize
from .versions import main_artist, split_version

# Klammern/Anhänge mit Versionsangabe: „(Hardtekk Remix)“, „- VIP“, „[Extended Mix]“
_VERSION_PART = re.compile(
    r"\s*(?:[\(\[][^\)\]]*\b(?:remix|vip|edit|bootleg|flip|rework|dub|refix|mix|version|ver|live|acoustic|"
    r"remaster(?:ed)?|slowed|reverb|sped up|nightcore|cover)\b[^\)\]]*[\)\]]"
    r"|\s[-–]\s.*\b(?:remix|vip|edit|bootleg|flip|rework|mix|version|live|acoustic|remaster(?:ed)?)\b.*$)", re.I)


def _artists(t: dict) -> set[str]:
    """Erster Künstler normalisiert – einmal komplett („DJ X feat. Y“ -> „dj x“), einmal nur Hauptkünstler („A & B“ -> „a“)."""
    arts = t.get("artists") or []
    return {normalize(arts[0]), normalize(main_artist(arts[0]))} - {""} if arts else {""}


def song_keys(t: dict) -> list[str]:
    title = normalize(t.get("title") or "")
    out = [f"{a}|{title}" for a in sorted(_artists(t))]
    if t.get("isrc"):
        # ISRC nur zusammen mit der Fassung: ältere Einträge können die ISRC des Originals tragen (falscher Treffer
        # beim Nachschlagen) – ein Remix/Flip/Cover darf darüber nie zum „doppelten“ Original werden
        kind, rest = hard_version(t.get("title") or "")
        out.append("isrc:" + t["isrc"].upper() + "|" + ",".join(sorted(kind)) + "|" + rest)
    return out


def base_key(t: dict) -> str:
    """Schlüssel ohne Versionsangabe: Original und Remix bekommen denselben."""
    title, arts, _ = split_version(t.get("title") or "", t.get("artists") or [])
    title = _VERSION_PART.sub("", title).strip() or title
    return f"{normalize(arts[0]) if arts else ''}|{normalize(title)}"


class _UF:
    def __init__(self):
        self.p: dict[int, int] = {}

    def find(self, x: int) -> int:
        self.p.setdefault(x, x)
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a: int, b: int) -> None:
        self.p[self.find(a)] = self.find(b)


def _rows() -> list[dict]:
    rows = []
    for p in store.local_playlists():
        for e in store.playlist_entries(p.name):
            rows.append({"playlist": p.name, "key": e["key"], "ts": e["ts"], "track": e["track"]})
    return rows


def _occ(r: dict) -> dict:
    t = r["track"]
    return {"playlist": r["playlist"], "key": r["key"], "ts": r["ts"], "title": t.get("title"),
            "artists": t.get("artists") or [], "cover": t.get("cover"), "isrc": t.get("isrc"),
            "genre": t.get("genre"), "subgenre": t.get("subgenre"), "preview_url": t.get("preview_url"),
            "ids": t.get("ids") or {}}


def find(rows: list[dict] | None = None) -> dict:
    rows = _rows() if rows is None else rows
    uf, first = _UF(), {}
    for i, r in enumerate(rows):
        uf.find(i)
        for k in song_keys(r["track"]):
            if k in first:
                uf.union(i, first[k])
            else:
                first[k] = i
    songs: dict[int, list[int]] = defaultdict(list)
    for i in range(len(rows)):
        songs[uf.find(i)].append(i)

    doppelt, mehrfach = [], []
    for idx in songs.values():
        if len(idx) < 2:
            continue
        by_pl: dict[str, list[int]] = defaultdict(list)
        for i in idx:
            by_pl[rows[i]["playlist"]].append(i)
        for pl, ii in by_pl.items():
            if len(ii) > 1:          # ältester Eintrag bleibt, die anderen sind überflüssig
                ii = sorted(ii, key=lambda i: rows[i]["ts"])
                doppelt.append({"playlist": pl, "keep": _occ(rows[ii[0]]), "remove": [_occ(rows[i]) for i in ii[1:]]})
        if len(by_pl) > 1:
            mehrfach.append({"song": _occ(rows[idx[0]]),
                             "in": [_occ(rows[sorted(ii, key=lambda i: rows[i]["ts"])[0]]) for ii in by_pl.values()]})

    # Versionen: verschiedene Songs mit gleichem Grundtitel
    by_base: dict[str, dict[int, int]] = defaultdict(dict)
    for root, idx in songs.items():
        by_base[base_key(rows[idx[0]]["track"])][root] = idx[0]
    versionen = []
    for b, roots in by_base.items():
        if len(roots) > 1 and b.split("|", 1)[1]:
            occ = [_occ(rows[i]) for i in roots.values()]
            occ.sort(key=lambda o: (len(o["title"] or ""), o["title"] or ""))     # Original (kürzester Titel) zuerst
            versionen.append({"songs": occ})
    mehrfach.sort(key=lambda g: -len(g["in"]))
    return {"doppelt": doppelt, "mehrfach": mehrfach, "versionen": versionen,
            "zahlen": {"doppelt": sum(len(g["remove"]) for g in doppelt), "mehrfach": len(mehrfach),
                       "versionen": len(versionen), "songs": len(rows)}}


def remove(items: list[dict]) -> int:
    """items: [{playlist, key}] -> Anzahl entfernter Einträge."""
    n = 0
    names = {p.name for p in store.local_playlists()}
    for it in items:
        if it.get("playlist") in names and it.get("key"):
            store.remove_from_playlist(it["playlist"], it["key"])
            n += 1
    return n

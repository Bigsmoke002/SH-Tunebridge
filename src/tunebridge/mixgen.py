"""„Mix erstellen“: aus Künstlern oder einem (Sub-)Genre eine neue, passende Playlist bauen.

Ablauf (ein Auftrag im Hintergrund, wie beim Set-Planer):
1. Kandidaten sammeln – Deezer (öffentliche API, ohne Login): Top-Songs der Start-Künstler, ihr Künstler-Radio und die
   Top-Songs ähnlicher Künstler. Bei der Genre-Suche kommen die Künstler aus Bibliothek, eigenen Einordnungen,
   Gemeinschafts-DB, MusicBrainz und Last.fm (siehe „Genre-Suche“). Jeder Kandidat bekommt einen Ähnlichkeitswert
   (`fit`, 0..1) und einen Grund.
2. Filtern: Fassungen (Remix/VIP/…), Songs aus der eigenen Bibliothek, höchstens N Songs pro Künstler.
3. Tempo, Tonart, Energie – nur wenn die gewählte Stufe (oder ein eigener Filter) sie braucht. Erst aus dem
   Song-Speicher, sonst aus der offiziellen 30-s-Hörprobe (audiofeat), nacheinander und mit Obergrenze
   (MEASURE_MAX) – es wird nicht auf Vorrat gemessen.
4. Bewerten (reine Rechnerei, `score`) und auswählen; bei „Mixbar“/„DJ-genau“ in DJ-Reihenfolge (setplan.order).

Datenschutz/Bedingungen: An Deezer gehen nur Künstler-Kennungen bzw. Künstlernamen, an MusicBrainz/Last.fm nur die
Genre-Tags (z. B. „liquid funk“). Ergebnisse bleiben
nur im Arbeitsspeicher (Aufträge 6 Std., Deezer-Antworten 1 Std.); gespeichert wird erst, wenn du „Als Playlist
speichern“ wählst. Kein Suchverlauf. Hörproben werden nur gestreamt; gemessen werden wie überall nur drei Zahlen.
Nichts davon geht an den Server des Entwicklers oder in die Gemeinschafts-Genre-Datenbank.
"""
from __future__ import annotations

import math
import statistics
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

from . import debuglog as dbg
from . import store
from .audiofeat import camelot_distance
from .matching import hard_version, normalize
from .models import Track
from .ratelimit import LimitReached
from .setplan import tempo_jump

# Stufen „Wie passend?“: Tempo-Abstand in % (None = egal), Tonart-Abstand zur Ziel-Tonart, Energie-Abstand,
# DJ-Reihenfolge. Eigene Filter (BPM-Bereich, Tonart, Energie) gelten zusätzlich und immer hart.
LEVELS: dict[str, dict] = {
    "locker":  {"name": "Locker",   "tempo": None, "key": None, "energy": None, "order": False,
                "hint": "ähnliche Künstler, Tempo und Tonart egal – schnell, ohne Messen"},
    "passend": {"name": "Passend",  "tempo": 15.0, "key": None, "energy": 0.3, "order": False,
                "hint": "ähnliches Tempo (±15 %) und ähnliche Energie"},
    "mixbar":  {"name": "Mixbar",   "tempo": 6.0, "key": 2, "energy": 0.25, "order": True,
                "hint": "±6 % Tempo (halbes/doppeltes zählt), ähnliche Energie, in DJ-Reihenfolge mit harmonischen Übergängen"},
    "genau":   {"name": "DJ-genau", "tempo": 3.0, "key": 1, "energy": None, "order": True,
                "hint": "±3 % Tempo, Übergänge in gleicher oder Nachbar-Tonart (Camelot), Energie-Verlauf wie im Set-Planer"},
}
POPULARITY = ("mix", "hits", "unbekannt")
COUNT_DEFAULT, COUNT_MAX = 30, 100
MAX_SEEDS = 15
RELATED_PER_SEED = 12      # ähnliche Künstler je Start-Künstler (bei vielen Start-Künstlern weniger, s. collect)
RELATED_TOTAL = 48         # höchstens so viele ähnliche Künstler insgesamt – Rücksicht auf Deezer
TOP_PER_RELATED = 4        # Top-Songs je ähnlichem Künstler
MEASURE_MAX = 150          # höchstens so viele Hörproben pro Auftrag (Rücksicht auf Deezer)
MEASURE_WORKERS = 4       # gleichzeitige Messungen – das Deezer-Budget (ratelimit) gilt trotzdem für alle zusammen
JOB_TTL = 6 * 3600

_jobs: dict[str, dict] = {}


# ------------------------------------------------------------------ Optionen
def clean_opts(o: dict | None) -> dict:
    """Eingaben der Oberfläche prüfen und auf sinnvolle Grenzen bringen."""
    o = dict(o or {})

    def num(k, lo, hi, cast=float):
        v = o.get(k)
        if v in (None, ""):
            return None
        try:
            return max(lo, min(hi, cast(v)))
        except (TypeError, ValueError):
            return None
    out = {
        "level": o.get("level") if o.get("level") in LEVELS else "passend",
        "count": int(num("count", 5, COUNT_MAX, int) or COUNT_DEFAULT),
        "per_artist": int(num("per_artist", 1, 10, int) or 2),
        "popularity": o.get("popularity") if o.get("popularity") in POPULARITY else "mix",
        "versions": bool(o.get("versions", True)),
        "skip_library": bool(o.get("skip_library", False)),
        "include_seeds": bool(o.get("include_seeds", True)),
        "bpm_min": num("bpm_min", 40, 250), "bpm_max": num("bpm_max", 40, 250),
        "energy_min": num("energy_min", 0, 1), "energy_max": num("energy_max", 0, 1),
        "camelot": (str(o.get("camelot") or "").strip().upper() or None),
        "curve": o.get("curve") if o.get("curve") in ("aufbau", "peak", "gleich", "runter") else "gleich",
    }
    if out["camelot"] and not _valid_camelot(out["camelot"]):
        out["camelot"] = None
    for a, b in (("bpm_min", "bpm_max"), ("energy_min", "energy_max")):
        if out[a] is not None and out[b] is not None and out[a] > out[b]:
            out[a], out[b] = out[b], out[a]
    return out


def _valid_camelot(c: str) -> bool:
    return len(c) in (2, 3) and c[-1] in "AB" and c[:-1].isdigit() and 1 <= int(c[:-1]) <= 12


def needs_features(opts: dict) -> bool:
    lv = LEVELS[opts["level"]]
    return any(lv[k] is not None for k in ("tempo", "key", "energy")) or lv["order"] or any(
        opts[k] is not None for k in ("bpm_min", "bpm_max", "energy_min", "energy_max", "camelot"))


# ------------------------------------------------------------------ Deezer
def _get(url: str, **params) -> dict:
    from .artists import _get as dz_get
    return dz_get(url, **params)


def _cached(key: str, fn):
    from .artists import _cached as cached
    return cached(f"mix:{key}", fn)


def search_artists(q: str, limit: int = 8) -> list[dict]:
    """Künstler bei Deezer suchen – der Nutzer wählt danach selbst aus (keine Namensvettern)."""
    q = (q or "").strip()[:100]
    if len(q) < 2:
        return []
    d = _cached(f"s:{q.lower()}", lambda: _get("https://api.deezer.com/search/artist", q=q, limit=limit))
    return [{"id": a["id"], "name": a.get("name") or "", "picture": a.get("picture_medium"), "fans": a.get("nb_fan") or 0}
            for a in (d.get("data") or []) if a.get("id")][:limit]


def _item(h: dict, fit: float, why: str, seed: bool = False) -> dict | None:
    art = h.get("artist") or {}
    if not h.get("id") or not h.get("title") or not art.get("name"):
        return None
    alb = h.get("album") or {}
    return {"title": h["title"], "artists": [art["name"]], "artist": art["name"], "artist_id": art.get("id"),
            "album": alb.get("title"), "cover": alb.get("cover_medium"), "duration_ms": (h.get("duration") or 0) * 1000 or None,
            "isrc": h.get("isrc"), "ids": {"deezer": str(h["id"])}, "preview_url": h.get("preview") or None,
            "rank": h.get("rank") or 0, "fit": round(fit, 3), "why": why, "seed": seed}


def collect(seeds: list[dict], opts: dict, job: dict | None = None) -> list[dict]:
    """Kandidaten aus Deezer: Top-Songs der Start-Künstler, deren Radio, Top-Songs ähnlicher Künstler."""
    seed_ids = {int(s["id"]) for s in seeds}
    out: list[dict] = []

    def add(h, fit, why, seed=False):
        if (it := _item(h, fit, why, seed)):
            out.append(it)

    related: dict[int, tuple[float, str, str]] = {}      # Künstler-ID -> (fit, Name, über wen)
    n = max(1, len(seeds))
    per_seed = max(3, min(RELATED_PER_SEED, RELATED_TOTAL // n))   # 1–4 Künstler: 12 je Künstler, 15 Künstler: 3
    radio_n = max(20, min(50, 250 // n))
    for s in seeds:
        aid, name = int(s["id"]), s.get("name") or ""
        top = _cached(f"top:{aid}", lambda aid=aid: _get(f"https://api.deezer.com/artist/{aid}/top", limit=10)).get("data") or []
        if opts["include_seeds"]:
            for i, h in enumerate(top):
                own = (h.get("artist") or {}).get("id") == aid
                add(h, 1.0 - i * 0.02, f"von {name}" if own else f"mit {name}", seed=True)
        radio = (_cached(f"radio:{aid}", lambda aid=aid: _get(f"https://api.deezer.com/artist/{aid}/radio", limit=50)).get("data") or [])[:radio_n]
        for i, h in enumerate(radio):
            if (h.get("artist") or {}).get("id") in seed_ids:
                if opts["include_seeds"]:
                    add(h, 0.9 - i * 0.004, f"von {name}", seed=True)
                continue
            add(h, max(0.45, 0.88 - i * 0.008), f"aus dem Radio von {name}")
        rel = _cached(f"rel:{aid}", lambda aid=aid: _get(f"https://api.deezer.com/artist/{aid}/related", limit=RELATED_PER_SEED)).get("data") or []
        for i, a in enumerate(rel[:per_seed]):
            if a.get("id") and a["id"] not in seed_ids:
                fit = 0.85 - i * 0.025
                if fit > related.get(a["id"], (0,))[0]:
                    related[a["id"]] = (fit, a.get("name") or "", name)
        if job is not None:
            job["done"] += 1

    if job is not None:
        job["total"] = len(seeds) + len(related)

    def top_of(item):
        rid, (fit, _name, via) = item
        try:
            ts = _cached(f"top:{rid}:{TOP_PER_RELATED}",
                         lambda: _get(f"https://api.deezer.com/artist/{rid}/top", limit=TOP_PER_RELATED)).get("data") or []
        except LimitReached:
            return []
        return [(h, fit - k * 0.03, f"ähnlich zu {via}") for k, h in enumerate(ts)]

    with ThreadPoolExecutor(4) as ex:
        for res in ex.map(top_of, sorted(related.items(), key=lambda kv: -kv[1][0])):
            for h, fit, why in res:
                add(h, fit, why)
            if job is not None:
                job["done"] += 1
    return dedupe(out)


# ------------------------------------------------------------------ Genre-Suche
# Woher Künstler/Songs eines (Sub-)Genres kommen – in dieser Reihenfolge der Verlässlichkeit:
#   1. deine Bibliothek (Song-Speicher + eigene Playlists) und deine eigenen Einordnungen – kostet keine Abfrage
#   2. Gemeinschafts-Genre-Datenbank (nur wenn du sie geladen hast)
#   3. MusicBrainz: Künstler mit passendem Tag (1 Abfrage, CC0)
#   4. Last.fm: Top-Künstler und Top-Songs des Tags (nur mit eigenem Last.fm-Key)
# Danach werden die Künstler bei Deezer gesucht (nur bei eindeutigem Namen) und ihre Top-Songs genommen. Die Genres
# stammen von Künstlern (nicht von jedem einzelnen Song) – deshalb steht im Grund z. B. „Liquid laut MusicBrainz“.
# Erst wenn das nicht reicht (oder bei „Locker“/„Passend“), wird über das Künstler-Radio aufgefüllt – solche Songs
# gelten als unbestätigt und fallen bei „DJ-genau“ weg.
MAX_GENRE_ARTISTS = 24
MB_PER_QUERY = 60
SRC_LABEL = {"bibliothek": "deiner Bibliothek", "eigene": "deinen Einordnungen", "gemeinschaft": "Gemeinschafts-DB",
             "musicbrainz": "MusicBrainz", "lastfm": "Last.fm", "haupt": "MusicBrainz"}
SRC_WEIGHT = {"bibliothek": 0.95, "eigene": 0.95, "gemeinschaft": 0.85, "lastfm": 0.82, "musicbrainz": 0.8, "haupt": 0.55}
MIN_SUB_ARTISTS = 6        # weniger Künstler fürs Subgenre gefunden -> mit dem Hauptgenre auffüllen (als unbestätigt)


def check_genre(g: dict | None) -> dict | None:
    """{"genre": …, "sub": …} gegen den Genre-Baum prüfen."""
    from .genres.taxonomy import TAXONOMY
    if not g or g.get("genre") not in TAXONOMY:
        return None
    sub = g.get("sub") or None
    if sub and (sub == "_" or sub not in TAXONOMY[g["genre"]]):
        sub = None
    return {"genre": g["genre"], "sub": sub}


def genre_label(g: dict) -> str:
    return f"{g['genre']} › {g['sub']}" if g.get("sub") else g["genre"]


def genre_tags(g: dict, n: int = 3) -> list[str]:
    """Die ersten Tag-Synonyme aus dem Genre-Baum (das sind die Tags, die in MusicBrainz/Last.fm stehen)."""
    from .genres.taxonomy import TAXONOMY
    return list(dict.fromkeys(TAXONOMY[g["genre"]][g["sub"] or "_"]))[:n]


def _local_genre(g: dict) -> tuple[list[dict], dict[str, str]]:
    """Songs der Bibliothek mit diesem Genre (als Kandidaten) und Künstler -> Quelle."""
    from . import genredb
    items, arts = [], {}
    for d in store.tracks_by_genre(g["genre"], g["sub"]):
        if not d.get("title") or not d.get("artists"):
            continue
        it = {"title": d["title"], "artists": d["artists"][:1], "artist": d["artists"][0], "artist_id": None,
              "album": d.get("album"), "cover": d.get("cover"), "duration_ms": d.get("duration_ms"), "isrc": d.get("isrc"),
              "ids": d.get("ids") or {}, "preview_url": d.get("preview_url"), "rank": 0, "fit": 0.95,
              "why": f"{_short(g)} · aus deiner Bibliothek", "seed": True}
        items.append(it)
        arts.setdefault(d["artists"][0], "bibliothek")
    try:
        for v in genredb.votes(2000):
            if v.get("genre") == g["genre"] and (not g["sub"] or v.get("subgenre") == g["sub"]) and v.get("artist"):
                arts.setdefault(v["artist"].split(",")[0].strip(), "eigene")
    except Exception as e:  # noqa: BLE001 – Einordnungen sind eine Zugabe
        dbg.error("mixgen", "Eigene Einordnungen nicht lesbar", e)
    return items, arts


def _community_artists(g: dict, limit: int = 15) -> list[str]:
    """Künstler, die in der Gemeinschafts-Genre-DB mindestens zweimal mit diesem Genre stehen (nur wenn geladen)."""
    from collections import Counter

    from . import consent, genredb
    if not consent.server("genredb"):
        return []
    d = genredb._load_community()
    if not d:
        return []
    cnt: Counter = Counter()
    for k, hit in d["songs"].items():
        if "|" in k and hit and hit[0] == g["genre"] and (not g["sub"] or (len(hit) > 1 and hit[1] == g["sub"])):
            cnt[k.split("|")[0]] += 1
    return [a for a, n in cnt.most_common(limit) if n >= 2]


def mb_relevant(tags_of_artist: list[dict], want: set[str], family: set[str]) -> int:
    """Stimmen für das gesuchte Genre, wenn es beim Künstler ein Schwerpunkt ist – sonst 0.
    Schwerpunkt = Stimmen für das Genre + seine Familie (bei Liquid z. B. auch „drum and bass“) sind mindestens halb so
    viele wie für den stärksten Tag des Künstlers. So fliegt z. B. Prince mit einer Einzelstimme „deep house“ raus."""
    counts = {(t.get("name") or "").lower(): max(0, t.get("count", 0)) for t in tags_of_artist or []}
    votes = sum(c for n, c in counts.items() if n in want)
    if votes <= 0:
        return 0
    related = sum(c for n, c in counts.items() if n in want or n in family)
    return votes if related * 2 >= max(counts.values(), default=0) else 0


def _mb_artists(g: dict) -> list[tuple[str, str]]:
    """MusicBrainz: Künstler mit passendem Tag -> [(Name, Beschreibung)], die mit den meisten Stimmen zuerst."""
    from .genres.sources import musicbrainz
    from .genres.taxonomy import TAXONOMY
    tags = genre_tags(g)
    q = " OR ".join(f'tag:"{t}"' for t in tags)

    def load():
        try:
            return musicbrainz._get("artist", query=q, limit=MB_PER_QUERY)
        except LimitReached:                     # MusicBrainz meldet gern kurz „ausgelastet“ (503) – Pause abwarten, einmal nachfassen
            from . import ratelimit
            with ratelimit.patient(max_wait=15):
                return musicbrainz._get("artist", query=q, limit=MB_PER_QUERY)
    d = _cached(f"mb:{q}", load)
    want = {t.lower() for t in TAXONOMY[g["genre"]][g["sub"] or "_"]}
    family = {t.lower() for syn in TAXONOMY[g["genre"]].values() for t in syn}
    rows = []
    for a in d.get("artists") or []:
        if a.get("name") and (votes := mb_relevant(a.get("tags"), want, family)):
            rows.append((votes, a.get("score", 0), a["name"], a.get("disambiguation") or ""))
    rows.sort(key=lambda r: (-r[0], -r[1]))
    return [(r[2], r[3]) for r in rows]


def _lastfm(g: dict) -> tuple[list[str], list[tuple[str, str]]]:
    """Last.fm (nur mit Key): Top-Künstler und Top-Songs des ersten passenden Tags."""
    from . import config
    if not config.opt("LASTFM_API_KEY"):
        return [], []
    from .genres.sources.lastfm import LastFM
    lf = LastFM()
    for tag in genre_tags(g, 2):
        a = _cached(f"lfa:{tag}", lambda tag=tag: lf._call("tag.getTopArtists", tag=tag, limit=30))
        t = _cached(f"lft:{tag}", lambda tag=tag: lf._call("tag.getTopTracks", tag=tag, limit=50))
        arts = [x["name"] for x in (a.get("topartists") or {}).get("artist", []) if x.get("name")]
        trs = [(x["artist"]["name"], x["name"]) for x in (t.get("tracks") or {}).get("track", [])
               if x.get("name") and (x.get("artist") or {}).get("name")]
        if arts or trs:
            return arts, trs
    return [], []


def deezer_artist(name: str) -> dict | None:
    """Künstler bei Deezer über den Namen – nur bei genau gleichem Namen; bei Namensvettern der mit den meisten Fans."""
    n = normalize(name)
    if not n:
        return None
    d = _cached(f"s:{name.lower()}", lambda: _get("https://api.deezer.com/search/artist", q=name, limit=8))
    same = [a for a in d.get("data") or [] if a.get("id") and normalize(a.get("name") or "") == n]
    return max(same, key=lambda a: a.get("nb_fan") or 0) if same else None


def _short(g: dict) -> str:
    return g["sub"] or g["genre"]


def collect_genre(g: dict, opts: dict, job: dict | None = None) -> list[dict]:
    out, arts = _local_genre(g)
    sources: dict[str, set[str]] = {}
    for a, src in arts.items():
        sources.setdefault(a, set()).add(src)

    def note(msg):
        if job is not None:
            job["note"] = ((job.get("note") or "") + " " + msg).strip()
    for a in _community_artists(g):
        sources.setdefault(a, set()).add("gemeinschaft")
    try:
        for a, _desc in _mb_artists(g)[:MAX_GENRE_ARTISTS]:
            sources.setdefault(a, set()).add("musicbrainz")
    except Exception as e:  # noqa: BLE001 – MusicBrainz ist eine von mehreren Quellen (auch LimitReached)
        dbg.problem("mixgen", f"MusicBrainz nicht erreichbar: {e}")
        note("MusicBrainz war gerade nicht erreichbar.")
    lf_tracks: list[tuple[str, str]] = []
    try:
        lf_arts, lf_tracks = _lastfm(g)
        for a in lf_arts:
            sources.setdefault(a, set()).add("lastfm")
    except Exception as e:  # noqa: BLE001 – Last.fm ist eine Zugabe (auch LimitReached)
        dbg.problem("mixgen", f"Last.fm nicht erreichbar: {e}")
    if g["sub"] and len({normalize(a) for a in sources}) < MIN_SUB_ARTISTS:
        try:
            for a, _desc in _mb_artists({"genre": g["genre"], "sub": None})[:MAX_GENRE_ARTISTS]:
                sources.setdefault(a, set()).add("haupt")
            note(f"Zu „{g['sub']}“ gibt es kaum Daten – ergänzt mit Künstlern aus {g['genre']} (Subgenre nicht bestätigt).")
        except Exception as e:  # noqa: BLE001
            dbg.problem("mixgen", f"MusicBrainz (Hauptgenre) nicht erreichbar: {e}")
    # gleiche Künstler aus mehreren Quellen zusammenführen (Schreibweisen), dann nach Verlässlichkeit ordnen
    merged: dict[str, tuple[str, set[str]]] = {}
    for a, srcs in sources.items():
        k = normalize(a)
        if k:
            name, s0 = merged.get(k, (a, set()))
            merged[k] = (name, s0 | srcs)

    def weight(srcs):
        return min(1.0, max(SRC_WEIGHT[s] for s in srcs) + 0.05 * (len(srcs) - 1))
    ranked = sorted(merged.values(), key=lambda x: -weight(x[1]))[:MAX_GENRE_ARTISTS]
    if job is not None:
        job.update(total=len(ranked), done=0)

    def one(entry):
        name, srcs = entry
        try:
            da = deezer_artist(name)
            if not da:
                return []
            top = _cached(f"top:{da['id']}:6", lambda: _get(f"https://api.deezer.com/artist/{da['id']}/top", limit=6)).get("data") or []
        except LimitReached:
            return []
        w = weight(srcs)
        sure = srcs - {"haupt"}
        if sure:
            why = f"{_short(g)} laut " + " + ".join(SRC_LABEL[s] for s in sorted(sure, key=lambda s: -SRC_WEIGHT[s]))
        else:
            why = f"{g['genre']} laut MusicBrainz – {g['sub']} nicht bestätigt"
        res = []
        for k, h in enumerate(top):
            if (h.get("artist") or {}).get("id") == da["id"] and (it := _item(h, w - k * 0.03, why, seed=bool(sure))):
                res.append(it)
        return res
    with ThreadPoolExecutor(4) as ex:
        for res in ex.map(one, ranked):
            out.extend(res)
            if job is not None:
                job["done"] += 1
    have = {song_key(it) for it in out}
    for artist, title in lf_tracks:
        it = {"title": title, "artists": [artist], "artist": artist, "artist_id": None, "album": None, "cover": None,
              "duration_ms": None, "isrc": None, "ids": {}, "preview_url": None, "rank": 0, "fit": 0.85,
              "why": f"{_short(g)} laut Last.fm (Song)", "seed": True}
        if song_key(it) not in have:
            out.append(it)
    # auffüllen über das Künstler-Radio – nur wenn nötig oder bei lockeren Stufen; diese Songs sind unbestätigt
    confirmed = len(dedupe(out))
    if opts["level"] != "genau" and (opts["level"] in ("locker", "passend") or confirmed < opts["count"] * 2):
        for entry in ranked[:3]:
            try:
                da = deezer_artist(entry[0])
                if not da:
                    continue
                radio = _cached(f"radio:{da['id']}", lambda da=da: _get(f"https://api.deezer.com/artist/{da['id']}/radio", limit=50)).get("data") or []
            except LimitReached:
                break
            for i, h in enumerate(radio):
                if (it := _item(h, max(0.35, 0.6 - i * 0.005), f"aus dem Radio von {da.get('name') or entry[0]}")):
                    out.append(it)
    if not ranked and not out:
        note(f"Für „{genre_label(g)}“ wurden keine Künstler gefunden.")
    return dedupe(out)


def song_key(it: dict) -> str:
    return f"{normalize(it['artists'][0] if it.get('artists') else '')}|{normalize(it.get('title') or '')}"


def dedupe(items: list[dict]) -> list[dict]:
    """Gleicher Song (Künstler + Titel inkl. Fassung, oder ISRC) nur einmal – der mit dem besten Grund bleibt."""
    best: dict[str, dict] = {}
    isrc_of: dict[str, str] = {}
    for it in items:
        k = song_key(it)
        if it.get("isrc"):
            k = isrc_of.setdefault(it["isrc"], k)
        if k not in best or it["fit"] > best[k]["fit"]:
            best[k] = it
    return list(best.values())


# ------------------------------------------------------------------ Filtern und Bewerten
def prefilter(items: list[dict], opts: dict, library: set[str] | None = None) -> list[dict]:
    out = []
    for it in items:
        if not opts["versions"] and hard_version(it["title"])[0]:
            continue
        if library and (song_key(it) in library or (it.get("isrc") and it["isrc"] in library)):
            continue
        out.append(it)
    return out


def library_keys() -> set[str]:
    keys = set()
    for p in store.local_playlists():
        for t in p.tracks:
            keys.add(f"{normalize(t.artists[0] if t.artists else '')}|{normalize(t.title)}")
            if t.isrc:
                keys.add(t.isrc)
    return keys


def popularity(items: list[dict]) -> None:
    """Rang (Deezer „rank“) -> Perzentil 0..1 innerhalb der Kandidaten."""
    ranks = sorted(it.get("rank") or 0 for it in items)
    n = len(ranks)
    for it in items:
        r = it.get("rank") or 0
        it["pop"] = round(sum(1 for x in ranks if x < r) / (n - 1), 3) if n > 1 else 0.5


def reference(items: list[dict], opts: dict) -> dict:
    """Ziel-Tempo/-Tonart/-Energie: eigene Angaben zuerst, sonst aus den gemessenen Songs der Start-Künstler."""
    seeds = [it for it in items if it.get("seed") and it.get("bpm")] or [it for it in items if it.get("bpm")][:15]
    ref = {"bpm": None, "camelot": opts["camelot"], "energy": None}
    if opts["bpm_min"] is not None or opts["bpm_max"] is not None:
        lo, hi = opts["bpm_min"] or opts["bpm_max"], opts["bpm_max"] or opts["bpm_min"]
        ref["bpm"] = (lo + hi) / 2
    elif seeds:
        ref["bpm"] = ref_tempo([(it["bpm"], it.get("bpm_conf", 0.5)) for it in seeds])
    es = [it["energy"] for it in seeds if it.get("energy") is not None]
    if es:
        ref["energy"] = statistics.median(es)
    return ref


def _octave_dist(a: float, b: float) -> float:
    """Abstand zweier Tempi, wobei halbes/doppeltes Tempo gleich ist (0 = gleich, 0,5 = größtmöglich), in Oktaven."""
    d = abs(math.log2(a / b)) % 1
    return min(d, 1 - d)


def ref_tempo(meas: list[tuple[float, float]]) -> float | None:
    """Ziel-Tempo aus Messungen (BPM, Sicherheit) – Abstimmung statt Median.
    Die Messung an 30-s-Hörproben verrutscht bei schneller Musik gern: halbes Tempo (DnB 174 -> 87) oder 2/3
    (174 -> 116). Deshalb gewinnt die Tempo-Gruppe (halb/doppelt zusammengefasst, ±4 %) mit dem meisten Gewicht;
    einzelne Ausreißer verschieben das Ziel nicht. Danach die Lage: Liegt mindestens ein Viertel der Messungen der
    Gruppe in der doppelten Lage und bleibt die unter 185 BPM, gilt die doppelte (DnB/Dubstep werden oft halb gemessen)."""
    pts = [(b, max(0.1, w or 0)) for b, w in meas if b and b > 0]
    if not pts:
        return None
    tol = math.log2(1.04)

    def weight(c):
        return sum(w for b, w in pts if _octave_dist(b, c) <= tol)
    best = max((b for b, _ in pts), key=lambda c: (weight(c), -abs(math.log2(c / 120))))
    group = [b for b, _ in pts if _octave_dist(b, best) <= tol]
    low = [b / 2 ** math.floor(math.log2(b / best) + 0.5) for b in group]       # alle in die Lage von „best“
    ref = statistics.median(low)
    while ref >= 185:
        ref /= 2
    while ref < 60:
        ref *= 2
    if ref * 2 <= 185 and sum(1 for b in group if abs(math.log2(b / (ref * 2))) <= tol) * 4 >= len(group):
        ref *= 2
    return round(ref, 1)


def fold_to(bpm: float | None, ref: float | None) -> float | None:
    """Tempo in die Lage des Ziel-Tempos bringen (Anzeige: 86,7 wird bei Ziel 174 zu 173,4)."""
    if not bpm or not ref:
        return bpm
    return round(min((bpm, bpm * 2, bpm / 2), key=lambda c: abs(c - ref)), 1)


def _in_bpm_range(bpm: float, lo: float | None, hi: float | None) -> bool:
    lo, hi = lo or 0, hi or 999
    return any(lo <= c <= hi for c in (bpm, bpm * 2, bpm / 2))


def passes(it: dict, opts: dict, ref: dict) -> tuple[bool, str]:
    """Harte Filter der Stufe und der eigenen Angaben. Unbekannte Werte fallen nur bei eigenen Filtern raus."""
    lv = LEVELS[opts["level"]]
    bpm, cam, en = it.get("bpm"), it.get("camelot"), it.get("energy")
    if opts["bpm_min"] is not None or opts["bpm_max"] is not None:
        if not bpm or not _in_bpm_range(bpm, opts["bpm_min"], opts["bpm_max"]):
            return False, "Tempo außerhalb des Bereichs"
    elif lv["tempo"] is not None and ref.get("bpm") and ((tj := tempo_jump(ref["bpm"], bpm)) is None or tj > lv["tempo"]):
        return False, "Tempo passt nicht"
    if opts["camelot"] and (not cam or camelot_distance(opts["camelot"], cam) > (lv["key"] if lv["key"] is not None else 1)):
        return False, "Tonart passt nicht"
    if opts["energy_min"] is not None or opts["energy_max"] is not None:
        if en is None or not ((opts["energy_min"] or 0) <= en <= (opts["energy_max"] if opts["energy_max"] is not None else 1)):
            return False, "Energie außerhalb des Bereichs"
    elif lv["energy"] is not None and ref.get("energy") is not None and en is not None and abs(en - ref["energy"]) > lv["energy"]:
        return False, "Energie passt nicht"
    return True, ""


def score(it: dict, opts: dict, ref: dict) -> float:
    """0..1 – Ähnlichkeit führt, dazu Bekanntheit (je nach Wunsch), Tempo- und Tonart-Nähe."""
    s = 0.6 * it["fit"]
    pop = it.get("pop", 0.5)
    s += 0.2 * (pop if opts["popularity"] == "hits" else 1 - pop if opts["popularity"] == "unbekannt" else 0.5)
    lv = LEVELS[opts["level"]]
    if lv["tempo"] is not None and ref.get("bpm") and it.get("bpm"):
        s += 0.12 * max(0.0, 1 - tempo_jump(ref["bpm"], it["bpm"]) / max(lv["tempo"], 1))
    if ref.get("camelot") and it.get("camelot"):
        s += 0.08 * max(0.0, 1 - camelot_distance(ref["camelot"], it["camelot"]) / 3)
    return round(s, 4)


def pick(items: list[dict], opts: dict) -> tuple[list[int], list[int]]:
    """Beste zuerst, höchstens per_artist je Künstler -> (Auswahl, Reserve) als Indizes."""
    order = sorted(range(len(items)), key=lambda i: -items[i]["score"])
    per: dict[str, int] = {}
    chosen, reserve = [], []
    for i in order:
        a = normalize(items[i]["artist"])
        if len(chosen) < opts["count"] and per.get(a, 0) < opts["per_artist"]:
            chosen.append(i)
            per[a] = per.get(a, 0) + 1
        else:
            reserve.append(i)
    return chosen, reserve


def _reasons(it: dict) -> list[str]:
    out = [it["why"]]
    if it.get("bpm"):
        out.append(f"{round(it['bpm'])} BPM")
    if it.get("camelot"):
        out.append(it["camelot"])
    if it.get("energy") is not None:
        out.append(f"Energie {round(it['energy'] * 100)} %")
    return out


# ------------------------------------------------------------------ Auftrag
def _measure(job: dict, items: list[dict], ref_first: list[dict]) -> None:
    """Tempo/Tonart/Energie holen – Start-Künstler zuerst (für die Ziel-Werte), dann die besten Kandidaten.
    Mehrere Hörproben gleichzeitig (Laden wartet aufs Netz); Deezers Budget regelt ratelimit für alle Threads.
    Bricht ab, sobald genug passende Songs da sind oder MEASURE_MAX erreicht ist."""
    from . import audiofeat, ratelimit
    opts = job["opts"]
    first = {id(it) for it in ref_first}
    pool = ref_first + [it for it in sorted(items, key=lambda x: -x["fit"]) if id(it) not in first]
    budget = min(len(pool), MEASURE_MAX)
    job.update(phase="measuring", done=0, total=budget)
    enough = int(opts["count"] * 1.3) + 5
    ref = None
    limited = threading.Event()

    def one(it: dict) -> None:
        if job["cancel"] or limited.is_set():
            return
        t = Track(title=it["title"], artists=it["artists"], isrc=it.get("isrc"), ids=it.get("ids") or {},
                  preview_url=it.get("preview_url"))
        with ratelimit.patient():            # gilt je Thread
            try:
                f = audiofeat.features(t)
            except LimitReached:
                limited.set()
                return
            except Exception as e:  # noqa: BLE001 – ein kaputter Song darf den Mix nicht abbrechen
                dbg.error("mixgen", "Tempo/Tonart nicht ermittelt", e)
                f = None
        it["measured"] = True
        if f:
            it.update(bpm=f.get("bpm"), bpm_conf=f.get("bpm_conf", 0.5), camelot=f.get("camelot"), key=f.get("key"),
                      energy=f.get("energy"))

    # Erst alle Start-Songs (Ziel-Werte), dann die Kandidaten in kleinen Runden – nach jeder Runde prüfen, ob es reicht
    n_ref = min(len(ref_first), budget)
    rounds = [pool[:n_ref]] + [pool[i:min(i + MEASURE_WORKERS * 2, budget)]
                              for i in range(n_ref, budget, MEASURE_WORKERS * 2)]
    done = 0
    with ThreadPoolExecutor(MEASURE_WORKERS, thread_name_prefix="mix-mess") as ex:
        for chunk in rounds:
            if not chunk:
                continue
            if job["cancel"]:
                return
            list(ex.map(one, chunk))
            done += len(chunk)
            job["done"] = done
            if limited.is_set():
                job["note"] = "Deezer bremst gerade – nicht alle Songs konnten gemessen werden."
                break
            if done >= n_ref:
                ref = ref or reference(items, opts)
                if sum(1 for x in pool[n_ref:done] if passes(x, opts, ref)[0]) >= enough:
                    break


def _run(job: dict) -> None:
    from . import ratelimit, setplan
    opts = job["opts"]
    try:
        with ratelimit.patient(max_wait=60):
            cands = collect_genre(job["genre"], opts, job) if job.get("genre") else collect(job["seeds"], opts, job)
        if job["cancel"]:
            job["state"] = "cancelled"
            return
        cands = prefilter(cands, opts, library_keys() if opts["skip_library"] else None)
        if not cands:
            job.update(state="done", items=[], order=[], reserve=[], ref={}, found=0,
                       note=((job.get("note") or "") + " Keine Songs gefunden – andere Auswahl oder lockerere Einstellungen probieren.").strip())
            return
        popularity(cands)
        if needs_features(opts):
            seeds_first = sorted([c for c in cands if c["seed"]], key=lambda x: -x["fit"])[:6 * max(2, len(job["seeds"]))]
            _measure(job, cands, seeds_first)
            if job["cancel"]:
                job["state"] = "cancelled"
                return
            ref = reference(cands, opts)
            if job.get("genre") and ref.get("bpm") and opts["bpm_min"] is None and opts["bpm_max"] is None:
                from .audiofeat import fold_bpm
                ref["bpm"] = round(fold_bpm(ref["bpm"], job["genre"]["genre"]), 1)   # DnB 87 -> 174, House bleibt
            # nicht gemessene Songs nur behalten, wenn keine harte Tempo-/Tonart-/Energie-Vorgabe gilt
            pool = [c for c in cands if passes(c, opts, ref)[0] and (c.get("measured") or not needs_features(opts))]
        else:
            ref, pool = reference(cands, opts), cands
        if job.get("genre") and opts["level"] == "genau":
            pool = [c for c in pool if c["seed"]]                 # nur bestätigte Genre-Treffer
        for c in pool:
            c["bpm"] = fold_to(c.get("bpm"), ref.get("bpm"))
            c["score"] = score(c, opts, ref)
            c["reasons"] = _reasons(c)
        chosen, reserve = pick(pool, opts)
        if LEVELS[opts["level"]]["order"] and len(chosen) > 2:
            sub = [pool[i] for i in chosen]
            chosen = [chosen[i] for i in setplan.order(sub, opts["curve"])]
        lost = len(cands) - len(pool)
        note = job.get("note") or ""
        if len(chosen) < opts["count"]:
            note = (note + " " if note else "") + (
                f"Nur {len(chosen)} von {opts['count']} Songs passen so genau"
                + (f" ({lost} Kandidaten aussortiert)" if lost else "") + " – „Locker“ oder „Passend“ findet mehr.")
        job.update(state="done", items=pool, order=chosen, reserve=reserve, found=len(cands),
                   ref={k: v for k, v in ref.items() if v is not None}, note=note.strip())
    except LimitReached as e:
        job.update(state="error", error=f"{e} – bitte gleich noch einmal versuchen.")
    except Exception as e:  # noqa: BLE001
        dbg.error("mixgen", "Mix erstellen abgebrochen", e)
        job.update(state="error", error=str(e))


def start(seeds: list[dict] | None, opts: dict | None = None, genre: dict | None = None) -> str:
    g = check_genre(genre) if genre else None
    if genre and not g:
        raise ValueError("Dieses Genre kenne ich nicht – bitte aus der Liste wählen")
    seeds = [{"id": int(s["id"]), "name": str(s.get("name") or "")[:200]} for s in (seeds or [])
             if str(s.get("id", "")).isdigit()][:MAX_SEEDS]
    if not seeds and not g:
        raise ValueError("Bitte mindestens einen Künstler oder ein Genre auswählen")
    opts = clean_opts(opts)
    jid = uuid.uuid4().hex[:10]
    _jobs[jid] = {"id": jid, "seeds": [] if g else seeds, "genre": g, "opts": opts, "state": "running",
                  "phase": "collecting", "done": 0, "total": 1 if g else len(seeds), "cancel": False,
                  "started": time.time(), "note": ""}
    threading.Thread(target=_run, args=(_jobs[jid],), daemon=True).start()
    for k in [k for k, j in _jobs.items() if time.time() - j["started"] > JOB_TTL]:
        _jobs.pop(k, None)
    return jid


def job(jid: str) -> dict:
    j = _jobs.get(jid)
    if not j:
        raise ValueError("Auftrag nicht gefunden (abgelaufen?) – bitte neu starten")
    return j


def public(j: dict) -> dict:
    """Was die Oberfläche sieht (ohne interne Felder)."""
    out = {k: j.get(k) for k in ("id", "state", "phase", "done", "total", "note", "error", "seeds", "genre", "opts",
                                  "order", "reserve", "found", "ref")}
    if j.get("state") == "done":
        keep = ("title", "artists", "artist", "album", "cover", "duration_ms", "isrc", "ids", "preview_url",
                "bpm", "camelot", "key", "energy", "reasons", "score")
        out["items"] = [{k: it.get(k) for k in keep} for it in j["items"]]
    return out


def describe(jid: str, idx: list[int]) -> dict:
    """Übergänge der aktuellen Auswahl (für „x von y Übergängen harmonisch“)."""
    from . import setplan
    j = job(jid)
    idx = _checked(j, idx)
    sub = [j["items"][i] for i in idx]
    d = setplan.describe(sub, list(range(len(sub))), j["opts"]["curve"])
    return {k: d[k] for k in ("harmonisch", "bekannt", "minuten")}


def _checked(j: dict, idx: list[int]) -> list[int]:
    if j.get("state") != "done":
        raise ValueError("Mix ist noch nicht fertig")
    n = len(j["items"])
    if not idx or len(set(idx)) != len(idx) or any(not isinstance(i, int) or i < 0 or i >= n for i in idx):
        raise ValueError("Auswahl passt nicht zum Mix")
    return idx


def save(jid: str, idx: list[int], name: str) -> dict:
    j = job(jid)
    idx = _checked(j, idx)
    name = (name or "").strip()[:120]
    if not name:
        raise ValueError("Bitte einen Namen eingeben")
    if any(p.name == name for p in store.local_playlists()):
        raise ValueError(f"Eine Playlist „{name}“ gibt es schon – bitte anderen Namen wählen")
    for i in idx:
        it = j["items"][i]
        store.add_to_playlist(name, Track(title=it["title"], artists=it["artists"], album=it.get("album"),
                                          isrc=it.get("isrc"), ids=it.get("ids") or {}, cover=it.get("cover"),
                                          preview_url=it.get("preview_url"), duration_ms=it.get("duration_ms")))
    return {"name": name, "count": len(idx)}

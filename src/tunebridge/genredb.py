"""Genre-Datenbank: eigene Einordnungen + Gemeinschafts-Datenbank.

Rechtlicher Rahmen (siehe DATENSCHUTZ.md): Hier landen nur *Urteile* – keine Daten, die aus fremden
Datenbanken (Spotify, TIDAL, Last.fm …) abgezogen wurden.
* Eigene Einordnung: was der Nutzer selbst bestätigt oder korrigiert hat. Quelle eines Vorschlags:
  „playlist“ (Genre-Name einer eigenen Playlist, lokal ausgewertet – der Name selbst verlässt nie den Rechner),
  „app“ (Ergebnis der App), „ki“ (KI hat NUR Künstler/Titel/Album/BPM gesehen, keine Tags der Dienste),
  „korrektur“ (vom Nutzer geändert).
* Eigene Einordnungen wirken sofort auf diesem Rechner (vor allem anderen).
* Mit Einwilligung „genres“ gehen sie pseudonym an den Server des Entwicklers (wie die übrigen Einträge:
  Song = Künstler/Titel/ISRC, Genre, Subgenre, Herkunft). Daraus baut der Entwickler auf seinem eigenen
  Rechner die Gemeinschafts-Datenbank (erst ab mehreren unabhängigen Installationen) und signiert sie.
* Mit Einwilligung „genredb“ lädt die App diese Datenbank (nur Song → Genre, keine Nutzerdaten) und prüft
  die Signatur, bevor sie benutzt wird.
"""

from __future__ import annotations

import json
import re
import threading
import time
import uuid

from . import config, store
from . import debuglog as dbg
from .matching import normalize
from .models import Track

SOURCES = ("korrektur", "playlist", "app", "ki")
NAMESPACE = "sh-tunebridge-genredb"
DB_FILE = "genredb.json"
CHECK_EVERY = 24 * 3600
MAX_PER_ANALYSIS = 2000
MAX_VOTES_PER_DAY = 5000

_SCHEMA = """
CREATE TABLE IF NOT EXISTS genre_votes(
  key TEXT PRIMARY KEY,          -- ISRC oder „künstler|titel“ (wie im Song-Speicher)
  alt TEXT,                      -- zweiter Schlüssel („künstler|titel“), falls key die ISRC ist
  artist TEXT, title TEXT, isrc TEXT,
  genre TEXT, subgenre TEXT,
  source TEXT,                   -- korrektur | playlist | app | ki
  uid TEXT, ts REAL, sent REAL);
CREATE INDEX IF NOT EXISTS genre_votes_alt ON genre_votes(alt);
"""
_ready: set[str] = set()
_lock = threading.Lock()
_community: dict = {"loaded": None, "data": None}


def _conn():
    return store._conn()


def _ensure(c) -> None:
    if str(store.DB) not in _ready:
        c.executescript(_SCHEMA)
        _ready.add(str(store.DB))


# ------------------------------------------------------------------ Schlüssel
def keys_of(artists: list[str] | str, title: str, isrc: str | None = None) -> list[str]:
    a = artists[0] if isinstance(artists, list) and artists else (artists if isinstance(artists, str) else "")
    out = [isrc.upper()] if isrc else []
    out.append(f"{normalize(a)}|{normalize(title or '')}")
    return out


def _valid(genre: str | None, sub: str | None) -> tuple[str | None, str | None]:
    from .genres import TAXONOMY
    if genre not in TAXONOMY:
        return None, None
    return genre, (sub if sub and sub in TAXONOMY[genre] and sub != "_" else None)


# ------------------------------------------------------------------ Playlist-Name -> Genre (nur lokal)
_PL_NOISE = re.compile(
    r"\b(my|meine?|mein|the|best|beste[nrs]?|top|hits?|songs?|tracks?|music|musik|playlist|mix(?:tape)?|vol|volume|"
    r"favou?rites?|favs?|lieblings\w*|collection|sammlung|for|f(?:ü|u)r|und|and|new|neue?|old|alte?|only|nur|"
    r"radio|session|set|edition|liste|list|daily|weekly|\d+)\b", re.I)


# Stimmungs-/Anlass-Wörter sind kein Genre-Urteil („Chill“ kann Lo-Fi, Pop oder Ambient sein)
_PL_MOOD = {"chill", "chillig", "dance", "party", "electronic", "edm", "vibes", "vibe", "relax", "study", "focus",
            "sleep", "workout", "gym", "mood", "summer", "sommer", "winter", "love", "sad", "happy", "car", "auto"}


def playlist_genre(name: str) -> tuple[str | None, str | None]:
    """Eindeutiger Genre-Name einer Playlist („Hardtekk 2024 🔥“ -> Techno/Hardtekk). Sonst (None, None).
    Läuft nur auf diesem Rechner – der Playlist-Name wird nie gesendet."""
    from .genres.classify import _lookup
    from .genres import TAXONOMY
    clean = normalize(_PL_NOISE.sub(" ", name or ""))
    if not clean or len(clean) < 3:
        return None, None
    words = [w for w in clean.split() if w not in _PL_MOOD]
    found: dict[str, str | None] = {}
    for size in range(min(4, len(words)), 0, -1):
        for i in range(len(words) - size + 1):
            hit, conf = _lookup(" ".join(words[i:i + size]))
            if hit and conf >= 1.0 and hit[0] in TAXONOMY:
                sub = hit[1] if hit[1] in TAXONOMY[hit[0]] else None
                if hit[0] not in found or (sub and not found[hit[0]]):
                    found[hit[0]] = sub
        if found:
            break
    if len(found) != 1:          # mehrere Richtungen („Rock & Techno“) -> keine Aussage
        return None, None
    g, s = next(iter(found.items()))
    return g, s


# ------------------------------------------------------------------ Eigene Einordnungen
def vote(artists: list[str], title: str, isrc: str | None, genre: str, subgenre: str | None, source: str) -> dict:
    genre, subgenre = _valid(genre, subgenre)
    if not genre:
        raise ValueError("Unbekanntes Genre")
    if source not in SOURCES:
        raise ValueError("Unbekannte Herkunft")
    ks = keys_of(artists, title, isrc)
    with _lock, _conn() as c:
        _ensure(c)
        day = time.time() - 86400
        if c.execute("SELECT COUNT(*) FROM genre_votes WHERE ts > ?", (day,)).fetchone()[0] >= MAX_VOTES_PER_DAY:
            raise ValueError(f"Tagesgrenze erreicht ({MAX_VOTES_PER_DAY} Einordnungen) – morgen weiter")
        old = c.execute("SELECT genre, subgenre, uid, sent FROM genre_votes WHERE key = ?", (ks[0],)).fetchone()
        changed = not old or (old["genre"], old["subgenre"]) != (genre, subgenre)
        c.execute("INSERT OR REPLACE INTO genre_votes(key, alt, artist, title, isrc, genre, subgenre, source, uid, ts, sent)"
                  " VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                  (ks[0], ks[-1] if len(ks) > 1 else None, ", ".join(artists) if isinstance(artists, list) else artists,
                   title, (isrc or "").upper() or None, genre, subgenre, source,
                   uuid.uuid4().hex if changed else old["uid"], time.time(), None if changed else old["sent"]))
    return {"key": ks[0], "genre": genre, "subgenre": subgenre, "source": source}


def own(artists, title: str, isrc: str | None = None) -> dict | None:
    ks = keys_of(artists, title, isrc)
    with _conn() as c:
        _ensure(c)
        for k in ks:
            r = c.execute("SELECT * FROM genre_votes WHERE key = ? OR alt = ? ORDER BY ts DESC LIMIT 1", (k, k)).fetchone()
            if r:
                return dict(r)
    return None


def votes(limit: int = 500) -> list[dict]:
    with _conn() as c:
        _ensure(c)
        return [dict(r) for r in c.execute("SELECT * FROM genre_votes ORDER BY ts DESC LIMIT ?", (limit,))]


def delete(keys: list[str] | None = None) -> int:
    with _lock, _conn() as c:
        _ensure(c)
        if keys is None:
            return c.execute("DELETE FROM genre_votes").rowcount
        return sum(c.execute("DELETE FROM genre_votes WHERE key = ?", (k,)).rowcount for k in keys)


def counts() -> dict:
    with _conn() as c:
        _ensure(c)
        r = c.execute("SELECT COUNT(*), SUM(sent IS NOT NULL) FROM genre_votes").fetchone()
        by = {row[0]: row[1] for row in c.execute("SELECT source, COUNT(*) FROM genre_votes GROUP BY source")}
    return {"total": r[0] or 0, "sent": r[1] or 0, "by_source": by}


# ------------------------------------------------------------------ Senden (über outbox.py)
def upload_entries(limit: int = 200) -> list[dict]:
    """Noch nicht gesendete Einordnungen – nur Song (Künstler/Titel/ISRC), Genre, Subgenre, Herkunft."""
    with _conn() as c:
        _ensure(c)
        rows = c.execute("SELECT * FROM genre_votes WHERE sent IS NULL ORDER BY ts LIMIT ?", (limit,)).fetchall()
    return [{"uid": r["uid"], "zeit": time.strftime("%Y-%m-%d", time.localtime(r["ts"])), "art": "genre",
             "song": {"artist": r["artist"], "title": r["title"], "isrc": r["isrc"]},
             "details": {"genre": r["genre"], "subgenre": r["subgenre"], "herkunft": r["source"],
                         "schluessel": [k for k in (r["key"], r["alt"]) if k]},   # wie im Song-Speicher (ISRC / künstler|titel)
             "_key": r["key"], "_ts": r["ts"]}
            for r in rows]


def mark_sent(keys: list[str]) -> None:
    now = time.time()
    with _lock, _conn() as c:
        _ensure(c)
        c.executemany("UPDATE genre_votes SET sent = ? WHERE key = ?", [(now, k) for k in keys])


# ------------------------------------------------------------------ Gemeinschafts-Datenbank
def _path():
    return config.DATA / DB_FILE


def _load_community() -> dict | None:
    p = _path()
    if not p.exists():
        return None
    mt = p.stat().st_mtime
    if _community["loaded"] == mt:
        return _community["data"]
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        if d.get("format") != 1 or not isinstance(d.get("songs"), dict):
            raise ValueError("Format")
    except (OSError, ValueError) as e:
        dbg.error("genredb", "Gemeinschafts-Datenbank unlesbar", e)
        return None
    _community.update(loaded=mt, data=d)
    return d


def community_info() -> dict:
    d = _load_community()
    return {"version": d.get("version"), "created": d.get("created"), "songs": len(d.get("songs") or {})} if d else {}


def _verify(data: bytes, sig: bytes) -> None:
    from importlib import resources

    from . import sshsig
    signers = (resources.files("tunebridge") / "release_signers").read_text(encoding="utf-8")
    sshsig.verify(data, sig, signers, "sh-tunebridge", NAMESPACE)


def update(force: bool = False) -> dict:
    """Gemeinschafts-Datenbank vom Server holen (nur mit Einwilligung „genredb“). Nur signierte Dateien."""
    import httpx

    from . import consent, upload
    if not consent.server("genredb"):
        return {"ok": False, "why": "nicht erlaubt"}
    last = float(store.meta_get("genredb:checked") or 0)
    if not force and time.time() - last < CHECK_EVERY:
        return {"ok": True, "skipped": True, **community_info()}
    store.meta_set("genredb:checked", str(time.time()))
    h = {"User-Agent": "SH-Tunebridge"}
    try:
        meta = httpx.get(upload.URL + "/v1/genredb/meta", headers=h, timeout=15)
        if meta.status_code == 404:
            return {"ok": True, "none": True}
        meta.raise_for_status()
        ver = int(meta.json().get("version") or 0)
        if ver and ver <= int((community_info() or {}).get("version") or 0) and not force:
            return {"ok": True, "current": True, **community_info()}
        data = httpx.get(upload.URL + "/v1/genredb", headers=h, timeout=60)
        sig = httpx.get(upload.URL + "/v1/genredb.sig", headers=h, timeout=15)
        data.raise_for_status()
        sig.raise_for_status()
    except (httpx.HTTPError, ValueError) as e:
        dbg.error("genredb", "Gemeinschafts-Datenbank nicht geladen", e)
        return {"ok": False, "why": f"Server nicht erreichbar: {e}"}
    try:
        _verify(data.content, sig.content)
        d = json.loads(data.content)
        if d.get("format") != 1 or not isinstance(d.get("songs"), dict):
            raise ValueError("unbekanntes Format")
    except Exception as e:  # noqa: BLE001 – unsignierte/kaputte Datei wird NIE benutzt
        dbg.problem("genredb", f"Gemeinschafts-Datenbank verworfen: {e}")
        return {"ok": False, "why": "Signatur ungültig – Datei verworfen"}
    tmp = _path().with_suffix(".tmp")
    tmp.write_bytes(data.content)
    tmp.replace(_path())
    dbg.event("genredb", "Gemeinschafts-Datenbank aktualisiert", version=d.get("version"), songs=len(d["songs"]))
    return {"ok": True, "updated": True, **community_info()}


def remove_community() -> None:
    _path().unlink(missing_ok=True)
    _community.update(loaded=None, data=None)


# ------------------------------------------------------------------ Anwenden
def lookup(track: Track) -> dict | None:
    """-> {genre, subgenre, from: eigene|gemeinschaft, …} oder None. Eigene Einordnung geht vor."""
    try:
        o = own(track.artists, track.title, track.isrc)
    except Exception as e:  # noqa: BLE001
        dbg.error("genredb", "Eigene Einordnungen nicht lesbar", e)
        o = None
    if o:
        return {"genre": o["genre"], "subgenre": o["subgenre"], "from": "eigene", "source": o["source"]}
    from . import consent
    if not consent.server("genredb"):
        return None
    d = _load_community()
    if not d:
        return None
    for k in keys_of(track.artists, track.title, track.isrc):
        if (hit := d["songs"].get(k)):
            g, s = _valid(hit[0], hit[1] if len(hit) > 1 else None)
            if g:
                return {"genre": g, "subgenre": s, "from": "gemeinschaft", "votes": hit[2] if len(hit) > 2 else None,
                        "version": d.get("version")}
    return None


def apply(track: Track, extra: dict) -> bool:
    """Eigene Einordnung / Gemeinschafts-Datenbank auf ein Ergebnis anwenden. -> True, wenn geändert."""
    hit = lookup(track)
    if not hit:
        return False
    if (track.genre, track.subgenre) != (hit["genre"], hit["subgenre"]):
        extra["genre_before"] = [track.genre, track.subgenre]
        if track.genre != hit["genre"]:
            track.niche = None
        track.genre, track.subgenre = hit["genre"], hit["subgenre"]
    extra["genre_source"] = "eigene Einordnung" if hit["from"] == "eigene" else "Gemeinschafts-Datenbank"
    extra["genredb"] = hit
    extra["confidence"] = max(float(extra.get("confidence") or 0), 0.95)
    return True


# ------------------------------------------------------------------ Playlists analysieren
_jobs: dict[str, dict] = {}


def _load_tracks(sid: str, pid: str) -> tuple[str, list[Track]]:
    if sid == "local":
        pl = next((p for p in store.local_playlists() if p.name == pid), None)
        if not pl:
            raise ValueError("Playlist nicht gefunden")
        return pl.name, list(pl.tracks)
    from . import services
    name, tracks = services.load(sid, pid)
    if not name:
        name = next((p.get("name", "") for p in services.playlists(sid) if str(p.get("id")) == str(pid)), "")
    return name, tracks


def _propose(it: dict) -> None:
    """Vorschlag + Status aus App-Ergebnis, Playlist-Genre und KI-Urteil (alles lokal)."""
    app_g, app_s, conf = it.get("app_genre"), it.get("app_subgenre"), it.get("confidence") or 0
    pl_g, pl_s = it.get("pl_genre"), it.get("pl_subgenre")
    ki = it.get("ki") or {}
    ki_g, ki_s = ki.get("genre"), ki.get("subgenre")
    if it.get("own"):
        o = it["own"]
        it.update(genre=o["genre"], subgenre=o["subgenre"], source=o["source"], status="eingeordnet")
        return
    if pl_g:
        sub = pl_s or (app_s if app_g == pl_g else None) or (ki_s if ki_g == pl_g else None)
        clash = (app_g and app_g != pl_g and conf >= 0.5) or (ki_g and ki_g != pl_g)
        it.update(genre=pl_g, subgenre=sub, source="playlist", status="pruefen" if clash else "ok")
    elif app_g and ki_g:
        same = app_g == ki_g
        it.update(genre=app_g, subgenre=app_s or (ki_s if same else None), source="app",
                  status="ok" if same and conf >= 0.4 else "pruefen")
    elif app_g:
        it.update(genre=app_g, subgenre=app_s, source="app", status="ok" if conf >= 0.6 else "pruefen")
    elif ki_g:
        it.update(genre=ki_g, subgenre=ki_s, source="ki", status="pruefen")
    else:
        it.update(genre=None, subgenre=None, source=None, status="offen")


def _run(job: dict) -> None:
    from .linkimport import _analyse_one
    try:
        job["state"] = "loading"
        name, tracks = _load_tracks(job["sid"], job["pid"])
        job["name"] = name
        pl_g, pl_s = playlist_genre(name)
        job["playlist_genre"] = [pl_g, pl_s]
        job["cut"] = max(0, len(tracks) - MAX_PER_ANALYSIS)
        tracks = tracks[:MAX_PER_ANALYSIS]
        job["total"], job["state"] = len(tracks), "analysing"
        for i, t in enumerate(tracks):
            if job["cancel"]:
                raise InterruptedError
            try:
                a = _analyse_one(t)
            except Exception as e:  # noqa: BLE001 – ein Song darf nicht alles abbrechen
                dbg.error("genredb", "Song-Analyse fehlgeschlagen", e)
                a = {"title": t.title, "artists": t.artists, "isrc": t.isrc, "genre": None, "cover": t.cover}
            it = {"i": i, "title": a.get("title") or t.title, "artists": a.get("artists") or t.artists,
                  "album": a.get("album") or t.album, "isrc": a.get("isrc") or t.isrc, "cover": a.get("cover"),
                  "bpm": a.get("bpm"), "app_genre": a.get("genre"), "app_subgenre": a.get("subgenre"),
                  "confidence": a.get("confidence"), "pl_genre": pl_g, "pl_subgenre": pl_s,
                  "own": own(a.get("artists") or t.artists, a.get("title") or t.title, a.get("isrc") or t.isrc)}
            _propose(it)
            job["items"].append(it)
            job["done"] = i + 1
        if job["use_ai"]:
            job["state"] = "ai"
            from . import ai
            todo = [it for it in job["items"] if not it.get("own")]
            try:
                for f in ai.judge_genres(todo, cancel=lambda: job["cancel"]):
                    it = todo[f["i"]]
                    it["ki"] = {"genre": f["genre"], "subgenre": f.get("subgenre"), "n": f.get("n", 1)}
                    _propose(it)
            except Exception as e:  # noqa: BLE001
                job["ai_error"] = str(e)
                dbg.error("genredb", "KI-Einschätzung fehlgeschlagen", e)
        job["state"] = "done"
    except InterruptedError:
        job["state"] = "cancelled"
    except Exception as e:  # noqa: BLE001
        dbg.error("genredb", "Playlist-Analyse abgebrochen", e)
        job.update(state="error", error=str(e))
    job["finished"] = time.time()


def start(sid: str, pid: str, use_ai: bool = False) -> str:
    jid = uuid.uuid4().hex[:10]
    _jobs[jid] = {"id": jid, "sid": sid, "pid": pid, "use_ai": use_ai, "name": "", "state": "queued", "done": 0,
                  "total": 0, "items": [], "cancel": False, "started": time.time()}
    threading.Thread(target=_run, args=(_jobs[jid],), daemon=True).start()
    for k in [k for k, j in _jobs.items() if time.time() - j["started"] > 6 * 3600]:
        _jobs.pop(k, None)
    return jid


def job(jid: str) -> dict | None:
    j = _jobs.get(jid)
    return {k: v for k, v in j.items() if k != "cancel"} if j else None


def cancel(jid: str) -> None:
    if jid in _jobs:
        _jobs[jid]["cancel"] = True


def accept(jid: str, rows: list[dict]) -> dict:
    """rows: [{i, genre, subgenre}] – vom Nutzer bestätigt oder geändert. Geändert = „korrektur“."""
    j = _jobs.get(jid)
    if not j:
        raise ValueError("Auftrag nicht gefunden (abgelaufen?) – bitte neu analysieren")
    saved = 0
    for r in rows:
        try:
            it = j["items"][int(r["i"])]
        except (KeyError, IndexError, TypeError, ValueError):
            continue
        g, s = _valid(r.get("genre"), r.get("subgenre"))
        if not g:
            continue
        src = it.get("source") if (g, s) == (it.get("genre"), it.get("subgenre")) and it.get("source") else "korrektur"
        if it.get("own") and (g, s) == (it["own"]["genre"], it["own"]["subgenre"]):
            continue                        # unverändert schon eingeordnet
        vote(it["artists"], it["title"], it.get("isrc"), g, s, src)
        it["own"] = {"genre": g, "subgenre": s, "source": src}
        it.update(genre=g, subgenre=s, source=src, status="eingeordnet")
        saved += 1
    return {"saved": saved}

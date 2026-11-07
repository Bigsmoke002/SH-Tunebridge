"""Backend der Oberfläche (FastAPI). Wird von `tunebridge app` (eigenes Fenster)
oder `tunebridge ui` (Browser) gestartet."""

from __future__ import annotations

import asyncio
import os
import re
import threading
import time
from collections import Counter
from dataclasses import asdict
from importlib.resources import files
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .. import backup, config, debuglog as dbg, store
from ..enrich import enrich
from ..genres import TAXONOMY, classify
from ..links import links as platform_links
from ..models import Track
from ..providers import PROVIDERS
from ..recognize import capture, meter, players, variants
from ..recognize.engines import available, recognize, shazam_paused
from ..split import split_by_genre
from ..suggest import suggest

app = FastAPI(title="SH-Tunebridge")
from .guard import GuardMiddleware  # noqa: E402
app.add_middleware(GuardMiddleware)   # fremde Webseiten / DNS-Rebinding abweisen


@app.middleware("http")
async def _debug_requests(request: Request, call_next):
    """Debug-Protokoll: jeder Fehler (4xx/5xx, Ausnahmen) mit Pfad und – bei 5xx – Traceback."""
    t0 = time.time()
    try:
        resp = await call_next(request)
    except Exception as e:
        dbg.error("server", f"{request.method} {request.url.path} abgestürzt", e)
        raise
    if resp.status_code >= 400 and dbg.enabled():
        dbg.problem("server", f"{request.method} {request.url.path} -> {resp.status_code}",
                    dauer_ms=round((time.time() - t0) * 1000))
    return resp


@app.on_event("startup")
async def _traffic_discord():
    from .. import autosync, discord_rpc, traffic
    traffic.install()          # Datenverbrauch zählen (nur lokal)
    discord_rpc.start()        # nur wenn eingeschaltet
    if not os.environ.get("TUNEBRIDGE_NO_AUTOSYNC"):
        autosync.start()       # Abgleich mit verbundenen Diensten (nur wenn eingeschaltet)


@app.on_event("shutdown")
async def _traffic_flush():
    from .. import traffic
    try:
        traffic.flush()
    except Exception:  # noqa: BLE001
        pass


def _discord_song(track: Track, extra: dict) -> None:
    try:
        from .. import discord_rpc
        if discord_rpc.settings()["enabled"]:
            dz = (track.ids or {}).get("deezer")
            discord_rpc.RPC.on_song(track.title, list(track.artists), track.cover, track.genre, track.subgenre,
                                    f"https://www.deezer.com/track/{dz}" if dz else None)
    except Exception as e:  # noqa: BLE001 – Discord darf die Erkennung nie stören
        dbg.error("discord", "Discord-Status nicht aktualisiert", e)


@app.on_event("startup")
async def _songcache_backfill():
    from .. import songcache
    try:
        await asyncio.to_thread(songcache.backfill)
    except Exception as e:
        dbg.error("speicher", "Übernahme aus dem Verlauf fehlgeschlagen", e)


@app.on_event("startup")
async def _auto_backup():
    async def run():
        while True:          # beim Start und danach stündlich prüfen, ob eine Sicherung fällig ist
            try:
                await asyncio.to_thread(backup.auto_backup)
            except Exception as e:  # Backup darf nie etwas anderes stören (z. B. Platte nicht eingehängt)
                dbg.error("sicherung", "Automatische Sicherung fehlgeschlagen", e)
            await asyncio.sleep(3600)
    asyncio.get_running_loop().create_task(run())
_WEB = files("tunebridge.web")
app.mount("/static", StaticFiles(directory=str(_WEB / "static")), name="static")


def _all_playlists():
    return store.local_playlists() + store.exported_playlists()


def _track_payload(track: Track) -> dict:
    key = store.track_key(track)
    in_pl = [p.name for p in store.local_playlists() if any(store.track_key(t) == key for t in p.tracks)]
    return {"track": asdict(track), "key": key, "in_playlists": in_pl,
            "suggestions": [asdict(s) for s in suggest(track, _all_playlists())]}


def _payload(rid: int):
    got = store.get_recognition(rid)
    if not got:
        raise HTTPException(404)
    track, extra = got
    track.cover = track.cover or extra.get("cover")
    track.preview_url = track.preview_url or extra.get("preview_url")
    from .. import aidetect
    extra["ai"] = aidetect.check(track, extra)      # immer aktuell (z. B. nach eigener Markierung)
    return {"id": rid, "extra": extra, **_track_payload(track)}


def _asset_version() -> str:
    """Kennung aus Änderungszeit/Größe von CSS+JS – das App-Fenster lädt nach jeder Änderung frisch
    (sonst zeigt Qt WebEngine u. U. die alte, zwischengespeicherte app.css)."""
    import hashlib
    h = hashlib.sha1()
    for f in ("app.css", "app.js", "icon.svg"):
        st = (_WEB / "static" / f).stat()
        h.update(f"{f}{st.st_mtime_ns}{st.st_size}".encode())
    return h.hexdigest()[:10]


@app.get("/", response_class=HTMLResponse)
def index():
    v = _asset_version()
    html = (_WEB / "index.html").read_text(encoding="utf-8")
    for f in ("app.css", "app.js", "icon.svg"):
        html = html.replace(f"/static/{f}\"", f"/static/{f}?v={v}\"")
    return HTMLResponse(html, headers={"Cache-Control": "no-cache"})


# ------------------------------------------------------------------ Status
@app.get("/api/status")
def status():
    return {"host": store.HOST, "engines": available(), "apps": capture.pipewire_ok(), "lastfm": bool(config.opt("LASTFM_API_KEY")),
            "llm": __import__("tunebridge.ai", fromlist=["x"]).ready()[0], "data": str(config.DATA), "config": str(config.CONFIG_FILE),
            "stats": store.stats(),
            "taxonomy": {g: [x for x in subs if x != "_"] for g, subs in TAXONOMY.items()},
            "version": __import__("tunebridge").__version__}


@app.get("/api/sources")
def sources():
    return [asdict(s) for s in capture.sources() + capture.apps()]


@app.get("/api/sources/scan")
async def scan_sources(kind: str | None = None):
    """Alle Geräte kurz anhören – welches bekommt gerade Ton?"""
    return await meter.scan(kind)


@app.websocket("/ws/level")
async def ws_level(ws: WebSocket, source: str = "desktop"):
    """Live-Pegel + Spektrum (~25 fps) der gewählten Quelle."""
    await ws.accept()
    try:
        async for frame in meter.levels(source):
            await ws.send_json(frame)
    except (WebSocketDisconnect, RuntimeError, asyncio.IncompleteReadError):
        pass
    except Exception as e:
        try:
            await ws.send_json({"error": str(e)})
        except Exception:
            pass


# ------------------------------------------------------------------ Erkennen
class ListenReq(BaseModel):
    mode: str = "desktop"   # desktop | mic – bestimmt, welche Einwilligung gilt
    source: str = "desktop"
    seconds: float = 10
    skip_key: str | None = None
    force: bool = False     # True = lokalen Wiedererkenner überspringen, immer online prüfen
    auto: bool = False      # Dauer-Modus (keine zusätzliche Tempo-Suche)
    tempo: bool = False     # ausdrücklich nach Slowed/Sped-up suchen (Knopf nach „Nichts erkannt“)


def _left(track: Track, pos: float | None, rec_start: float) -> float | None:
    """Wie lange läuft der Song noch (Sekunden)?"""
    if not track.duration_ms or pos is None:
        return None
    return round(track.duration_ms / 1000 - pos - (time.time() - rec_start), 1)


@app.post("/api/listen")
async def listen(req: ListenReq):
    from .. import songcache
    from ..recognize import localfp, players
    mode = "mic" if req.mode == "mic" else "desktop"
    prefs = _prefs()
    if mode == "mic" and not prefs["mic_ack"]:
        raise HTTPException(403, "Bitte zuerst den Mikrofon-Hinweis bestätigen")
    # Rohaudio (AudD/ACRCloud) nur mit ausdrücklicher Einwilligung – sonst nur Shazam (lokaler Fingerabdruck)
    engines = None if prefs[f"send_audio_{mode}"] is True else [e for e in available() if e == "shazam"]
    src_kind = ("anwendung" if req.source.startswith(capture.APP_PREFIX) else
                "standard" if req.source in ("desktop", "mic") else "gerät")
    dbg.event("erkennen", "Start", modus=mode, quelle=req.source, art=src_kind, sekunden=req.seconds,
              dienste=engines or available(), rohaudio=prefs[f"send_audio_{mode}"] is True, erzwungen=req.force)
    rec_start = time.time()
    try:
        wav = await asyncio.to_thread(capture.record, req.source, max(3, min(req.seconds, 30)))
    except Exception as e:
        dbg.error("erkennen", "Aufnahme fehlgeschlagen", e, quelle=req.source)
        raise HTTPException(500, f"Aufnahme fehlgeschlagen: {e}")
    from .. import consent
    cons = consent.get()["local"]
    player = players.minimal(await asyncio.to_thread(players.current)) \
        if mode == "desktop" and cons["player"] else None
    variant, notice, hashes, res, tempo_offer = None, None, [], None, False
    try:
        level = await asyncio.to_thread(meter.wav_level, wav)
        if level <= meter.SILENT_DB:
            # Stille: gar nicht erst an die Dienste schicken
            dbg.problem("erkennen", "Stille – nichts gesendet", pegel_db=round(level, 1), quelle=req.source)
            return {"found": False, "silent": True, "level_db": round(level, 1), "errors": {}}
        # 1) Lokal: kennt die App genau diese Stelle schon? Dann keine Online-Anfrage.
        try:
            if cons["cache"]:
                hashes = await asyncio.to_thread(localfp.fingerprint, wav)
            m = None if req.force or not hashes else await asyncio.to_thread(localfp.match, hashes)
        except Exception as e:
            dbg.error("lokal", "Fingerabdruck fehlgeschlagen", e)
            m = None
        if m and (got := songcache.lookup_key(localfp.parse_ref(m["ref"])[0])):
            track, extra = got
            if extra.get("gcheck", 0) < songcache.GENRE_CHECK:
                # Eintrag stammt von vor der Künstler-/Titel-Prüfung -> Infos einmal frisch nachschlagen
                from ..recognize.engines import Recognition as _Rec
                try:
                    track, fresh_x = await asyncio.to_thread(enrich, _Rec(
                        engine="lokal", title=track.title, artists=track.artists, album=track.album, isrc=track.isrc,
                        cover=track.cover, preview_url=track.preview_url, duration_ms=track.duration_ms), True)
                    extra = {**extra, **fresh_x, "cached": None}
                except Exception as e:  # noqa: BLE001 – offline: alten Stand zeigen
                    dbg.error("lokal", "Song-Infos ließen sich nicht auffrischen", e)
            from ..enrich import _known
            _known(track, extra)
            speed = localfp.parse_ref(m["ref"])[1]
            extra.update(engines=["lokal"], agreement=1, alternatives=[], local=m,
                         speed=None if speed == 1.0 else speed)
            store.bump_saved("shazam")
            pos = m["pos_frames"] / localfp.FPS if m["pos_frames"] > 0 else None
            dbg.event("erkennen", "Lokal erkannt – keine Shazam-Anfrage", song=f"{track.artist} – {track.title}", **m)
            if req.skip_key and req.skip_key == store.track_key(track):
                return {"found": True, "same": True, "local": True, "left": _left(track, pos, rec_start)}
            rid = store.add_recognition(req.source, "lokal", 1, track, extra)
            _discord_song(track, extra)
            return {"found": True, "local": True, "left": _left(track, pos, rec_start), "errors": {}, **_payload(rid)}
        # 2) Online (Shazam pausiert? Dann gar nicht erst senden.)
        if (wait := shazam_paused()):
            dbg.problem("erkennen", "Abgelehnt: Shazam-Limit aktiv", noch_s=round(wait))
            return {"found": False, "limited": True, "wait": round(wait),
                    "errors": {"shazam": f"Shazam-Limit erreicht – wieder frei in {round(wait)} s"}}
        res = await recognize(wav, engines)
        dbg.event("erkennen", "Ergebnis der Dienste", pegel_db=round(level, 1),
                  treffer=[f"{r.engine}: {', '.join(r.artists)} – {r.title} (skew {r.skew}, ab {r.offset} s)" for r in res.all],
                  fehler=res.errors, einig=res.agreement)
        # Slowed/Sped-up? Nur Shazam-Fingerabdrücke der lokal umgerechneten Aufnahme, kein Audio
        variants.LAST_SEEN.clear()
        if variants.suspicious(res.best):
            from .. import ratelimit
            free = ratelimit.free("shazam")
            tries = 0 if shazam_paused() else (min(variants.MAX_TRIES, free) if req.tempo else variants.tries_allowed(free))
            if req.auto:
                # Dauer-Modus: keine Tempo-Suche – ein unbekannter Song würde sonst jede Runde das Budget aufbrauchen
                dbg.event("erkennen", "Dauer-Modus: Tempo-Suche ausgelassen")
            elif res.best is None and not req.tempo:
                # Gar kein Treffer: nicht automatisch 3 weitere Anfragen hinterherschicken (Shazam sperrt sonst schnell).
                # Die Tempo-Suche gibt es dann per Knopf („Als Slowed/Sped-up suchen“).
                tempo_offer = True
                dbg.event("erkennen", "Kein Treffer – Tempo-Suche nur auf Wunsch")
            elif not tries:
                notice = "Tempo-Suche (Slowed/Sped-up) diesmal ausgelassen – spart Shazam-Anfragen"
                dbg.problem("erkennen", notice, frei=ratelimit.free("shazam"))
            else:
                dbg.event("erkennen", "Unsicher/kein Treffer – suche Slowed/Sped-up-Version", versuche=tries)
                # höchstens 3 Versuche und immer genug Reserve, damit der nächste Scan sofort geht
                variant = await variants.find(wav, max_tries=tries)
    finally:
        wav.unlink(missing_ok=True)
    best, hits = res.best, list(res.all)
    if variant and not (best and variant.same_song(best)):
        best, hits = variant, [variant, *hits]
    if not best:
        dbg.problem("erkennen", "Nichts erkannt", pegel_db=round(level, 1), fehler=res.errors, quelle=req.source)
        try:
            if cons["misses"]:
                store.miss_add("unerkannt", req.source, round(level, 1), player, None,
                               {"dienste": engines or available(), "fehler": res.errors, "hinweis": notice,
                                "unsichere_treffer": [f"{', '.join(r.artists)} – {r.title} (skew {r.skew})"
                                                      for r in res.all],
                                "tempo_versuche": variants.LAST_SEEN, "sekunden": req.seconds})
        except Exception as e:
            dbg.error("erkennen", "Nicht-erkannt-Eintrag fehlgeschlagen", e)
        return {"found": False, "silent": False, "level_db": round(level, 1), "errors": res.errors,
                "notice": notice, "missed": True, "tempo_offer": tempo_offer}
    if variant is best:
        dbg.event("erkennen", "Über Tempo-Korrektur gefunden", song=f"{best.artists} – {best.title}", tempo=best.speed,
                  vorher=res.best and f"{res.best.artists} – {res.best.title}")
    track, extra = await asyncio.to_thread(enrich, best)
    extra["engines"] = [best.engine] if variant is best else [r.engine for r in res.all]
    extra["agreement"] = 1 if variant is best else res.agreement
    extra["alternatives"] = [f"{', '.join(r.artists)} – {r.title} ({r.engine})"
                             for r in hits if not r.same_song(best)]
    # Sicheren Treffer lokal merken -> nächstes Mal ggf. ohne Shazam
    if hashes and (variant is best or not variants.suspicious(best)):
        try:
            await asyncio.to_thread(localfp.remember, songcache.primary_key(best), best.speed, hashes,
                                    None if variant is best else best.offset)
        except Exception as e:
            dbg.error("lokal", "Fingerabdruck nicht gespeichert", e)
    if not track.genre and cons["misses"]:
        try:
            store.miss_add("genre", req.source, round(level, 1), player,
                           {"artist": track.artist, "title": track.title, "isrc": track.isrc},
                           {"tags": dict(sorted((track.tags or {}).items(), key=lambda kv: -kv[1])[:25]),
                            "quelle": extra.get("genre_source")})
        except Exception as e:
            dbg.error("erkennen", "Genre-unbekannt-Eintrag fehlgeschlagen", e)
    pos = best.offset if variant is not best else None
    left = _left(track, pos, rec_start)
    if req.skip_key and req.skip_key == store.track_key(track):
        return {"found": True, "same": True, "left": left, "cached": bool(extra.get("cached"))}
    rid = store.add_recognition(req.source, best.engine, res.agreement, track, extra)
    _discord_song(track, extra)
    return {"found": True, "errors": res.errors, "notice": notice, "left": left,
            "cached": bool(extra.get("cached")), **_payload(rid)}


@app.websocket("/ws/hold")
async def ws_hold(ws: WebSocket, source: str = "desktop", limit: float = 60):
    """Dauer-Modus: lokal warten, bis der Song wechselt (siehe recognize/hold.py)."""
    from ..recognize import hold
    await ws.accept()
    try:
        async for ev in hold.watch(source, min(max(5.0, limit), 300.0)):
            await ws.send_json(ev)
            if ev.get("done"):
                dbg.event("dauer", "Songwechsel-Wache beendet", grund=ev["why"])
                break
    except (WebSocketDisconnect, RuntimeError):
        pass
    except LookupError as e:
        await ws.send_json({"done": True, "why": "fehler", "error": str(e)})
    finally:
        try:
            await ws.close()
        except RuntimeError:
            pass


@app.post("/api/recognition/{rid}/refresh")
async def recognition_refresh(rid: int):
    """„Neu laden“: Genre/Cover/Links des Songs frisch online nachschlagen."""
    from ..recognize.engines import Recognition
    got = store.get_recognition(rid)
    if not got:
        raise HTTPException(404)
    t, old = got
    rec = Recognition(engine="speicher", title=t.title, artists=t.artists, album=t.album, isrc=t.isrc,
                      cover=old.get("cover"), preview_url=old.get("preview_url"), links=old.get("links") or {},
                      label=old.get("label"), year=old.get("year"), duration_ms=t.duration_ms, speed=old.get("speed"))
    track, extra = await asyncio.to_thread(enrich, rec, True)
    for k in ("engines", "agreement", "alternatives", "version", "speed"):
        if k in old:
            extra[k] = old[k]
    store.update_recognition(rid, asdict(track), extra)
    return _payload(rid)


@app.get("/api/recognition/{rid}")
def recognition(rid: int):
    return _payload(rid)


@app.get("/api/history")
def history(limit: int = 200):
    return [{"id": h["id"], "ts": h["ts"], "host": h["host"], "engine": h["engine"], "source": h["source"],
             "title": h["track"]["title"], "artists": h["track"]["artists"],
             "genre": h["track"]["genre"], "subgenre": h["track"]["subgenre"],
             "cover": h["track"].get("cover") or h["extra"].get("cover"),
             "preview_url": h["track"].get("preview_url") or h["extra"].get("preview_url"),
             "isrc": h["track"].get("isrc"), "ids": h["track"].get("ids") or {},
             "bpm": h["extra"].get("bpm")} for h in store.history(limit)]


# ------------------------------------------------------------------ Mix-Tracklists (Verlauf)
@app.get("/api/mixlog")
def mixlog_list():
    from .. import mixlog
    return mixlog.overview()


@app.get("/api/mixlog/{sid}")
def mixlog_get(sid: int, fmt: str = "offset", genre: bool = False):
    from .. import mixlog
    s = mixlog.find(sid)
    if not s:
        raise HTTPException(404, "Sitzung nicht gefunden")
    return {**{k: v for k, v in s.items() if k != "songs"}, "songs": s["songs"],
            "text": mixlog.tracklist(s, fmt if fmt in ("offset", "clock", "plain") else "offset", genre)}


class MixlogSaveReq(BaseModel):
    name: str


@app.post("/api/mixlog/{sid}/save")
def mixlog_save(sid: int, req: MixlogSaveReq):
    from .. import mixlog
    s = mixlog.find(sid)
    name = req.name.strip()[:120]
    if not s or not name:
        raise HTTPException(400, "Sitzung oder Name fehlt")
    added = 0
    for x in s["songs"]:
        added += store.add_to_playlist(name, Track(title=x["title"], artists=x["artists"], isrc=x.get("isrc"), ids=x.get("ids") or {},
                                                   cover=x.get("cover"), preview_url=x.get("preview_url"), genre=x.get("genre"),
                                                   subgenre=x.get("subgenre")))
    return {"name": name, "added": added}


# ------------------------------------------------------------------ Statistik
@app.get("/api/stats")
def stats_get(year: str = "", source: str = "alle"):
    from .. import stats
    y = int(year) if year.isdigit() else None
    return stats.overview(y, source)


# ------------------------------------------------------------------ Set-Planer
def _sp(fn, *a):
    try:
        return fn(*a)
    except ValueError as e:
        raise HTTPException(400, str(e))


class SetStartReq(BaseModel):
    playlist: str


class SetOrderReq(BaseModel):
    curve: str = "peak"


class SetOutReq(BaseModel):
    order: list[int]
    fmt: str = "m3u8"
    name: str = ""


@app.get("/api/setplan/curves")
def setplan_curves():
    from .. import setplan
    return [{"id": k, "name": v[0], "hint": v[1]} for k, v in setplan.CURVES.items()]


@app.post("/api/setplan/start")
def setplan_start(req: SetStartReq):
    from .. import setplan
    return {"job": _sp(setplan.start, req.playlist)}


@app.get("/api/setplan/{jid}")
def setplan_job(jid: str):
    from .. import setplan
    j = _sp(setplan.job, jid)
    return {k: v for k, v in j.items() if k != "cancel"}


@app.post("/api/setplan/{jid}/cancel")
def setplan_cancel(jid: str):
    from .. import setplan
    _sp(setplan.job, jid)["cancel"] = True
    return {"ok": True}


@app.post("/api/setplan/{jid}/order")
def setplan_order(jid: str, req: SetOrderReq):
    from .. import setplan
    j = _sp(setplan.job, jid)
    if j["state"] != "done":
        raise HTTPException(400, "Analyse läuft noch")
    curve = req.curve if req.curve in setplan.CURVES else "peak"
    return setplan.describe(j["items"], setplan.order(j["items"], curve), curve)


@app.post("/api/setplan/{jid}/describe")
def setplan_describe(jid: str, req: SetOutReq, curve: str = "peak"):
    """Eigene Reihenfolge (nach Verschieben von Hand) neu bewerten."""
    from .. import setplan
    j = _sp(setplan.job, jid)
    return setplan.describe(j["items"], _sp(setplan._checked_order, j, req.order), curve if curve in setplan.CURVES else "peak")


@app.post("/api/setplan/{jid}/export")
def setplan_export(jid: str, req: SetOutReq):
    from .. import setplan
    if req.fmt == "txt" and req.name == "clipboard":
        return {"text": _sp(setplan.render, _sp(setplan.job, jid), req.order, "txt")}
    return _sp(setplan.export, jid, req.order, req.fmt)


@app.post("/api/setplan/{jid}/save")
def setplan_save(jid: str, req: SetOutReq):
    from .. import setplan
    return _sp(setplan.save, jid, req.order, req.name)


# ------------------------------------------------------------------ Mix erstellen
class MixStartReq(BaseModel):
    seeds: list[dict] = []
    opts: dict = {}
    genre: dict | None = None


class MixPickReq(BaseModel):
    order: list[int]
    name: str = ""


@app.get("/api/mix/levels")
def mix_levels():
    from .. import mixgen
    return {"levels": [{"id": k, "name": v["name"], "hint": v["hint"]} for k, v in mixgen.LEVELS.items()],
            "count": mixgen.COUNT_DEFAULT, "count_max": mixgen.COUNT_MAX, "max_seeds": mixgen.MAX_SEEDS}


@app.get("/api/mix/artists")
def mix_artists(q: str = ""):
    """Künstler bei Deezer suchen (nur der eingegebene Name geht an Deezer, nichts wird gespeichert)."""
    from .. import mixgen
    import httpx

    from ..ratelimit import LimitReached
    try:
        return mixgen.search_artists(q)
    except LimitReached as e:
        raise HTTPException(429, str(e))
    except (httpx.HTTPError, ValueError) as e:
        raise HTTPException(502, f"Deezer antwortet gerade nicht ({e.__class__.__name__})")


@app.post("/api/mix/start")
def mix_start(req: MixStartReq):
    from .. import mixgen
    return {"job": _sp(mixgen.start, req.seeds, req.opts, req.genre)}


@app.get("/api/mix/{jid}")
def mix_job(jid: str):
    from .. import mixgen
    return mixgen.public(_sp(mixgen.job, jid))


@app.post("/api/mix/{jid}/cancel")
def mix_cancel(jid: str):
    from .. import mixgen
    _sp(mixgen.job, jid)["cancel"] = True
    return {"ok": True}


@app.post("/api/mix/{jid}/describe")
def mix_describe(jid: str, req: MixPickReq):
    from .. import mixgen
    return _sp(mixgen.describe, jid, req.order)


@app.post("/api/mix/{jid}/save")
def mix_save(jid: str, req: MixPickReq):
    from .. import mixgen
    return _sp(mixgen.save, jid, req.order, req.name)


# ------------------------------------------------------------------ Doppelte Songs
@app.get("/api/dupes")
def dupes_find():
    from .. import dupes
    return dupes.find()


class DupesRemoveReq(BaseModel):
    items: list[dict]


@app.post("/api/dupes/remove")
def dupes_remove(req: DupesRemoveReq):
    from .. import dupes
    return {"removed": dupes.remove(req.items[:5000])}


# ------------------------------------------------------------------ Playlists
@app.get("/api/playlists")
def playlists():
    out, times = [], store.playlist_times()
    for p in store.local_playlists():
        created, updated = times.get(p.name, (0, 0))
        out.append({"name": p.name, "count": len(p.tracks), "origin": "lokal", "created": created, "updated": updated,
                    "covers": [t.cover for t in p.tracks if t.cover][-4:],
                    "top": [[d["label"], d["count"], d["genre"], d["subgenre"]] for d in _dist(p.tracks)[:3]]})
    for p in store.exported_playlists():
        out.append({"name": p.name, "count": len(p.tracks), "origin": p.ids.get("source"), "covers": [], "top": []})
    return out


def _dist(tracks: list[Track]) -> list[dict]:
    c = Counter((t.genre, t.subgenre) for t in tracks)
    return [{"label": sub or g or "Unsortiert", "genre": g, "subgenre": sub, "count": n} for (g, sub), n in c.most_common()]


@app.get("/api/search")
def search(q: str = ""):
    """Globale Suche (Seitenleiste): Songs in eigenen Playlists und Erkennungsverlauf. Playlists/Einstellungen sucht die App selbst."""
    q = q.strip()[:100]
    if len(q) < 2:
        return {"songs": [], "history": []}
    return {"songs": store.search_songs(q), "history": store.search_history(q)}


@app.get("/api/playlists/{name:path}")
def playlist_detail(name: str):
    entries = store.playlist_entries(name)
    return {"name": name, "entries": entries, "dist": _dist([Track(**e["track"]) for e in entries])}


class KeyReq(BaseModel):
    key: str


@app.post("/api/track")
def track_detail(req: KeyReq):
    t = store.find_track(req.key)
    if not t:
        raise HTTPException(404, "Song nicht gefunden")
    return {"id": None, "extra": {}, **_track_payload(t)}


class AssignReq(BaseModel):
    id: int | None = None
    key: str | None = None
    playlist: str


def _resolve(req: AssignReq) -> Track:
    if req.id is not None and (got := store.get_recognition(req.id)):
        t, extra = got
        t.cover = t.cover or extra.get("cover")
        t.preview_url = t.preview_url or extra.get("preview_url")
        return t
    if req.key and (t := store.find_track(req.key)):
        return t
    raise HTTPException(404, "Song nicht gefunden")


@app.post("/api/assign")
def assign(req: AssignReq):
    if not req.playlist.strip():
        raise HTTPException(400, "Playlist-Name fehlt")
    t = _resolve(req)
    added = store.add_to_playlist(req.playlist.strip(), t)
    return {"added": added, **(_payload(req.id) if req.id is not None else _track_payload(t))}


# ------------------------------------------------------------------ Automatischer Abgleich
@app.get("/api/autosync")
def autosync_get():
    from .. import autosync
    return {**autosync.status(), "items": autosync.inbox()}


@app.get("/api/autosync/status")
def autosync_status():
    from .. import autosync
    return autosync.status()


@app.post("/api/autosync")
def autosync_set(data: dict):
    from .. import autosync
    autosync.save(data)
    return autosync.status()


@app.post("/api/autosync/run")
def autosync_run():
    from .. import autosync
    return {"started": autosync.run_async()}


@app.post("/api/autosync/reset")
def autosync_reset():
    from .. import autosync
    try:
        autosync.reset()
    except RuntimeError as e:
        raise HTTPException(409, str(e))
    return autosync.status()


class InboxAddReq(BaseModel):
    playlist: str


@app.post("/api/autosync/inbox/{iid}/add")
def autosync_add(iid: str, req: InboxAddReq):
    from .. import autosync
    name = req.playlist.strip()
    if not name:
        raise HTTPException(400, "Playlist-Name fehlt")
    item = next((x for x in autosync.inbox() if x["id"] == iid), None)
    if not item:
        raise HTTPException(404, "Eintrag nicht mehr da")
    added = store.add_to_playlist(name, autosync.inbox_track(item))
    autosync.take(iid)
    return {"added": added, "playlist": name}


@app.post("/api/autosync/inbox/{iid}/undo")
def autosync_undo(iid: str):
    from .. import autosync
    undone = autosync.undo_auto(iid)
    if not undone:
        raise HTTPException(404, "Nichts zum Zurücknehmen")
    return undone


@app.post("/api/autosync/inbox/{iid}/done")
def autosync_done(iid: str):
    from .. import autosync
    autosync.take(iid)
    return {"ok": True}


@app.post("/api/autosync/inbox/clear")
def autosync_clear():
    from .. import autosync
    autosync.clear_inbox()
    return {"ok": True}


@app.post("/api/unassign")
def unassign(req: AssignReq):
    t = _resolve(req)
    store.remove_from_playlist(req.playlist, store.track_key(t))
    return _payload(req.id) if req.id is not None else _track_payload(t)


class RenameReq(BaseModel):
    new: str


@app.post("/api/playlists/{name:path}/rename")
def rename(name: str, req: RenameReq):
    if not req.new.strip():
        raise HTTPException(400)
    store.rename_playlist(name, req.new.strip())
    return {"ok": True}


class MergeReq(BaseModel):
    src: str = "local"          # "local" oder eine Dienst-ID (auch friend-…)
    src_id: str


MERGE_MAX = 5000


@app.post("/api/playlists/{name:path}/merge")
def merge_playlist(name: str, req: MergeReq):
    """Songs einer anderen Playlist (lokal, Export oder Dienst) in eine bestehende oder neue lokale Playlist übernehmen.
    Doppelte Songs werden übersprungen, die Reihenfolge der Quelle bleibt erhalten."""
    target = name.strip()[:200]
    if not target:
        raise HTTPException(400, "Name der Ziel-Playlist fehlt")
    if req.src == "local":
        if req.src_id == target:
            raise HTTPException(400, "Quelle und Ziel sind dieselbe Playlist")
        src = next((p for p in [*store.local_playlists(), *store.exported_playlists()] if p.name == req.src_id), None)
        if src is None:
            raise HTTPException(404, "Playlist nicht gefunden")
        tracks = src.tracks
    else:
        from .. import services
        _, tracks = _svc_call(services.load, req.src, req.src_id)
    tracks = tracks[:MERGE_MAX]
    added = sum(bool(store.add_to_playlist(target, t)) for t in tracks)
    return {"name": target, "added": added, "dupes": len(tracks) - added, "total": len(tracks)}


@app.delete("/api/playlists/{name:path}")
def delete_playlist(name: str):
    store.delete_playlist(name)
    return {"ok": True}


# ------------------------------------------------------------------ Aufteilen
class SplitReq(BaseModel):
    playlist: str
    detail: str = "sub"
    prefix: str = ""


@app.post("/api/split/preview")
def split_preview(req: SplitReq):
    pl = next((p for p in _all_playlists() if p.name == req.playlist), None)
    if not pl:
        raise HTTPException(404)
    parts = split_by_genre(pl.tracks, req.detail, req.prefix)
    return [{"name": p.name, "count": len(p.tracks),
             "genre": p.tracks[0].genre, "subgenre": p.tracks[0].subgenre if req.detail == "sub" else None,
             "tracks": [{"title": t.title, "artists": t.artists, "cover": t.cover} for t in p.tracks[:6]]}
            for p in parts]


@app.post("/api/split/apply")
def split_apply(req: SplitReq):
    pl = next((p for p in _all_playlists() if p.name == req.playlist), None)
    if not pl:
        raise HTTPException(404)
    n = 0
    for part in split_by_genre(pl.tracks, req.detail, req.prefix):
        for t in part.tracks:
            n += store.add_to_playlist(part.name, t)
    return {"added": n}


# ------------------------------------------------------------------ Entdecken
def _lastfm():
    if not config.opt("LASTFM_API_KEY"):
        raise HTTPException(400, "Für diese Funktion wird ein Last.fm-Key benötigt (Einstellungen).")
    from ..genres.sources.lastfm import LastFM
    return LastFM()


def _similar(track: Track, limit: int):
    from concurrent.futures import ThreadPoolExecutor

    from .. import ratelimit, similar
    lf = _lastfm() if config.opt("LASTFM_API_KEY") else None   # Genres der Treffer nur mit Last.fm-Key
    try:
        cands = similar.find(track, limit=limit)                 # Last.fm, sonst/zusätzlich Deezer
    except ratelimit.LimitReached as e:
        raise HTTPException(429, f"{e} – bitte gleich nochmal versuchen")

    def row(cm):
        cand, m = cm
        try:
            c = classify(lf.tags(cand) if lf else {})
        except Exception:
            c = classify({})
        a = cand.artists[0] if cand.artists else ""
        return {"title": cand.title, "artists": cand.artists, "match": round(m, 2),
                "genre": c.genre, "subgenre": c.subgenre,
                # Hörprobe erst beim Abspielen über Deezer suchen (kostet vorher nichts)
                "preview_url": f"lookup:{a}|{cand.title}",
                "links": platform_links(cand, lookup=False)}

    with ThreadPoolExecutor(6) as ex:
        out = list(ex.map(row, cands))
    (dbg.event if out else dbg.problem)("ähnlich", f"{len(out)} ähnliche Songs", song=f"{track.artist} – {track.title}",
                                        ohne_genre=sum(1 for r in out if not r["genre"]))
    return out


class CoversReq(BaseModel):
    items: list[dict]       # [{a: Künstler, t: Titel, isrc?}]


def _cover_one(it: dict) -> dict:
    """Cover-*Adresse* + Deezer-ID für einen Song (nur Adresse – das Bild lädt der Player/Browser direkt beim
    Anbieter, gespeichert wird kein Bild). 30 Tage im Zwischenspeicher, damit Listen sofort Bilder haben."""
    from ..enrich import deezer
    from ..recognize.engines import Recognition
    a, t = str(it.get("a") or "")[:200], str(it.get("t") or "")[:200]
    if not a or not t:
        return {}
    key = f"{a.lower()}|{t.lower()}"
    if (hit := store.cache_get("cover_lookup", key, max_age=30 * 86400)) is not None:
        return hit
    d = deezer(Recognition("cover", t, [a], isrc=it.get("isrc") or None)) or {}
    out = {"cover": (d.get("album") or {}).get("cover_medium") or (d.get("album") or {}).get("cover_big"),
           "dz": str(d["id"]) if d.get("id") else None} if d.get("id") else {}
    store.cache_set("cover_lookup", key, out)
    return out


@app.post("/api/covers")
async def covers(req: CoversReq):
    from concurrent.futures import ThreadPoolExecutor

    def run():
        with ThreadPoolExecutor(4) as ex:
            return list(ex.map(_cover_one, req.items[:60]))
    return await asyncio.to_thread(run)


@app.get("/api/similar")
def similar_by_key(key: str, limit: int = 15):
    t = store.find_track(key)
    if not t:
        raise HTTPException(404, "Song nicht gefunden")
    return _similar(t, limit)


@app.get("/api/similar/{rid}")
def similar(rid: int, limit: int = 15):
    got = store.get_recognition(rid)
    if not got:
        raise HTTPException(404)
    return _similar(got[0], limit)


@app.get("/api/audiofeat")
def audiofeat_get(id: int | None = None, key: str | None = None, artist: str = "", title: str = "", isrc: str = "", dz: str = ""):
    """Tempo / Tonart / Energie eines Songs (Speicher oder 30-s-Hörprobe von Deezer). {} = keine Hörprobe."""
    from .. import audiofeat
    extra = {}
    if id is not None and (got := store.get_recognition(id)):
        t, extra = got
    elif key and (t := store.find_track(key)):
        pass
    elif artist.strip() and title.strip():
        t = Track(title=title.strip()[:300], artists=[artist.strip()[:200]], isrc=isrc.strip().upper()[:12] or None,
                  ids={"deezer": dz} if dz.isdigit() else {})
    else:
        raise HTTPException(400, "Song fehlt")
    f = audiofeat.features(t, deezer_bpm=(extra or {}).get("bpm")) or {}
    return {k: f.get(k) for k in ("bpm", "camelot", "key", "energy")} if f else {}


@app.get("/api/mixmatch")
def mixmatch(id: int | None = None, key: str | None = None):
    """„Passt dazu“: mixbare Songs (Tempo + Tonart) aus den eigenen Playlists."""
    from .. import mixmatch as mm
    extra = {}
    if id is not None and (got := store.get_recognition(id)):
        t, extra = got
    elif key and (t := store.find_track(key)):
        pass
    else:
        raise HTTPException(404, "Song nicht gefunden")
    return mm.find(t, deezer_bpm=(extra or {}).get("bpm"))


class DiscoverReq(BaseModel):
    artist: str
    title: str
    limit: int = 20


@app.post("/api/discover")
def discover(req: DiscoverReq):
    base = Track(title=req.title.strip(), artists=[req.artist.strip()])
    c = classify(_lastfm().tags(base) if config.opt("LASTFM_API_KEY") else {})   # ähnliche Songs gehen auch ohne Key
    return {"genre": c.genre, "subgenre": c.subgenre, "confidence": c.confidence,
            "similar": _similar(base, req.limit)}


# ------------------------------------------------------------------ Plattformen
_conn_cache: dict[str, tuple[float, bool, str | None]] = {}
_conn_err: dict[str, str | None] = {}          # warum ein angemeldeter Dienst gerade nicht antwortet (für die Karte)


def _platform_state(pid: str, fresh: bool = False) -> tuple[bool, str | None]:
    """Verbunden? – höchstens alle 5 min beim Dienst nachfragen."""
    from ..providers import get_provider
    c = _conn_cache.get(pid)
    if c and not fresh and time.time() - c[0] < 300:
        return c[1], c[2]
    prov = get_provider(pid)
    ok = prov.connected()
    acc = prov.account() if ok else None
    _conn_cache[pid] = (time.time(), ok, acc)
    _conn_err[pid] = None if ok else getattr(prov, "last_error", None)
    return ok, acc


@app.get("/api/platforms")
async def platforms():
    out = []
    for pid, (name, info, avail) in PROVIDERS.items():
        ok, acc = (await asyncio.to_thread(_platform_state, pid)) if avail else (False, None)
        out.append({"id": pid, "name": name, "info": info, "available": avail, "connected": ok, "account": acc, "error": _conn_err.get(pid)})
    return out


def _prov(pid: str):
    from ..providers import get_provider
    try:
        return get_provider(pid)
    except NotImplementedError as e:
        raise HTTPException(400, str(e))


@app.post("/api/platforms/{pid}/login")
def platform_login(pid: str):
    import webbrowser
    try:
        st = _prov(pid).login()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, str(e))
    threading.Thread(target=webbrowser.open, args=(st["url"],), daemon=True).start()
    return st


@app.get("/api/platforms/{pid}/login")
def platform_login_state(pid: str):
    st = _prov(pid).login_state()
    if st.get("state") == "connected":
        _conn_cache.pop(pid, None)
    return st


@app.post("/api/platforms/{pid}/logout")
def platform_logout(pid: str):
    _prov(pid).logout()
    _conn_cache.pop(pid, None)
    _SVC_RAM.clear()
    return {"ok": True}


@app.get("/api/platforms/{pid}/playlists")
async def platform_playlists(pid: str):
    prov = _prov(pid)
    try:
        lists = await asyncio.to_thread(prov.playlist_list)
        liked = await asyncio.to_thread(prov.liked_count)
    except Exception as e:
        raise HTTPException(502, f"{PROVIDERS[pid][0]}: {e}")
    return [{"id": "__liked__", "name": "Lieblingssongs", "count": liked, "own": True}] + lists


class TransferReq(BaseModel):
    src: str
    src_id: str
    dst: str
    name: str = ""
    like: bool = False


@app.post("/api/transfer")
def transfer_start(req: TransferReq):
    from .. import transfer
    if req.src == req.dst and req.src != "local":
        raise HTTPException(400, "Quelle und Ziel sind gleich")
    if req.dst in ("youtube", "soundcloud"):
        raise HTTPException(400, f"{PROVIDERS[req.dst][0]} ist nur lesend angebunden – als Ziel nicht möglich")
    if not req.like and not req.name.strip():
        raise HTTPException(400, "Name fehlt")
    return {"job": transfer.start(req.src, req.src_id, req.dst, req.name.strip(), req.like)}


@app.get("/api/transfer/{jid}")
def transfer_job(jid: str):
    from .. import transfer
    j = transfer.job(jid)
    if not j:
        raise HTTPException(404)
    return j


@app.post("/api/transfer/{jid}/cancel")
def transfer_cancel(jid: str):
    from .. import transfer
    transfer.cancel(jid)
    return {"ok": True}


# ------------------------------------------------------------------ Einstellungen
SETTINGS = {
    "LASTFM_API_KEY": "Last.fm API-Key",
    "AUDD_API_TOKEN": "AudD API-Token",
    "ACRCLOUD_HOST": "ACRCloud Host",
    "ACRCLOUD_ACCESS_KEY": "ACRCloud Access Key",
    "ACRCLOUD_ACCESS_SECRET": "ACRCloud Access Secret",
    "SPOTIFY_CLIENT_ID": "Spotify – Client-ID deiner App",
    "YOUTUBE_API_KEY": "YouTube Data API-Key (für Playlist-Links)",
    "YOUTUBE_OAUTH_CLIENT_ID": "YouTube-Login – Client-ID (Google-OAuth, Desktop-App)",
    "YOUTUBE_OAUTH_CLIENT_SECRET": "YouTube-Login – Client-Secret",
    "SOUNDCLOUD_CLIENT_ID": "SoundCloud-Login – Client-ID deiner App",
    "SOUNDCLOUD_CLIENT_SECRET": "SoundCloud-Login – Client-Secret",
    "LASTFM_SHARED_SECRET": "Last.fm-Login – Shared secret deines API-Kontos",
}
_SECRET = {"LASTFM_API_KEY", "AUDD_API_TOKEN", "ACRCLOUD_ACCESS_KEY", "ACRCLOUD_ACCESS_SECRET", "YOUTUBE_API_KEY",
           "YOUTUBE_OAUTH_CLIENT_SECRET", "SOUNDCLOUD_CLIENT_SECRET",
           "LASTFM_SHARED_SECRET"}


def _mask(k: str, v: str | None) -> str:
    if not v:
        return ""
    return v if k not in _SECRET else (v[:4] + "•" * 8 + v[-2:] if len(v) > 8 else "•" * 8)


@app.get("/api/settings")
def get_settings():
    return [{"key": k, "label": lbl, "value": _mask(k, config.opt(k)), "set": bool(config.opt(k)),
             "secret": k in _SECRET} for k, lbl in SETTINGS.items()]


class SettingReq(BaseModel):
    key: str
    value: str


@app.post("/api/settings")
def set_setting(req: SettingReq):
    if req.key not in SETTINGS:
        raise HTTPException(400)
    config.set_value(req.key, req.value.strip())
    return get_settings()


# ------------------------------------------------------------------ Sicherung
def _backup_path(name: str):
    p = backup.backup_dir() / name
    if p.parent != backup.backup_dir() or not p.name.endswith(backup.SUFFIX) or not p.exists():
        raise HTTPException(404, "Sicherung nicht gefunden")
    return p


@app.get("/api/backups")
def backups():
    last = store.meta_get("last_auto_backup")
    return {"dir": str(backup.backup_dir()), "items": backup.list_backups(),
            "last_auto": float(last) if last else None, "auto": backup.auto_settings(), "next_auto": backup.next_auto(),
            "custom_dir": bool(config.opt("TUNEBRIDGE_BACKUP_DIR"))}


class BackupAutoReq(BaseModel):
    interval: str | None = None
    keep: int | None = None
    folder: str | None = None


@app.post("/api/backups/auto")
def backup_auto_set(req: BackupAutoReq):
    try:
        s = backup.save_auto_settings(req.interval, req.keep, req.folder)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {**s, "dir": str(backup.backup_dir()), "next_auto": backup.next_auto()}


class BackupReq(BaseModel):
    include_keys: bool = False


@app.post("/api/backups")
def create_backup(req: BackupReq):
    f = backup.create(include_keys=req.include_keys)
    return {"name": f.name, **backup.inspect(f)}


class RestoreReq(BaseModel):
    name: str
    mode: str = "replace"
    restore_keys: bool = False


@app.post("/api/backups/restore")
def restore_backup(req: RestoreReq):
    try:
        return backup.restore(_backup_path(req.name), req.mode, req.restore_keys)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/api/backups/upload")
async def upload_backup(request: Request):
    """Backup-Datei (z.B. vom alten Rechner) in den Backup-Ordner übernehmen."""
    name = Path(request.headers.get("x-filename", "import.tbbackup")).name
    if not name.endswith(backup.SUFFIX):
        name += backup.SUFFIX
    target = backup.backup_dir() / name
    if target.exists():
        target = target.with_name(target.stem + "-import" + backup.SUFFIX)
    data = await request.body()
    target.write_bytes(data)
    target.chmod(0o600)
    try:
        m = backup.inspect(target)
    except ValueError as e:
        target.unlink(missing_ok=True)
        raise HTTPException(400, str(e))
    return {"name": target.name, **m}


@app.get("/api/backups/download/{name}")
def download_backup(name: str):
    p = _backup_path(name)
    return FileResponse(p, filename=p.name, media_type="application/zip")


@app.delete("/api/backups/{name}")
def delete_backup(name: str):
    _backup_path(name).unlink()
    return {"ok": True}


@app.post("/api/backups/open-folder")
def open_backup_folder():
    from .. import osutil
    try:
        osutil.open_path(backup.backup_dir())
    except osutil.OpenError as e:
        raise HTTPException(400, str(e)) from e
    return {"ok": True}


# ------------------------------------------------------------------ Hörproben
@app.get("/api/preview")
async def preview(u: str | None = None, isrc: str | None = None, dz: str | None = None, a: str = "", t: str = "",
                  aac: bool = False):
    """Adresse einer offiziellen Hörprobe -> {url, source}. Der Player streamt direkt vom Anbieter;
    SH-Tunebridge lädt nichts herunter und speichert nichts (Bedingungen von Apple/Deezer)."""
    from .. import preview as pv
    try:
        return await asyncio.to_thread(pv.resolve, u, isrc, dz, a, t, aac)
    except FileNotFoundError as e:
        dbg.problem("hörprobe", "Keine Hörprobe gefunden", song=f"{a} – {t}", isrc=isrc, url=u)
        raise HTTPException(404, str(e))


# ------------------------------------------------------------------ Geräte-Auswahl (pro Rechner)
_PREFS_KEY = f"prefs:{store.HOST}"
_PREF_DEFAULTS = {"mode": "desktop", "device_desktop": "desktop", "device_mic": "mic", "seconds": 10,
                  # Datenschutz: None = noch nicht gefragt -> wie „nein“ behandeln (privacy by default)
                  "send_audio_desktop": None, "send_audio_mic": None, "mic_ack": False}


def _prefs() -> dict:
    import json
    raw = store.meta_get(_PREFS_KEY)
    return {**_PREF_DEFAULTS, **(json.loads(raw) if raw else {})}


@app.get("/api/prefs")
def get_prefs():
    prefs = _prefs()
    names = {s.name for s in capture.sources()}
    # Gerät gespeichert, aber gerade nicht angeschlossen?
    prefs["missing"] = [k for k in ("device_desktop", "device_mic")
                        if prefs[k] not in ("desktop", "mic") and prefs[k] not in names]
    return prefs


@app.post("/api/prefs")
def set_prefs(prefs: dict):
    import json
    raw = store.meta_get(_PREFS_KEY)
    cur = {**_PREF_DEFAULTS, **(json.loads(raw) if raw else {})}
    cur.update({k: v for k, v in prefs.items() if k in _PREF_DEFAULTS})
    store.meta_set(_PREFS_KEY, json.dumps(cur))
    return cur


# ------------------------------------------------------------------ Konten verbinden
@app.get("/api/connect")
def connect_overview():
    from .. import connect, keys
    return [{**s, "session": connect.session(s["id"])} for s in keys.status()]


def _svc(svc: str) -> str:
    from .. import keys
    if svc not in keys.SERVICES:
        raise HTTPException(404, "Unbekannter Dienst")
    return svc


@app.post("/api/connect/{svc}")
def connect_start(svc: str):
    from .. import connect
    return {"mode": connect.start(_svc(svc))}


@app.get("/api/connect/{svc}")
def connect_status(svc: str):
    from .. import connect
    return connect.session(_svc(svc))


@app.post("/api/connect/{svc}/clipboard")
def connect_clipboard(svc: str):
    from .. import connect
    return {"found": connect.clipboard(_svc(svc))}


@app.post("/api/connect/{svc}/accept")
def connect_accept(svc: str):
    from .. import connect
    ok, msg = connect.accept_clipboard(_svc(svc))
    if ok is False:
        raise HTTPException(400, msg)
    return {"ok": ok, "message": msg}


@app.post("/api/connect/{svc}/test")
def connect_test(svc: str):
    from .. import config as cfg, keys
    s = keys.SERVICES[_svc(svc)]
    ok, msg = keys.validate(svc, {f.key: cfg.opt(f.key) or "" for f in s.fields})
    return {"ok": ok, "message": msg}


# ------------------------------------------------------------------ Updates
@app.get("/api/update")
async def update_check(force: bool = False):
    from .. import update
    return await asyncio.to_thread(update.check, force)


class TagReq(BaseModel):
    tag: str


@app.post("/api/update/prepare")
async def update_prepare(req: TagReq):
    from .. import update
    try:
        return await asyncio.to_thread(update.prepare, req.tag)
    except Exception as e:
        raise HTTPException(400, str(e))


@app.post("/api/update/install")
async def update_install():
    from .. import update
    try:
        return await asyncio.to_thread(update.install)
    except Exception as e:
        raise HTTPException(400, str(e))


@app.post("/api/update/restart")
def update_restart():
    from .. import update
    try:
        import webview
        mode = "app" if webview.windows else "ui"
    except ImportError:
        mode = "ui"
    update.restart(mode)
    return {"ok": True}


# ------------------------------------------------------------------ Lokales LLM
@app.get("/api/llm")
async def llm_overview():
    from .. import llm
    return await asyncio.to_thread(llm.overview)


@app.post("/api/llm/settings")
def llm_settings(patch: dict):
    from .. import llm
    if "model" in patch and patch["model"] not in llm.MODELS:
        raise HTTPException(400, "Unbekanntes Modell")
    if "device" in patch and patch["device"] not in llm.RUNTIMES:
        raise HTTPException(400, "Unbekanntes Gerät")
    return llm.save_settings(patch)


@app.post("/api/llm/models/{mid}/download")
def llm_download(mid: str):
    from .. import llm
    if mid not in llm.MODELS:
        raise HTTPException(404)
    try:
        llm.download_model(mid)
    except PermissionError as e:
        raise HTTPException(403, str(e))
    return {"ok": True}


@app.post("/api/llm/models/{mid}/cancel")
def llm_cancel(mid: str):
    from .. import llm
    llm.cancel(f"model:{mid}")
    return {"ok": True}


@app.delete("/api/llm/models/{mid}")
def llm_delete(mid: str):
    from .. import llm
    if mid not in llm.MODELS:
        raise HTTPException(404)
    llm.delete_model(mid)
    return {"ok": True}


@app.post("/api/llm/runtime/{variant}")
def llm_runtime(variant: str):
    from .. import llm
    if variant not in llm.RUNTIMES:
        raise HTTPException(404)
    llm.download_runtime(variant)
    return {"ok": True}


@app.post("/api/llm/warm")
def llm_warm():
    from .. import llm
    llm.warm()
    return {"ok": True}


@app.post("/api/llm/stop")
def llm_stop():
    from .. import llm
    llm.stop()
    return {"ok": True}


@app.post("/api/llm/test")
async def llm_test():
    """Startet bei Bedarf und stellt eine Testfrage – misst die Antwortzeit."""
    import time
    from .. import llm
    from ..enrich import llm_subgenre
    if not llm.settings()["enabled"]:
        raise HTTPException(400, "Lokales LLM ist nicht aktiviert")
    t0 = time.time()
    url = await asyncio.to_thread(llm.ensure_running, 240)
    if not url:
        raise HTTPException(500, llm.status().get("error") or "Server startet nicht")
    t1 = time.time()
    tr = Track(title="Afterglow", artists=["Wilkinson"], tags={"drum and bass": 100})
    sub = await asyncio.to_thread(llm_subgenre, tr, "Drum & Bass", "lokal")
    return {"ok": bool(sub), "answer": sub, "start_s": round(t1 - t0, 1), "answer_s": round(time.time() - t1, 1),
            "question": "Wilkinson – Afterglow (Drum & Bass) → Subgenre?"}


# ------------------------------------------------------------------ Auf Plattformen öffnen
@app.get("/api/links")
async def track_links(id: int | None = None, key: str | None = None):
    from .. import links
    known = {}
    if id is not None:
        got = store.get_recognition(id)
        if not got:
            raise HTTPException(404)
        track, extra = got
        known = extra.get("links") or {}
    elif key:
        track = store.find_track(key)
        if not track:
            raise HTTPException(404)
    else:
        raise HTTPException(400)
    return await asyncio.to_thread(links.links, track, known)


# ------------------------------------------------------------------ Datenschutz
@app.get("/api/privacy")
def privacy():
    from .. import llm, preview
    files = list(preview.CACHE.glob("*.*")) if preview.CACHE.exists() else []
    return {"prefs": {k: _prefs()[k] for k in ("send_audio_desktop", "send_audio_mic", "mic_ack")},
            "engines": available(), "history": store.stats().get("recognitions", 0),
            "preview_cache": {"files": len(files), "bytes": sum(f.stat().st_size for f in files)},
            "llm_terms": llm.settings().get("terms_accepted", False)}


# ------------------------------------------------------------------ Genres (Katalog + Dazulernen)
def _families() -> dict[str, list[str]]:
    from ..genres.classify import CATALOG_STATS  # noqa: F401  (lädt Katalog)
    fams = {g: [x for x in subs if x != "_"] for g, subs in TAXONOMY.items()}
    for extra in ("Electronic", "Blues", "Folk / Country / World", "Religious", "Kinder & Sonstiges"):
        fams.setdefault(extra, [])
    return fams


@app.get("/api/genres")
def genres_overview():
    from ..genres import learn
    from ..genres.classify import CATALOG_STATS
    curated = sum(len(a) for subs in TAXONOMY.values() for a in subs.values())
    return {"catalog": CATALOG_STATS, "curated": {"families": len(TAXONOMY), "aliases": curated},
            "families": _families(), **learn.overview()}


class TermReq(BaseModel):
    tag: str
    action: str            # accept | reject | reset
    main: str | None = None
    sub: str | None = None


@app.post("/api/genres/term")
def genres_term(req: TermReq):
    from ..genres import learn
    if req.action == "accept" and req.main not in _families():
        raise HTTPException(400, "Unbekanntes Hauptgenre")
    try:
        learn.set_term(req.tag, req.action, req.main, req.sub)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return genres_overview()


@app.post("/api/genres/reclassify")
def genres_reclassify():
    from ..genres import learn
    return learn.reclassify()


@app.get("/api/ratelimit")
def ratelimits():
    """Stand aller Dienst-Limits – für die Anzeige „Limit erreicht, noch X s“."""
    from .. import ratelimit
    return ratelimit.state()


@app.get("/api/debug")
def debug_status():
    return dbg.status()


class DebugReq(BaseModel):
    enabled: bool


@app.post("/api/debug")
def debug_set(req: DebugReq):
    return dbg.set_enabled(req.enabled)


@app.post("/api/debug/clear")
def debug_clear():
    dbg.clear()
    return dbg.status()


@app.get("/api/debug/report")
def debug_report():
    """Vorschau: genau das, was in der Datei landet."""
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(dbg.report())


@app.post("/api/debug/export")
def debug_export():
    path = dbg.export()
    dbg.event("debug", "Bericht gespeichert", datei=path.name)
    return {"path": str(path), "name": path.name, "folder": str(path.parent)}


@app.post("/api/debug/open-folder")
def debug_open_folder(req: dict):
    folder = Path(req.get("folder") or dbg.downloads_dir())
    if folder.is_dir():
        from .. import osutil
        try:
            osutil.open_path(folder)
        except osutil.OpenError as e:
            raise HTTPException(400, str(e)) from e
    return {"ok": True}


class ClientErr(BaseModel):
    message: str
    where: str = ""
    stack: str = ""


@app.post("/api/debug/client")
def debug_client(err: ClientErr):
    dbg.error("oberfläche", err.message[:500], ort=err.where[:200], stack=err.stack[:2000])
    return {"ok": True}


# ------------------------------------------------------------------ Speicher & Cache
def _dir_size(p: Path, pattern: str = "*") -> tuple[int, int]:
    fs = [f for f in p.glob(pattern) if f.is_file()] if p.exists() else []
    return len(fs), sum(f.stat().st_size for f in fs)


@app.get("/api/storage")
def storage():
    st = store.storage()
    lg = _dir_size(dbg.LOG_DIR, "debug.log*")
    bk = _dir_size(backup.backup_dir(), "*" + backup.SUFFIX)
    c = st["cache"]
    g = lambda k: c.get(k, {"count": 0, "bytes": 0})  # noqa: E731
    rows = [
        {"id": "songs", "label": "Song-Speicher", "hint": "Bekannte Songs mit Genre, Links und Cover-/Hörproben-Adressen (keine Bilder, kein Ton) – spart Online-Abfragen",
         **st["songs"]},
        {"id": "fingerprints", "label": "Lokale Fingerabdrücke",
         "hint": f"Wiedererkennung ohne Shazam · {st['fingerprints']['songs']} Songs (kein Ton, nicht rückrechenbar)",
         "count": st["fingerprints"]["count"], "bytes": st["fingerprints"]["bytes"]},
        {"id": "tags", "label": "Genre-Tags (Last.fm)", "hint": "30 Tage gültig", **g("tags")},
        {"id": "similar", "label": "Ähnliche Songs", "hint": "7 Tage gültig", **g("similar")},
        {"id": "links", "label": "Plattform-Links", "hint": "Apple Music, TIDAL-Treffer", **g("links")},
        {"id": "other", "label": "Sonstiges", "hint": "Update-Prüfung u. a.", **g("other")},
        {"id": "misses", "label": "Nicht erkannt / Genre unbekannt", "hint": "deine Sammlung zum Auswerten", **st["misses"]},
        {"id": "logs", "label": "Debug-Protokoll", "hint": "nur wenn eingeschaltet", "count": lg[0], "bytes": lg[1]},
    ]
    return {"rows": rows, "db_bytes": st["db_bytes"], "data_dir": dbg._redact(str(config.DATA)),
            "recognitions": st["recognitions"], "genre_terms": st["genre_terms"], "backups": {"count": bk[0], "bytes": bk[1]},
            "saved": store.saved_calls(), "ram": {"count": len(store._RAM), "max": store._RAM_MAX}}


class ClearReq(BaseModel):
    what: list[str]


@app.post("/api/storage/clear")
def storage_clear(req: ClearReq):
    from .. import preview
    out = {}
    for w in req.what:
        if w in ("songs", "fingerprints", "misses"):
            out[w] = store.clear_table(w)
        elif w in ("tags", "similar", "links", "other"):
            out[w] = store.clear_cache_group(w)
        elif w == "previews" and preview.CACHE.exists():
            out[w] = sum(1 for f in preview.CACHE.glob("*.*") if not f.unlink(missing_ok=True))
        elif w == "logs":
            dbg.clear()
            out[w] = 1
    store.vacuum()
    dbg.event("speicher", "Geleert", **out)
    return {"cleared": out, **storage()}


# ------------------------------------------------------------------ Nicht erkannt
@app.get("/api/misses")
def misses_list():
    from .. import upload
    return {"items": store.misses(), "server": {"url": upload.URL, "identity": upload.identity()}}


class MissNote(BaseModel):
    note: str


@app.post("/api/misses/{mid}/note")
def misses_note(mid: int, req: MissNote):
    store.miss_update(mid, note=req.note)
    return {"ok": True}


class MissIds(BaseModel):
    ids: list[int] | None = None


@app.post("/api/misses/delete")
def misses_delete(req: MissIds):
    return {"deleted": store.miss_delete(req.ids)}


def _miss_export(ids: list[int] | None) -> dict:
    """Genau das, was weitergegeben würde – ohne Rechnername, Pfade oder Gerätenamen."""
    from .. import __version__
    items = [m for m in store.misses(1000) if ids is None or m["id"] in ids]
    out = []
    for m in items:
        src = m["source"] or ""
        out.append({"uid": m["uid"], "zeit": time.strftime("%Y-%m-%d", time.localtime(m["ts"])),
                    "art": m["kind"], "quelle": "anwendung" if src.startswith(capture.APP_PREFIX) else
                    ("standard" if src in ("desktop", "mic") else "gerät"),
                    "pegel_db": m["level_db"], "player": players.minimal(m["player"]), "song": m["song"],
                    "details": m["details"], "notiz": m["note"]})
    return {"app": "SH-Tunebridge", "version": __version__, "format": 1, "eintraege": out}


@app.post("/api/misses/preview")
def misses_preview(req: MissIds):
    return _miss_export(req.ids)


@app.post("/api/misses/export")
def misses_export(req: MissIds):
    import json as _json
    import os
    data = _miss_export(req.ids)
    path = dbg.downloads_dir() / f"SH-Tunebridge-Nicht-erkannt-{time.strftime('%Y%m%d-%H%M%S')}.json"
    path.write_text(_json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    os.chmod(path, 0o600)
    return {"path": str(path), "name": path.name, "folder": str(path.parent), "count": len(data["eintraege"])}


@app.post("/api/misses/send")
def misses_send(req: MissIds):
    """Nur auf ausdrücklichen Klick (nach Vorschau) – sendet genau _miss_export(ids)."""
    from .. import consent, upload
    c = consent.get()
    if not (c["privacy_at"] and c["server"]["domain"]):
        raise HTTPException(403, f"Senden ist nicht erlaubt – bitte in den Einstellungen unter „Datenschutz & "
                                 f"Einwilligungen“ die Datenschutzerklärung und die Domain {consent.DOMAIN} bestätigen")
    data = _miss_export(req.ids)
    if not data["eintraege"]:
        raise HTTPException(400, "Nichts zu senden")
    try:
        res = upload.send(data)
    except upload.UploadError as e:
        raise HTTPException(502, str(e))
    now = time.time()
    uids = {e["uid"] for e in data["eintraege"]}
    for m in store.misses(1000):
        if m["uid"] in uids:
            store.miss_update(m["id"], sent=now)
    return {**res, "count": len(uids)}


# ------------------------------------------------------------------ Darstellung (Farben, Hintergrund)
_LOOK_KEYS = {"mode": ("dunkel", "hell", "system"), "accent": str, "palette": str, "font": (90, 95, 100, 105, 110, 115),
              "radius": ("eckig", "normal", "rund"), "density": ("kompakt", "normal", "luftig"), "motion": bool,
              "bg_dim": int, "bg_blur": int, "panel": int, "side_min": bool, "bg_v": int}


def _bg_file(orig: bool = False) -> Path:
    """Anzeige-Bild (Weichzeichner schon eingerechnet) bzw. das unbearbeitete, verkleinerte Original."""
    return config.DATA / "appearance" / ("original.webp" if orig else "hintergrund.webp")


@app.get("/api/appearance")
def look_get():
    import json
    raw = store.meta_get("appearance")
    d = json.loads(raw) if raw else {}
    return {**d, "bg": _bg_file().exists()}


@app.post("/api/appearance")
def look_set(patch: dict):
    import json
    raw = store.meta_get("appearance")
    d = json.loads(raw) if raw else {}
    for k, v in patch.items():
        rule = _LOOK_KEYS.get(k)
        if rule is None:
            continue
        if k == "bg_v":
            d[k] = int(v) % 10**9
            continue
        if isinstance(rule, tuple):
            if v not in rule:
                raise HTTPException(400, f"Ungültiger Wert für {k}")
        elif rule is str:
            v = str(v)[:40]
            if k == "accent" and not re.fullmatch(r"#[0-9a-fA-F]{6}", v):
                raise HTTPException(400, "Farbe bitte als #rrggbb")
        elif rule is int:
            v = max(0, min(100, int(v)))
        else:
            v = bool(v)
        d[k] = v
    store.meta_set("appearance", json.dumps(d))
    return {**d, "bg": _bg_file().exists()}


class BgReq(BaseModel):
    data: str        # base64 – im Browser bereits auf Bildschirmgröße verkleinert und als WebP kodiert
    original: bool = False


@app.post("/api/appearance/bg")
def look_bg_set(req: BgReq):
    import base64
    try:
        raw = base64.b64decode(req.data.split(",", 1)[-1], validate=True)
    except ValueError:
        raise HTTPException(400, "Bild nicht lesbar")
    if len(raw) > 6_000_000:
        raise HTTPException(400, "Bild zu groß")
    if not (raw[:4] == b"RIFF" and raw[8:12] == b"WEBP") and raw[:3] != b"\xff\xd8\xff":
        raise HTTPException(400, "Nur WebP/JPEG")
    f = _bg_file(req.original)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_bytes(raw)
    if req.original:
        return look_get()
    return look_set({"bg_v": int(time.time() * 1000) % 10**9})   # neue Adresse -> kein altes Bild aus dem Cache


@app.delete("/api/appearance/bg")
def look_bg_del():
    _bg_file().unlink(missing_ok=True)
    _bg_file(True).unlink(missing_ok=True)
    return look_get()


@app.get("/api/appearance/bg")
def look_bg_get(orig: bool = False):
    f = _bg_file(orig) if orig and _bg_file(True).exists() else _bg_file()
    if not f.exists():
        raise HTTPException(404, "Kein Hintergrund")
    return FileResponse(f, media_type="image/webp" if f.read_bytes()[:4] == b"RIFF" else "image/jpeg",
                        headers={"Cache-Control": "max-age=31536000, immutable"})


# ------------------------------------------------------------------ Begleiter: Tray + Schwebe-Icon
_companion: dict = {"proc": None}
_companion_lock = threading.Lock()
# Vom Desktop-Fenster gesetzt (desktop.py): Fenster zeigen bzw. App beenden
WINDOW_HOOKS: dict = {}
WINDOW_STATE: dict = {"shown": False, "error": None}   # App-Fenster wirklich offen? (Rauchtest, Diagnose)


@app.get("/api/window")
def window_state():
    return WINDOW_STATE


def _comp_cfg() -> dict:
    import json
    raw = store.meta_get("companion")
    return {"tray": False, "bubble": False, "pos": None, "viz": "bars", **(json.loads(raw) if raw else {})}


def companion_available() -> tuple[bool, str]:
    try:
        import PySide6.QtWidgets  # noqa: F401
    except ImportError:
        return False, "Auf diesem System noch nicht verfügbar (Qt fehlt) – kommt mit einem späteren Update."
    return True, ""


def companion_ensure(port: int | None = None) -> None:
    """Begleit-Prozess starten, wenn Tray oder Schwebe-Icon an ist und er noch nicht läuft.
    (Ausschalten erledigt er selbst: er fragt alle 2,5 s die Einstellungen ab und beendet sich.)"""
    cfg = _comp_cfg()
    if not (cfg["tray"] or cfg["bubble"]) or not companion_available()[0]:
        return
    with _companion_lock:
        _companion_start(cfg, port)


def _companion_start(cfg: dict, port: int | None) -> None:
    import json
    import os
    import subprocess
    import sys
    p = _companion["proc"]
    if p is not None and p.poll() is None:
        return
    port = port or int(os.environ.get("TUNEBRIDGE_PORT", "8765"))
    env = {k: v for k, v in os.environ.items() if not k.startswith("QTWEBENGINE")}
    env["TUNEBRIDGE_COMPANION_CFG"] = json.dumps(cfg)   # sofort anzeigen, nicht erst nach der ersten Abfrage
    if sys.platform.startswith("linux") and env.get("WAYLAND_DISPLAY") and env.get("DISPLAY"):
        env["QT_QPA_PLATFORM"] = "xcb"     # XWayland: „immer im Vordergrund“ + freie Position sind erlaubt
    cmd = [sys.executable, "companion", "--port", str(port)] if getattr(sys, "frozen", False) else \
        [sys.executable, "-c", f"from tunebridge.companion import main; main({port})"]
    from .. import osutil
    if osutil.WINDOWS and not getattr(sys, "frozen", False):   # Entwickler-Start: pythonw statt python (kein Konsolenfenster)
        pw = Path(sys.executable).with_name("pythonw.exe")
        if pw.exists():
            cmd[0] = str(pw)
    _companion["proc"] = subprocess.Popen(cmd, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, **osutil.NO_WINDOW,
                                          stderr=subprocess.DEVNULL, start_new_session=True)
    dbg.event("begleiter", "Gestartet", tray=cfg["tray"], schwebe_icon=cfg["bubble"])


def companion_stop(wait: float = 3) -> None:
    """Begleit-Prozess sofort beenden (vor einem Update – unter Windows sperrt er sonst den Programmordner)."""
    p = _companion["proc"]
    if p is None or p.poll() is not None:
        return
    p.terminate()
    try:
        p.wait(wait)
    except Exception:  # noqa: BLE001
        p.kill()


@app.get("/api/companion")
def companion_get():
    import json
    raw = store.meta_get("appearance")
    look = json.loads(raw) if raw else {}
    ok, why = companion_available()
    p = _companion["proc"]
    return {**_comp_cfg(), "accent": look.get("accent", "#6cc8a8"), "available": ok, "why": why,
            "running": bool(p is not None and p.poll() is None),
            "desktop": bool(WINDOW_HOOKS), "source": _prefs().get("device_desktop") or "desktop"}


VIZ_STYLES = ("bars", "wave", "rgb")   # Anzeige beim Zuhören: Spektrum · 3-Band-Welle · RGB-Welle


@app.post("/api/companion")
def companion_set(patch: dict, request: Request):
    import json
    cfg = _comp_cfg()
    for k in ("tray", "bubble"):
        if k in patch:
            cfg[k] = bool(patch[k])
    if patch.get("viz") in VIZ_STYLES:
        cfg["viz"] = patch["viz"]
    if isinstance(patch.get("pos"), list) and len(patch["pos"]) == 2:
        cfg["pos"] = [int(patch["pos"][0]), int(patch["pos"][1])]
    store.meta_set("companion", json.dumps(cfg))
    companion_ensure(request.url.port)
    return companion_get()


@app.post("/api/companion/scan")
async def companion_scan():
    """Ein Klick aufs Schwebe-Icon: Musik am Rechner erkennen (Quelle aus den Erkennen-Einstellungen)."""
    prefs = _prefs()
    try:
        r = await listen(ListenReq(mode="desktop", source=prefs.get("device_desktop") or "desktop", seconds=10))
    except HTTPException as e:
        return {"found": False, "error": str(e.detail)}
    if r.get("found") and not r.get("same"):
        t = r.get("track") or r
        return {"found": True, "artist": t.get("artist") or ", ".join(t.get("artists") or []), "title": t.get("title"),
                "cover": t.get("cover") or (r.get("extra") or {}).get("cover"),
                "genre": " · ".join(x for x in (t.get("genre"), t.get("subgenre")) if x)}
    return {"found": False, "silent": r.get("silent"), "hint": (r.get("errors") or {}).get("shazam") or r.get("notice")}


@app.post("/api/window/show")
def window_show(request: Request):
    if WINDOW_HOOKS.get("show"):
        WINDOW_HOOKS["show"]()
    else:
        import webbrowser
        webbrowser.open(f"http://127.0.0.1:{request.url.port}")
    return {"ok": True}


@app.post("/api/app/quit")
def app_quit():
    if WINDOW_HOOKS.get("quit"):
        threading.Timer(0.2, WINDOW_HOOKS["quit"]).start()
    return {"ok": True}


# ------------------------------------------------------------------ KI-Anbieter
@app.get("/api/ai")
def ai_get():
    from .. import ai
    return {**ai.public(), "ready": ai.ready()}


@app.post("/api/ai/settings")
def ai_set(patch: dict):
    from .. import ai
    try:
        out = ai.save_settings(patch)
    except ai.AIError as e:
        raise HTTPException(400, str(e))
    dbg.event("ki", "Einstellungen", anbieter="+".join(out["use"]) or "aus", modus=out["combine"], automatisch=out["auto_genre"])
    return {**out, "ready": ai.ready()}


@app.get("/api/ai/detect")
async def ai_detect():
    from .. import ai
    return await asyncio.to_thread(ai.detect)


@app.get("/api/ai/models/{provider}")
async def ai_models(provider: str, refresh: bool = False):
    from .. import ai
    if provider not in ai.PROVIDERS:
        raise HTTPException(404, "Unbekannter Anbieter")
    try:
        return {"models": await asyncio.to_thread(ai.refresh_models, provider, refresh)}
    except Exception as e:
        raise HTTPException(502, f"Modelle nicht abrufbar: {_friendly_net_error(e)}")


def _friendly_net_error(e: Exception) -> str:
    """Netzwerkfehler verständlich machen (statt „[WinError 10061] …“ / „Errno 111 Connection refused“)."""
    txt = str(e)
    if isinstance(e, ConnectionRefusedError) or "10061" in txt or "Connection refused" in txt or "Errno 111" in txt:
        return "keine Verbindung – das Programm läuft gerade nicht oder die Adresse stimmt nicht"
    if isinstance(e, TimeoutError) or "timed out" in txt.lower() or "10060" in txt:
        return "keine Antwort (Zeitüberschreitung) – Adresse und Netzwerk prüfen"
    return txt


@app.post("/api/ai/test")
async def ai_test():
    from .. import ai
    t0 = time.time()
    try:
        d = await asyncio.to_thread(ai.analyze_track, {"artist": "Wilkinson", "title": "Afterglow",
                                                       "tags": ["drum and bass", "liquid funk"]})
    except Exception as e:
        raise HTTPException(502, str(e))
    return {"ok": True, "antwort": d, "dauer_s": round(time.time() - t0, 1)}


class AnalyzeReq(BaseModel):
    id: int | None = None          # Erkennung aus dem Verlauf
    track: dict | None = None      # oder direkt {artist, title, ...}


@app.post("/api/ai/analyze/track")
async def ai_analyze_track(req: AnalyzeReq):
    from .. import ai
    if req.id is not None:
        got = store.get_recognition(req.id)
        if not got:
            raise HTTPException(404)
        tr, extra = got
        t = {"artist": tr.artist, "title": tr.title, "album": tr.album, "tags": list(tr.tags or {}),
             "genre": tr.genre, "subgenre": tr.subgenre, "bpm": extra.get("bpm"), "year": extra.get("year")}
    elif req.track and req.track.get("title"):
        t = {k: req.track.get(k) for k in ("artist", "title", "album", "tags", "genre", "subgenre", "bpm", "year")}
    else:
        raise HTTPException(400, "Song fehlt")
    try:
        return await asyncio.to_thread(ai.analyze_track, t)
    except Exception as e:
        raise HTTPException(502, str(e))


@app.post("/api/ai/analyze/link/{jid}")
async def ai_analyze_link(jid: str):
    from .. import ai, linkimport
    j = linkimport.job(jid)
    if not j or j["state"] != "done":
        raise HTTPException(400, "Analyse noch nicht fertig")
    try:
        return await asyncio.to_thread(ai.analyze_playlist, j.get("name", ""), j["items"])
    except Exception as e:
        raise HTTPException(502, str(e))


class AiMarkReq(BaseModel):
    id: int | None = None
    track: dict | None = None
    mark: str | None = None        # "ki" | "mensch" | None


@app.post("/api/ai-mark")
def ai_mark(req: AiMarkReq):
    """Eigene Einschätzung „KI-generiert“ / „nicht KI“ – hat Vorrang vor allen Hinweisen."""
    from .. import aidetect
    if req.mark not in ("ki", "mensch", None):
        raise HTTPException(400)
    if req.id is not None:
        got = store.get_recognition(req.id)
        if not got:
            raise HTTPException(404)
        track, extra = got
    elif req.track and req.track.get("title"):
        track = Track(title=req.track["title"], artists=req.track.get("artists") or [req.track.get("artist", "")])
        extra = {}
    else:
        raise HTTPException(400, "Song fehlt")
    aidetect.mark(track, req.mark)
    return aidetect.check(track, extra)


@app.get("/api/buy")
def buy(id: int | None = None, artist: str = "", title: str = ""):
    """Kauf-Links (ohne Affiliate) – Künstler direkt unterstützen."""
    from .. import links
    if id is not None:
        got = store.get_recognition(id)
        if not got:
            raise HTTPException(404)
        track = got[0]
    elif title:
        track = Track(title=title, artists=[artist] if artist else [])
    else:
        raise HTTPException(400)
    return links.buy_links(track)


# ------------------------------------------------------------------ Links einfügen
class LinkReq(BaseModel):
    url: str


@app.post("/api/import-link")
def import_link(req: LinkReq):
    from .. import linkimport
    try:
        return {"job": linkimport.start(req.url)}
    except linkimport.LinkError as e:
        raise HTTPException(400, str(e))


class FileImportReq(BaseModel):
    name: str
    data: str   # Base64 – Dateien gehen nur an die App auf deinem Rechner, nirgendwohin sonst


@app.post("/api/import-file")
def import_file(req: FileImportReq):
    """Playlist-Datei (Export von Apple Music, Google Takeout, Exportify, .m3u …) -> Analyse-Auftrag."""
    import base64
    import binascii

    from .. import linkimport, playlistfile
    try:
        raw = base64.b64decode(req.data, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(400, "Datei konnte nicht gelesen werden")
    try:
        name, tracks = playlistfile.parse(req.name, raw)
    except playlistfile.FileError as e:
        raise HTTPException(400, str(e))
    return {"job": linkimport.start(preset={"service": "datei", "kind": "playlist", "name": name, "tracks": tracks}),
            "count": len(tracks)}


# ------------------------------------------------------------------ Dienste: Playlists ansehen & sortieren
def _svc_call(fn, *a, **kw):
    from .. import services
    from ..dataexport import ExportError
    from ..linkimport import LinkError
    from ..share import ShareError
    try:
        return fn(*a, **kw)
    except (services.ServiceError, LinkError, NotImplementedError, ExportError, ShareError) as e:
        raise HTTPException(400, str(e))
    except Exception as e:  # noqa: BLE001 – Dienst nicht erreichbar o. ä.
        dbg.error("dienste", "Dienst-Abfrage fehlgeschlagen", e)
        raise HTTPException(502, f"Dienst nicht erreichbar: {e}")


@app.get("/api/services")
async def services_overview():
    from .. import services
    states = {}
    for pid in ("spotify", "tidal", "youtube", "soundcloud"):
        try:
            states[pid] = await asyncio.to_thread(_platform_state, pid)
        except Exception:  # noqa: BLE001
            states[pid] = (False, None)
    out = services.overview(lambda pid: states.get(pid, (False, None)))
    for row in out:
        if isinstance(row, dict) and _conn_err.get(row.get("id")):
            row["error"] = _conn_err[row["id"]]
    return out


class ProfileReq(BaseModel):
    value: str = ""


@app.post("/api/services/{sid}/profile")
def services_profile(sid: str, req: ProfileReq):
    from .. import services
    return _svc_call(services.set_profile, sid, req.value)


_SVC_RAM: dict[tuple, tuple[float, object]] = {}   # nur Arbeitsspeicher: Playlist-Listen/Songs der Dienste
_SVC_TTL = 600


def _svc_ram(key: tuple, fn, fresh: bool = False):
    hit = _SVC_RAM.get(key)
    if hit and not fresh and time.time() - hit[0] < _SVC_TTL:
        return hit[1]
    val = fn()
    if len(_SVC_RAM) > 200:
        _SVC_RAM.pop(next(iter(_SVC_RAM)))
    _SVC_RAM[key] = (time.time(), val)
    return val


@app.get("/api/services/{sid}/playlists")
async def services_playlists(sid: str, refresh: bool = False):
    from .. import services
    return await asyncio.to_thread(_svc_ram, ("pl", sid), lambda: _svc_call(services.playlists, sid), refresh)


@app.get("/api/services/{sid}/playlists/{pid}/tracks")
async def services_playlist_tracks(sid: str, pid: str, refresh: bool = False):
    """Songs einer Dienst-Playlist zum Ansehen/Vorhören – nur im Arbeitsspeicher, Cover nur als Link."""
    from .. import services

    def load():
        name, tracks = _svc_call(services.load, sid, pid)
        return {"name": name, "tracks": [{"title": t.title, "artists": t.artists, "album": t.album, "isrc": t.isrc,
                                          "cover": t.cover, "preview_url": t.preview_url, "ids": t.ids,
                                          "duration_ms": t.duration_ms} for t in tracks[:1000]]}
    return await asyncio.to_thread(_svc_ram, ("tr", sid, pid), load, refresh)


# ------------------------------------------------------------------ Datenexporte der Dienste (ohne Entwickler-App)
def _svc_ram_drop(sid: str) -> None:
    for k in [k for k in _SVC_RAM if len(k) > 1 and k[1] == sid]:
        _SVC_RAM.pop(k, None)


@app.post("/api/services/{sid}/import")
async def services_import(sid: str, request: Request, name: str = ""):
    """Rohe Datei im Body (kein Base64, kein Formular) – Spotify-Kontodaten, Google Takeout, Apple-Mediathek."""
    from .. import dataexport
    if sid not in dataexport.IMPORT_SERVICES:
        raise HTTPException(400, "Für diesen Dienst gibt es keinen Datei-Import")
    data = bytearray()
    async for chunk in request.stream():
        data += chunk
        if len(data) > dataexport.MAX_UPLOAD:
            raise HTTPException(413, "Datei ist zu groß (max. 300 MB) – bitte beim Export nur Playlists auswählen")
    if not data:
        raise HTTPException(400, "Leere Datei")
    _svc_ram_drop(sid)
    return {"job": dataexport.start(sid, name, bytes(data))}


# ------------------------------------------------------------------ Playlists teilen (privater/öffentlicher Schlüssel)
class ShareReq(BaseModel):
    name: str = ""
    key: str = ""
    nick: str = ""
    names: list[str] = []
    public: bool = False


def _share(fn, *a):
    from ..share import ShareError
    try:
        return fn(*a)
    except ShareError as e:
        raise HTTPException(400, str(e))


@app.get("/api/share")
def share_status():
    from .. import share
    return share.status()


@app.post("/api/share/create")
def share_create(req: ShareReq):
    from .. import share
    return _share(share.create, req.name)


@app.post("/api/share/join")
def share_join(req: ShareReq):
    from .. import share
    return _share(share.join, req.key)


@app.post("/api/share/leave")
def share_leave():
    from .. import share
    return share.leave()


@app.post("/api/share/delete")
def share_delete():
    from .. import share
    return _share(share.delete_space)


@app.post("/api/share/rename")
def share_rename(req: ShareReq):
    from .. import share
    return _share(share.rename, req.name)


@app.post("/api/share/playlists")
def share_add(req: ShareReq):
    from .. import share
    return _share(share.add_local, req.names, req.public)


@app.post("/api/share/sync")
def share_sync():
    from .. import share
    return _share(share.update_local)


@app.post("/api/share/playlists/{pid}/public")
def share_public(pid: str, req: ShareReq):
    from .. import share
    return _share(share.set_public, pid, req.public)


@app.delete("/api/share/playlists/{pid}")
def share_remove(pid: str):
    from .. import share
    return _share(share.remove, pid)


@app.post("/api/share/friends")
def share_friend_add(req: ShareReq):
    from .. import share
    _SVC_RAM.clear()
    return _share(share.add_friend, req.key, req.nick)


@app.delete("/api/share/friends/{fid}")
def share_friend_remove(fid: str):
    from .. import share
    _svc_ram_drop(f"friend-{fid}")
    return share.remove_friend(fid)


@app.post("/api/share/friends/{fid}/copy/{pid}")
def share_friend_copy(fid: str, pid: str, req: ShareReq):
    from .. import share
    name, tracks = _share(share.friend_playlist, fid, pid)
    target = (req.name or name).strip()[:200] or name
    return {"name": target, "added": share.copy_to_local(target, tracks)}


@app.get("/api/services/import/{jid}")
def services_import_job(jid: str):
    from .. import dataexport
    j = dataexport.job(jid)
    if not j:
        raise HTTPException(404, "Import nicht gefunden")
    if j["state"] == "done":
        _svc_ram_drop(j["service"])
    return j


@app.post("/api/services/import/{jid}/cancel")
def services_import_cancel(jid: str):
    from .. import dataexport
    dataexport.cancel(jid)
    return {"ok": True}


@app.delete("/api/services/{sid}/import")
def services_import_delete(sid: str):
    from .. import dataexport
    dataexport.remove(sid)
    _svc_ram_drop(sid)
    return {"ok": True}


# ------------------------------------------------------------------ Genre-Datenbank (eigene Einordnungen + Gemeinschaft)
class GdbAnalyzeReq(BaseModel):
    sid: str
    pid: str
    ai: bool = False


class GdbAcceptReq(BaseModel):
    rows: list[dict]


class GdbVoteReq(BaseModel):
    id: int | None = None          # Erkennung im Verlauf
    key: str | None = None         # Song aus einer lokalen Playlist
    genre: str
    subgenre: str | None = None


class GdbDeleteReq(BaseModel):
    keys: list[str] | None = None
    all: bool = False


@app.get("/api/genredb")
def genredb_overview():
    from .. import ai, consent, genredb
    return {"counts": genredb.counts(), "community": genredb.community_info(),
            "consent": {"genres": consent.server("genres"), "genredb": consent.server("genredb")},
            "ai_ready": ai.ready()[0], "votes": genredb.votes(300),
            "taxonomy": {g: [x for x in subs if x != "_"] for g, subs in TAXONOMY.items()},
            "checked": float(store.meta_get("genredb:checked") or 0) or None}


@app.post("/api/genredb/analyze")
def genredb_analyze(req: GdbAnalyzeReq):
    from .. import ai, genredb
    if req.ai and not ai.ready()[0]:
        raise HTTPException(400, f"KI nicht bereit: {ai.ready()[1]}")
    return {"job": genredb.start(req.sid, req.pid, req.ai)}


@app.get("/api/genredb/job/{jid}")
def genredb_job(jid: str):
    from .. import genredb
    j = genredb.job(jid)
    if not j:
        raise HTTPException(404, "Auftrag nicht gefunden")
    return j


@app.post("/api/genredb/job/{jid}/cancel")
def genredb_cancel(jid: str):
    from .. import genredb
    genredb.cancel(jid)
    return {"ok": True}


@app.post("/api/genredb/job/{jid}/accept")
def genredb_accept(jid: str, req: GdbAcceptReq):
    from .. import genredb
    try:
        return genredb.accept(jid, req.rows)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/api/genredb/vote")
def genredb_vote(req: GdbVoteReq):
    """Genre eines Songs von Hand festlegen (Korrektur). Gilt sofort; im Verlauf wird der Eintrag angepasst."""
    from .. import genredb
    if req.id is not None and (got := store.get_recognition(req.id)):
        t, extra = got
    elif req.key and (t := store.find_track(req.key)):
        extra = None
    else:
        raise HTTPException(404, "Song nicht gefunden")
    try:
        v = genredb.vote(t.artists, t.title, t.isrc, req.genre, req.subgenre, "korrektur")
    except ValueError as e:
        raise HTTPException(400, str(e))
    if req.id is not None and extra is not None:
        from dataclasses import asdict
        before = [t.genre, t.subgenre]
        t.genre, t.subgenre = v["genre"], v["subgenre"]
        if before[0] != t.genre:
            t.niche = None
        extra.update(genre_source="eigene Einordnung", genre_before=before, confidence=0.95)
        store.update_recognition(req.id, asdict(t), extra)
    dbg.event("genredb", "Genre von Hand festgelegt", song=f"{t.artist} – {t.title}", genre=f"{v['genre']}/{v['subgenre']}")
    return v


@app.post("/api/genredb/votes/delete")
def genredb_delete(req: GdbDeleteReq):
    from .. import genredb
    return {"deleted": genredb.delete(None if req.all else (req.keys or []))}


@app.post("/api/genredb/update")
def genredb_update():
    from .. import genredb
    r = genredb.update(force=True)
    if not r.get("ok"):
        raise HTTPException(400, r.get("why") or "Nicht geladen")
    return r


# ------------------------------------------------------------------ Gemeinschaft (Einstellungen › Gemeinschaft)
@app.get("/api/community")
def community_status():
    from .. import community
    return community.status()


class ModeReq(BaseModel):
    mode: str


@app.post("/api/community/mode")
def community_mode(req: ModeReq):
    from .. import community
    try:
        return {"mode": community.set_mode(req.mode)}
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/api/community/sync")
def community_sync():
    from .. import community, upload
    try:
        return {"done": community.sync(), **community.status()}
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except upload.UploadError as e:
        raise HTTPException(502, str(e))


# ------------------------------------------------------------------ Öffentliches Playlist-Verzeichnis
def _pub(fn, *a, **kw):
    from .. import pubdir
    try:
        return fn(*a, **kw)
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except pubdir.PubError as e:
        raise HTTPException(400, str(e))


@app.get("/api/pubdir")
def pubdir_list(q: str = "", genre: str = "", page: int = 0):
    from .. import consent, pubdir
    if not consent.server("verzeichnis"):
        return {"allowed": False, "reasons": pubdir.REASONS}
    r = _pub(pubdir.browse, q, genre, page)
    g = _pub(pubdir.genres)
    return {"allowed": True, **r, "genres": g, "reasons": pubdir.REASONS}


@app.get("/api/pubdir/item/{pid}")
def pubdir_item(pid: str):
    from .. import pubdir
    return _pub(pubdir.get, pid)


@app.get("/api/pubdir/mine")
def pubdir_mine():
    from .. import pubdir
    return _pub(pubdir.mine)


class PubReq(BaseModel):
    name: str = ""
    alias: str = ""
    genre: str = ""
    info: str = ""
    confirm: bool = False
    id: str = ""
    grund: str = ""
    text: str = ""
    alle: bool = False


@app.post("/api/pubdir/publish")
def pubdir_publish(req: PubReq):
    from .. import pubdir
    return _pub(pubdir.publish, req.name, req.alias, req.genre, req.info, req.confirm)


@app.post("/api/pubdir/delete")
def pubdir_delete(req: PubReq):
    from .. import pubdir
    return _pub(pubdir.unpublish, req.id or None, req.alle)


@app.post("/api/pubdir/report")
def pubdir_report(req: PubReq):
    from .. import pubdir
    return _pub(pubdir.report, req.id, req.grund, req.text)


@app.post("/api/pubdir/copy")
def pubdir_copy(req: PubReq):
    from .. import pubdir
    return _pub(pubdir.copy, req.id, req.name)


class SortStartReq(BaseModel):
    service: str
    playlist: str = ""
    name: str = ""
    ai_check: bool = False
    file_name: str = ""
    file_data: str = ""      # Base64 (Apple-Music-Export u. ä.) – bleibt auf diesem Rechner


@app.post("/api/sort/start")
def sort_start(req: SortStartReq):
    from .. import ai, services
    if req.ai_check:
        ok, why = ai.ready()
        if not ok:
            raise HTTPException(400, f"KI-Prüfung nicht möglich: {why}")
    preset = None
    if req.file_data:
        import base64
        import binascii

        from .. import playlistfile
        try:
            name, tracks = playlistfile.parse(req.file_name, base64.b64decode(req.file_data, validate=True))
        except (binascii.Error, ValueError, playlistfile.FileError) as e:
            raise HTTPException(400, str(e) or "Datei konnte nicht gelesen werden")
        preset = (name, tracks)
    elif not req.playlist:
        raise HTTPException(400, "Keine Playlist gewählt")
    return {"job": services.start(req.service, req.playlist, req.name, req.ai_check, preset)}


@app.get("/api/sort/{jid}")
def sort_job(jid: str):
    from .. import services
    j = services.job(jid)
    if not j:
        raise HTTPException(404, "Auftrag nicht gefunden")
    return j


@app.post("/api/sort/{jid}/cancel")
def sort_cancel(jid: str):
    from .. import services
    services.cancel(jid)
    return {"ok": True}


class SortGenreReq(BaseModel):
    i: int
    genre: str
    subgenre: str | None = None
    learn: bool = True


@app.post("/api/sort/{jid}/genre")
def sort_genre(jid: str, req: SortGenreReq):
    from .. import services
    return _svc_call(services.set_genre, jid, req.i, req.genre, req.subgenre, req.learn)


@app.post("/api/sort/{jid}/ai-unsorted")
def sort_ai_unsorted(jid: str):
    from .. import services
    return {"songs": _svc_call(services.ai_unsorted, jid)}


class SortGroupsReq(BaseModel):
    level: int = 6
    min_size: int = 3


@app.post("/api/sort/{jid}/groups")
def sort_groups(jid: str, req: SortGroupsReq):
    from .. import services
    return _svc_call(services.groups, jid, req.level, max(1, min(50, req.min_size)))


class SortApplyReq(BaseModel):
    plan: list[dict]
    target: str = "local"
    prefix: str = ""


@app.post("/api/sort/{jid}/apply")
def sort_apply(jid: str, req: SortApplyReq):
    from .. import services
    if req.target not in ("local", "spotify", "tidal"):
        raise HTTPException(400, "Ziel nicht möglich")
    res = _svc_call(services.apply, jid, req.plan, req.target, req.prefix)
    return res


@app.get("/api/import-link/{jid}")
def import_link_job(jid: str):
    from .. import linkimport
    j = linkimport.job(jid)
    if not j:
        raise HTTPException(404)
    return j


@app.post("/api/import-link/{jid}/cancel")
def import_link_cancel(jid: str):
    from .. import linkimport
    linkimport.cancel(jid)
    return {"ok": True}


@app.get("/api/platforms/{pid}/playlists/{plid}/tracks")
async def platform_playlist_tracks(pid: str, plid: str):
    """Playlist eines Dienstes anzeigen (zum Durchsehen/Vorhören)."""
    from .. import transfer
    _prov(pid)
    try:
        tracks = await asyncio.to_thread(transfer.load, pid, plid)
    except Exception as e:
        raise HTTPException(502, f"{PROVIDERS[pid][0]}: {e}")
    return [{"title": t.title, "artist": t.artist, "album": t.album, "isrc": t.isrc, "cover": t.cover,
             "preview_url": t.preview_url, "ids": t.ids} for t in tracks]


@app.get("/api/spotify/callback")
def spotify_callback(code: str = "", state: str = "", error: str = ""):
    return _oauth_done("spotify", code, state, error)


# ------------------------------------------------------------------ Last.fm-Login (offizielle Web-Anmeldung)
@app.post("/api/lastfm/login")
def lastfm_login():
    import webbrowser
    from ..lastfm_auth import LOGIN, LastfmError
    try:
        st = LOGIN.login()
    except LastfmError as e:
        raise HTTPException(400, str(e))
    threading.Thread(target=webbrowser.open, args=(st["url"],), daemon=True).start()
    return st


@app.get("/api/lastfm/login")
def lastfm_login_state():
    from ..lastfm_auth import LOGIN
    return LOGIN.login_state()


@app.get("/api/lastfm/callback/{state}")
def lastfm_callback(state: str, token: str = ""):
    from .. import services
    from ..lastfm_auth import LOGIN
    from fastapi.responses import HTMLResponse as _H
    import html as _html
    try:
        name = LOGIN.finish_login(token, state)
        services.set_profile_direct("lastfm", name, name)
        _SVC_RAM.clear()
        msg = f"Last.fm ist verbunden ({name}). Du kannst dieses Fenster schließen."
    except Exception as e:  # noqa: BLE001
        msg = f"Fehler: {e}"
    return _H(f"<!doctype html><meta charset=utf-8><title>SH-Tunebridge</title>"
              f"<body style='font-family:sans-serif;background:#111;color:#eee;padding:40px'>"
              f"<h2>SH-Tunebridge</h2><p>{_html.escape(msg)}</p></body>")


@app.post("/api/lastfm/logout")
def lastfm_logout():
    from .. import services
    from ..lastfm_auth import LOGIN
    LOGIN.logout()
    services.set_profile("lastfm", "")
    _SVC_RAM.clear()
    return {"ok": True}


@app.get("/api/oauth/{pid}/callback")
def oauth_callback(pid: str, code: str = "", state: str = "", error: str = "", error_description: str = ""):
    if pid not in ("youtube", "soundcloud"):
        raise HTTPException(404)
    return _oauth_done(pid, code, state, error_description or error)


def _oauth_done(pid: str, code: str, state: str, error: str):
    from ..providers import get_provider
    from fastapi.responses import HTMLResponse as _H
    name = PROVIDERS[pid][0]
    prov = get_provider(pid)
    if error:
        msg = f"{name}-Anmeldung abgebrochen: {error}"
        if hasattr(prov, "fail_login"):
            prov.fail_login(msg)
    else:
        try:
            prov.finish_login(code, state)
            _conn_cache.pop(pid, None)
            _SVC_RAM.clear()
            msg = f"{name} ist verbunden. Du kannst dieses Fenster schließen."
        except Exception as e:
            msg = f"Fehler: {e}"
    import html as _html
    return _H(f"<!doctype html><meta charset=utf-8><title>SH-Tunebridge</title>"
              f"<body style='font-family:sans-serif;background:#111;color:#eee;padding:40px'>"
              f"<h2>SH-Tunebridge</h2><p>{_html.escape(msg)}</p></body>")


# ------------------------------------------------------------------ Einwilligungen
@app.get("/api/consent")
def consent_get():
    from .. import consent, outbox
    return {**consent.get(), "pending_errors": len(outbox.pending_errors()),
            "pending_songs": len(outbox.song_entries()) if consent.server("songs") else 0}


@app.post("/api/consent")
def consent_set(data: dict):
    from .. import consent, outbox
    try:
        out = consent.save(data)
    except ValueError as e:
        raise HTTPException(400, str(e))
    if not consent.server("fehler"):
        outbox.clear_errors()          # ohne Erlaubnis keine gesammelten Fehlerberichte aufheben
    from .. import genredb
    if consent.server("genredb"):
        threading.Thread(target=genredb.update, kwargs={"force": True}, daemon=True).start()
    else:
        genredb.remove_community()     # Erlaubnis zurückgenommen -> geladene Datenbank nicht weiter nutzen
    dbg.event("datenschutz", "Einwilligungen gespeichert", lokal=out["local"], server=out["server"])
    return out


@app.post("/api/consent/send-now")
def consent_send_now():
    from .. import consent, outbox, upload
    if not consent.server_any():
        raise HTTPException(403, "Keine Sende-Erlaubnis erteilt")
    try:
        return {"gesendet": outbox.flush()}
    except upload.UploadError as e:
        raise HTTPException(502, str(e))


@app.on_event("startup")
async def _outbox_loop():
    from .. import outbox, preview
    try:
        preview._prune()             # Hörproben-Zwischenspeicher: höchstens 24 h
    except Exception:
        pass
    asyncio.get_running_loop().create_task(outbox.loop())


@app.get("/api/misses/server")
def misses_server_status():
    from .. import upload
    try:
        return {**upload.status(), "identity": upload.identity()}
    except upload.UploadError as e:
        raise HTTPException(502, str(e))


@app.post("/api/misses/server-delete")
def misses_server_delete():
    from .. import upload
    try:
        return upload.delete_all()
    except upload.UploadError as e:
        raise HTTPException(502, str(e))


@app.post("/api/privacy/clear")
def privacy_clear(what: dict):
    from .. import preview
    out = {}
    if what.get("history"):
        out["history"] = store.clear_history()
    if what.get("previews") and preview.CACHE.exists():
        n = 0
        for f in preview.CACHE.glob("*.*"):
            f.unlink(missing_ok=True)
            n += 1
        out["previews"] = n
    if what.get("cache"):
        out["cache"] = store.clear_cache()
    return out


# ------------------------------------------------------------------ Datenverbrauch
@app.get("/api/traffic/live")
def traffic_live():
    from .. import traffic
    return traffic.live()


@app.get("/api/traffic")
def traffic_summary():
    from .. import traffic
    return traffic.summary()


class TrafficClientReq(BaseModel):
    items: list[dict] = []


@app.post("/api/traffic/client")
def traffic_client(req: TrafficClientReq):
    """Was das Fenster selbst lädt (Cover, Hörproben) – von der Oberfläche gemeldet, teils geschätzt."""
    from .. import traffic
    for it in req.items[:500]:
        try:
            n = max(0, min(int(it.get("bytes") or 0), 200_000_000))
        except (TypeError, ValueError):
            continue
        if n:
            traffic.add(str(it.get("host") or "")[:200], n, 0, bool(it.get("est")))
    return {"ok": True}


@app.post("/api/traffic/reset")
def traffic_reset():
    from .. import traffic
    traffic.reset()
    return {"ok": True}


# ------------------------------------------------------------------ Discord
@app.get("/api/discord")
def discord_get():
    from .. import discord_rpc
    return discord_rpc.status()


@app.post("/api/discord")
def discord_set(patch: dict):
    from .. import discord_rpc
    try:
        return discord_rpc.save(patch)
    except (TypeError, ValueError) as e:
        raise HTTPException(400, str(e))


class DiscordEventReq(BaseModel):
    view: str | None = None
    preview: dict | None = None
    kind: str = "view"


@app.post("/api/discord/event")
def discord_event(req: DiscordEventReq):
    from .. import discord_rpc
    if not discord_rpc.settings()["enabled"]:
        return {"ok": False}
    if req.kind == "preview":
        p = req.preview
        discord_rpc.RPC.on_preview({"title": str(p.get("title") or "")[:200], "artists": [str(a)[:100] for a in (p.get("artists") or [])][:5],
                                    "cover": p.get("cover"), "genre": p.get("genre"), "subgenre": p.get("subgenre"),
                                    "url": p.get("url")} if p else None)
    else:
        discord_rpc.RPC.on_view((req.view or "")[:40] or None)
    return {"ok": True}


@app.post("/api/discord/test")
def discord_test():
    """Verbindung prüfen und eine Beispielanzeige setzen (verschwindet nach der Anzeigezeit)."""
    from .. import discord_rpc
    cfg = discord_rpc.settings()
    if not cfg["client_id"]:
        raise HTTPException(400, "Bitte zuerst die Application ID eintragen")
    try:
        c = discord_rpc._Conn(cfg["client_id"])
        c.close()
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, str(e))
    discord_rpc.RPC.wake()
    return {"ok": True, "user": c.user}


# ------------------------------------------------------------------ Zwischenablage (nur auf Klick, für „Einfügen“)
class ClipReq(BaseModel):
    text: str = ""


@app.post("/api/clipboard/read")
def clipboard_read():
    """Nur auf ausdrücklichen Klick („Einfügen“) – das App-Fenster hat kein eigenes Rechtsklick-Menü."""
    text = None
    if (fn := WINDOW_HOOKS.get("clipboard_get")):
        try:
            text = fn()
        except Exception:  # noqa: BLE001
            text = None
    if not text:
        from .. import keys
        text = keys.read_clipboard()
    return {"text": (text or "")[:20000]}


@app.get("/api/artists")
def artists_of(dz: str):
    """Künstler eines geprüften Deezer-Songs (für „Mehr vom Künstler“)."""
    from .. import artists
    if not dz.isdigit():
        raise HTTPException(400, "Deezer-ID fehlt")
    try:
        return artists.contributors(dz)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"Deezer nicht erreichbar: {e}")


@app.get("/api/artist/{aid}")
def artist_tracks(aid: int):
    from .. import artists
    try:
        return artists.tracks(aid)
    except LookupError as e:
        raise HTTPException(404, str(e))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"Deezer nicht erreichbar: {e}")


class OpenReq(BaseModel):
    url: str


def open_external(url: str) -> None:
    """Link im Standard-Browser des Systems öffnen (xdg-open/KDE, Windows, macOS)."""
    import subprocess
    import sys as _sys
    if _sys.platform == "win32":
        os.startfile(url)  # noqa: S606
        return
    cmd = ["open", url] if _sys.platform == "darwin" else ["xdg-open", url]
    env = {k: v for k, v in os.environ.items() if not k.startswith(("QT_", "QTWEBENGINE"))}
    subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True, env=env)


@app.post("/api/open")
def open_link(req: OpenReq, request: Request):
    """Externe Links aus dem App-Fenster – nur http(s) und nur von der eigenen Oberfläche (eigener Header)."""
    from urllib.parse import urlparse
    if request.headers.get("x-tunebridge") != "1":
        raise HTTPException(403)
    u = urlparse(req.url.strip())
    if u.scheme not in ("http", "https") or not u.netloc or len(req.url) > 4000:
        raise HTTPException(400, "Kein gültiger Link")
    try:
        open_external(req.url.strip())
    except Exception as e:  # noqa: BLE001
        dbg.error("links", "Browser ließ sich nicht öffnen", e)
        raise HTTPException(500, f"Browser ließ sich nicht öffnen: {e}")
    return {"ok": True}


@app.post("/api/clipboard/write")
def clipboard_write(req: ClipReq):
    if (fn := WINDOW_HOOKS.get("clipboard_set")):
        try:
            fn(req.text[:20000])
            return {"ok": True}
        except Exception:  # noqa: BLE001
            pass
    return {"ok": False}

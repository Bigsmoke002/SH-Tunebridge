"""Automatischer Abgleich: holt regelmäßig Playlists und Likes deiner verbundenen Dienste und findet neue Songs.

Alles läuft auf diesem Rechner. Ablauf je Durchgang:
  1. Für jeden verbundenen Dienst (Login oder verknüpftes Profil) Lieblingssongs und – wenn gewünscht – die
     eigenen Playlists lesen (nur Titel, Künstler, Cover-Adresse; nie Musik).
  2. Beim allerersten Mal je Dienst wird nur der Ist-Stand gemerkt („Grundstand“) – sonst wäre alles „neu“.
  3. Danach: Songs, die vorher nicht da waren, werden analysiert (Genre, Tempo …) und bekommen Vorschläge,
     in welche deiner Playlists sie passen. Sie landen in „Neu von deinen Diensten“.
Gespeichert wird lokal: Einstellungen, eine Liste kurzer Prüfsummen bereits gesehener Songs (keine Titel) und
die Inbox (höchstens 300 Einträge, Cover nur als Adresse). Gelesene Dienst-Listen bleiben nur im Arbeitsspeicher.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
import uuid
from dataclasses import asdict

from . import store
from . import debuglog as dbg
from .models import Track

_CFG = "autosync"
_SEEN = "autosync_seen"
_INBOX = "autosync_inbox"
MAX_INBOX = 300
MAX_SEEN = 60000
MAX_NEW_PER_RUN = 40          # Rest kommt beim nächsten Durchgang dran
MAX_LISTS = 30                # Playlists je Dienst

DEFAULTS = {
    "enabled": True,
    "interval_h": 6,           # 1 … 48
    "lists": True,             # auch eigene Playlists (sonst nur Lieblingssongs)
    "services": {},            # sid -> False zum Ausschließen
    "last_run": 0.0,
}

_lock = threading.Lock()            # ein Durchgang zur Zeit
_ilock = threading.Lock()           # Inbox lesen/schreiben
_status: dict = {"running": False, "phase": None, "last": None, "errors": {}, "found": 0}
_thread: threading.Thread | None = None
_wake = threading.Event()


# ------------------------------------------------------------------ Einstellungen
def settings() -> dict:
    try:
        cur = json.loads(store.meta_get(_CFG) or "{}")
    except ValueError:
        cur = {}
    return {**DEFAULTS, **{k: v for k, v in cur.items() if k in DEFAULTS}}


def _write(cfg: dict) -> None:
    store.meta_set(_CFG, json.dumps(cfg))


def save(patch: dict) -> dict:
    cfg = settings()
    for k, v in patch.items():
        if k == "enabled" or k == "lists":
            cfg[k] = bool(v)
        elif k == "interval_h":
            cfg[k] = max(1, min(48, int(v)))
        elif k == "services" and isinstance(v, dict):
            cfg[k] = {**cfg["services"], **{str(s): bool(on) for s, on in v.items()}}
    _write(cfg)
    _wake.set()
    return cfg


# ------------------------------------------------------------------ gesehene Songs (nur Prüfsummen)
def _h(key: str) -> str:
    return hashlib.sha1(key.encode()).hexdigest()[:16]


def _seen() -> dict:
    try:
        d = json.loads(store.meta_get(_SEEN) or "{}")
    except ValueError:
        d = {}
    return {"base": d.get("base") or [], "keys": d.get("keys") or []}


def _save_seen(base: set, keys: list) -> None:
    store.meta_set(_SEEN, json.dumps({"base": sorted(base), "keys": keys[-MAX_SEEN:]}))


# ------------------------------------------------------------------ Inbox
def inbox() -> list[dict]:
    try:
        return json.loads(store.meta_get(_INBOX) or "[]")
    except ValueError:
        return []


def _save_inbox(items: list[dict]) -> None:
    store.meta_set(_INBOX, json.dumps(items[:MAX_INBOX], ensure_ascii=False))


def inbox_track(item: dict) -> Track:
    return Track(title=item["title"], artists=item.get("artists") or [], album=item.get("album"),
                 isrc=item.get("isrc"), ids=item.get("ids") or {}, genre=item.get("genre"),
                 subgenre=item.get("subgenre"), niche=item.get("niche"), cover=item.get("cover"),
                 preview_url=item.get("preview_url"), duration_ms=item.get("duration_ms"))


def take(item_id: str) -> dict | None:
    """Eintrag aus der Inbox nehmen (z. B. nach „Hinzufügen“ oder „Erledigt“)."""
    with _ilock:
        items = inbox()
        hit = next((x for x in items if x["id"] == item_id), None)
        if hit:
            _save_inbox([x for x in items if x["id"] != item_id])
    return hit


def clear_inbox() -> None:
    with _ilock:
        _save_inbox([])


def reset() -> None:
    """Alles vergessen: nächster Durchgang setzt nur einen neuen Grundstand."""
    if not _lock.acquire(timeout=5):
        raise RuntimeError("Abgleich läuft gerade – bitte kurz warten")
    try:
        store.meta_set(_SEEN, "{}")
        with _ilock:
            _save_inbox([])
    finally:
        _lock.release()


# ------------------------------------------------------------------ Quellen
def _account_state(sid: str):
    from .providers import get_provider
    prov = get_provider(sid)
    ok = prov.connected()
    return ok, (prov.account() if ok else None)


def sources() -> list[dict]:
    """Dienste, die gerade abgeglichen werden können (verbunden / Profil verknüpft)."""
    from . import services
    return [s for s in services.overview(_account_state) if s["ready"] and s["kind"] in ("account", "profile")]


def _collect(sid: str, with_lists: bool) -> list[tuple[str, Track]]:
    from . import services
    lists = services.playlists(sid)
    if not with_lists:
        lists = [p for p in lists if p["id"] == "__liked__"]
    out: list[tuple[str, Track]] = []
    for p in lists[:MAX_LISTS + 1]:
        try:
            _name, tracks = services.load(sid, p["id"])
        except Exception as e:  # noqa: BLE001 – eine kaputte Playlist darf den Rest nicht stoppen
            dbg.error("autosync", f"{sid}: Playlist {p.get('name')} nicht lesbar", e)
            continue
        out += [(p.get("name") or "", t) for t in tracks if t.title]
    return out


# ------------------------------------------------------------------ Durchgang
def run_once() -> dict:
    from . import linkimport
    from .suggest import suggest
    if not _lock.acquire(blocking=False):
        return {"ok": False, "error": "läuft schon"}
    _status.update(running=True, phase="Lese deine Dienste …", errors={}, found=0)
    found = 0
    try:
        cfg = settings()
        seen = _seen()
        base, keys = set(seen["base"]), list(seen["keys"])
        known = set(keys)
        local = {store.track_key(t) for p in store.local_playlists() for t in p.tracks}
        pls = store.local_playlists() + store.exported_playlists()
        items: list[dict] = []
        budget = MAX_NEW_PER_RUN
        for s in sources():
            sid = s["id"]
            if cfg["services"].get(sid) is False:
                continue
            _status["phase"] = f"Lese {s['name']} …"
            try:
                got = _collect(sid, cfg["lists"])
            except Exception as e:  # noqa: BLE001
                _status["errors"][sid] = str(e)[:200]
                continue
            first = sid not in base
            for src, t in got:
                k = _h(store.track_key(t))
                if k in known:
                    continue
                if first or store.track_key(t) in local:
                    known.add(k)
                    keys.append(k)
                    continue
                if budget <= 0:
                    continue                    # bleibt „ungesehen“ -> nächster Durchgang
                budget -= 1
                _status["phase"] = f"Analysiere neue Songs ({MAX_NEW_PER_RUN - budget}) …"
                try:
                    a = linkimport._analyse_one(t)
                except Exception as e:  # noqa: BLE001
                    dbg.error("autosync", "Analyse fehlgeschlagen", e)
                    a = {"title": t.title, "artists": t.artists, "cover": t.cover, "ids": t.ids, "isrc": t.isrc}
                tr = Track(title=a.get("title") or t.title, artists=a.get("artists") or t.artists,
                           album=a.get("album") or t.album, isrc=a.get("isrc") or t.isrc, ids=a.get("ids") or t.ids,
                           genre=a.get("genre"), subgenre=a.get("subgenre"), niche=a.get("niche"),
                           cover=a.get("cover") or t.cover, preview_url=a.get("preview_url") or t.preview_url,
                           duration_ms=t.duration_ms)
                sug = [asdict(x) for x in suggest(tr, pls, top=3)]
                items.insert(0, {"id": uuid.uuid4().hex[:12], "ts": time.time(), "sid": sid, "service": s["name"],
                                 "source": "Lieblingssongs" if src in ("Lieblingssongs", "Lieblingssongs (Loved Tracks)") else src,
                                 **{k2: v for k2, v in asdict(tr).items() if k2 != "tags"},
                                 "bpm": a.get("bpm"), "confidence": a.get("confidence"), "suggestions": sug})
                known.add(k)
                keys.append(k)
                found += 1
            base.add(sid)
        _save_seen(base, keys)
        with _ilock:
            _save_inbox(items + inbox())
        cfg = settings()
        cfg["last_run"] = time.time()
        _write(cfg)
        _status.update(last=time.time(), found=found)
        return {"ok": True, "found": found, "errors": _status["errors"]}
    finally:
        _status.update(running=False, phase=None)
        _lock.release()


def status() -> dict:
    cfg = settings()
    nxt = cfg["last_run"] + cfg["interval_h"] * 3600 if cfg["enabled"] else None
    return {"settings": cfg, "running": _status["running"], "phase": _status["phase"], "errors": _status["errors"],
            "found": _status["found"], "next_run": nxt, "count": len(inbox())}


# ------------------------------------------------------------------ Zeitplan
def _loop() -> None:
    time.sleep(90)                       # erst einmal in Ruhe starten lassen
    while True:
        cfg = settings()
        if cfg["enabled"] and time.time() >= cfg["last_run"] + cfg["interval_h"] * 3600:
            try:
                if sources():
                    run_once()
            except Exception as e:  # noqa: BLE001
                dbg.error("autosync", "Abgleich fehlgeschlagen", e)
        _wake.wait(timeout=300)
        _wake.clear()


def start() -> None:
    global _thread
    if _thread is None or not _thread.is_alive():
        _thread = threading.Thread(target=_loop, name="autosync", daemon=True)
        _thread.start()


def run_async() -> bool:
    if _status["running"]:
        return False
    threading.Thread(target=run_once, name="autosync-now", daemon=True).start()
    return True

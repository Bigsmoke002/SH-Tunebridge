"""Discord Rich Presence – zeigt in Discord, was SH-Tunebridge erkannt hat bzw. was du gerade machst.

Standard: AUS. Gesprochen wird nur mit dem Discord-Programm auf diesem Rechner (lokale IPC-Schnittstelle,
offizielles RPC-Protokoll); Discord zeigt es dann deinen Kontakten. Was angezeigt wird, stellst du in den
Einstellungen ein. Braucht eine Discord-„Application ID“ (öffentlich, kein Geheimnis).
"""

from __future__ import annotations

import json
import os
import struct
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path

from . import store
from . import debuglog as dbg

_KEY = "discord_rpc"
DEFAULT_CLIENT_ID = os.environ.get("TUNEBRIDGE_DISCORD_CLIENT_ID", "")
DEFAULTS = {
    "enabled": False, "client_id": "",
    "song": True,          # erkannten Song zeigen
    "cover": True,         # Cover als Bild (Discord lädt es vom Anbieter)
    "genre": True,         # Genre/Subgenre als Zusatz
    "preview": True,       # laufende Hörprobe zeigen
    "activity": True,      # was du in der App machst (Playlists, Sortieren, Entdecken …)
    "buttons": True,       # Knopf „Song anhören“ (Deezer/Suche)
    "elapsed": True,       # „seit 3:12“ anzeigen
    "keep_min": 10,        # erkannten Song so lange zeigen (Minuten)
    "idle": False,         # auch ohne Aktivität „SH-Tunebridge geöffnet“ zeigen
}
ACTIVITIES = {
    "listen": "Erkennt Musik", "history": "Stöbert im Verlauf", "playlists": "Sieht sich Playlists an",
    "services": "Sieht sich Playlists an", "sort": "Sortiert eine Playlist", "discover": "Entdeckt neue Musik",
    "split": "Teilt Playlists nach Genre auf", "transfer": "Überträgt Playlists", "links": "Importiert einen Link", "inbox": "Sortiert neue Songs ein",
}


def settings() -> dict:
    try:
        cur = json.loads(store.meta_get(_KEY) or "{}")
    except Exception:  # noqa: BLE001
        cur = {}
    out = {**DEFAULTS, **{k: v for k, v in cur.items() if k in DEFAULTS}}
    out["client_id"] = str(out["client_id"] or DEFAULT_CLIENT_ID).strip()
    return out


def save(patch: dict) -> dict:
    cur = settings()
    for k, v in patch.items():
        if k not in DEFAULTS:
            continue
        if k == "client_id":
            v = "".join(ch for ch in str(v) if ch.isdigit())[:24]
        elif k == "keep_min":
            v = max(1, min(240, int(v)))
        else:
            v = bool(v)
        cur[k] = v
    store.meta_set(_KEY, json.dumps(cur))
    RPC.wake()
    return status()


# ------------------------------------------------------------------ IPC-Verbindung
def _candidates() -> list[str]:
    if os.environ.get("TUNEBRIDGE_DISCORD_IPC"):
        return [os.environ["TUNEBRIDGE_DISCORD_IPC"]]
    if sys.platform == "win32":
        return [rf"\\?\pipe\discord-ipc-{i}" for i in range(10)]
    bases = [os.environ.get(k) for k in ("XDG_RUNTIME_DIR", "TMPDIR", "TMP", "TEMP")] + [tempfile.gettempdir(), "/tmp"]
    subs = ["", "app/com.discordapp.Discord", "app/com.discordapp.DiscordCanary", "snap.discord",
            "app/dev.vencord.Vesktop", ".flatpak/dev.vencord.Vesktop/xdg-run"]
    out = []
    for b in dict.fromkeys(x for x in bases if x):
        for s in subs:
            for i in range(10):
                p = str(Path(b) / s / f"discord-ipc-{i}")
                if p not in out:
                    out.append(p)
    return out


class _Conn:
    def __init__(self, client_id: str):
        self.f = None
        self.sock = None
        for p in _candidates():
            try:
                if sys.platform == "win32":
                    self.f = open(p, "r+b", buffering=0)   # noqa: SIM115
                else:
                    if not os.path.exists(p):
                        continue
                    import socket
                    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    s.settimeout(5)
                    s.connect(p)
                    self.sock = s
                break
            except OSError:
                continue
        if not (self.f or self.sock):
            raise ConnectionError("Discord läuft nicht (keine Verbindung zum Discord-Programm gefunden)")
        self._send(0, {"v": 1, "client_id": client_id})
        op, data = self._recv()
        if op != 1 or data.get("evt") != "READY":
            raise ConnectionError((data.get("data") or {}).get("message") or data.get("message") or "Discord hat abgelehnt")
        self.user = ((data.get("data") or {}).get("user") or {}).get("username")

    def _send(self, op: int, payload: dict) -> None:
        raw = json.dumps(payload, separators=(",", ":")).encode()
        msg = struct.pack("<II", op, len(raw)) + raw
        if self.sock:
            self.sock.sendall(msg)
        else:
            self.f.write(msg)

    def _read(self, n: int) -> bytes:
        buf = b""
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf)) if self.sock else self.f.read(n - len(buf))
            if not chunk:
                raise ConnectionError("Verbindung zu Discord getrennt")
            buf += chunk
        return buf

    def _recv(self) -> tuple[int, dict]:
        op, ln = struct.unpack("<II", self._read(8))
        return op, json.loads(self._read(ln) or b"{}")

    def activity(self, act: dict | None) -> None:
        self._send(1, {"cmd": "SET_ACTIVITY", "args": {"pid": os.getpid(), "activity": act}, "nonce": uuid.uuid4().hex})
        op, data = self._recv()
        if data.get("evt") == "ERROR":
            raise ValueError((data.get("data") or {}).get("message") or "Discord-Fehler")

    def close(self) -> None:
        for c in (self.sock, self.f):
            try:
                if c:
                    c.close()
            except OSError:
                pass


def _txt(s, n=128) -> str | None:
    s = " ".join(str(s or "").split())
    if len(s) < 2:
        return None
    return s if len(s) <= n else s[: n - 1] + "…"


# ------------------------------------------------------------------ Zustand & Zusammenbau
class _RPC:
    def __init__(self):
        self.song: dict | None = None        # {title, artists, cover, genre, subgenre, url, ts}
        self.preview: dict | None = None
        self.view: str | None = None
        self.view_ts = time.time()
        self.started = time.time()
        self.conn: _Conn | None = None
        self.state = "aus"
        self.error: str | None = None
        self.user: str | None = None
        self.last: str | None = None
        self._ev = threading.Event()
        self._thr: threading.Thread | None = None

    def wake(self) -> None:
        if self._thr is None or not self._thr.is_alive():
            self._thr = threading.Thread(target=self._loop, name="discord-rpc", daemon=True)
            self._thr.start()
        self._ev.set()

    # Ereignisse aus der App
    def on_song(self, title: str, artists: list[str], cover: str | None, genre: str | None, subgenre: str | None,
                url: str | None = None) -> None:
        self.song = {"title": title, "artists": artists, "cover": cover, "genre": genre, "subgenre": subgenre,
                     "url": url, "ts": time.time()}
        if settings()["enabled"]:
            self.wake()

    def on_preview(self, t: dict | None) -> None:
        self.preview = {**t, "ts": time.time()} if t else None
        if settings()["enabled"]:
            self.wake()

    def on_view(self, view: str | None) -> None:
        if view != self.view:
            self.view, self.view_ts = view, time.time()
            if settings()["enabled"]:
                self.wake()

    def compose(self, cfg: dict | None = None) -> dict | None:
        cfg = cfg or settings()
        now = time.time()
        act: dict = {"type": 2}             # 2 = „Hört …“
        s = self.song if self.song and cfg["song"] and now - self.song["ts"] < cfg["keep_min"] * 60 else None
        p = self.preview if self.preview and cfg["preview"] else None
        cur = p or s
        if cur:
            artists = ", ".join(cur.get("artists") or [])
            act["details"] = _txt(cur.get("title")) or "Unbekannter Song"
            act["state"] = _txt(("Hörprobe · " if p else "") + artists) or ("Hörprobe" if p else None)
            g = " – ".join(x for x in (cur.get("genre"), cur.get("subgenre")) if x)
            assets = {}
            if cfg["cover"] and str(cur.get("cover") or "").startswith("https://"):
                assets["large_image"] = cur["cover"]
            if cfg["genre"] and g:
                assets["large_text"] = _txt(g)
            elif assets:
                assets["large_text"] = _txt(cur.get("title"))
            if assets:
                act["assets"] = assets
            if cfg["elapsed"]:
                act["timestamps"] = {"start": int(cur["ts"])}
            if cfg["buttons"]:
                from urllib.parse import quote_plus
                url = cur.get("url") or f"https://www.deezer.com/search/{quote_plus(artists + ' ' + (cur.get('title') or ''))}"
                act["buttons"] = [{"label": "Song anhören", "url": url[:512]}]
        elif cfg["activity"] and self.view in ACTIVITIES:
            act["type"] = 0
            act["details"] = ACTIVITIES[self.view]
            if cfg["elapsed"]:
                act["timestamps"] = {"start": int(self.view_ts)}
        elif cfg["idle"]:
            act["type"] = 0
            act["details"] = "Bereit zum Erkennen"
        else:
            return None
        return {k: v for k, v in act.items() if v is not None}

    def _loop(self) -> None:
        while True:
            self._ev.wait(timeout=20)          # auch ohne Ereignis regelmäßig: Ablauf der Anzeigezeit
            self._ev.clear()
            cfg = settings()
            if not cfg["enabled"] or not cfg["client_id"]:
                if self.conn:
                    try:
                        self.conn.activity(None)
                    except Exception:  # noqa: BLE001
                        pass
                    self.conn.close()
                    self.conn = None
                self.state = "aus" if not cfg["enabled"] else "id_fehlt"
                self.last = None
                if not cfg["enabled"]:
                    return                       # Thread endet, bis wieder eingeschaltet
                continue
            act = self.compose(cfg)
            key = json.dumps(act, sort_keys=True)
            if key == self.last and self.conn:
                continue
            try:
                if not self.conn:
                    self.conn = _Conn(cfg["client_id"])
                    self.user = self.conn.user
                self.conn.activity(act)
                self.last, self.state, self.error = key, "verbunden", None
            except Exception as e:  # noqa: BLE001 – Discord zu, falsche ID …
                if self.conn:
                    self.conn.close()
                self.conn, self.last = None, None
                self.state, self.error = "fehler", str(e)
                if not isinstance(e, ConnectionError):
                    dbg.error("discord", "Discord-Status nicht gesetzt", e)
                time.sleep(10)
                self._ev.set()                   # später erneut versuchen


RPC = _RPC()


def status() -> dict:
    cfg = settings()
    return {**cfg, "state": RPC.state if cfg["enabled"] else "aus", "error": RPC.error, "user": RPC.user,
            "preview_activity": RPC.compose(cfg), "found": any(os.path.exists(p) for p in _candidates()[:60])
            if sys.platform != "win32" else None}


def start() -> None:
    if settings()["enabled"]:
        RPC.wake()

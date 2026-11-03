"""Datenverbrauch der App – gemessen nur auf diesem Rechner, nichts davon wird gesendet.

Gezählt wird an den Netzwerk-Sockets des Programms (alles außer 127.0.0.1/::1), zugeordnet zum Dienst über den
Hostnamen. Was das Fenster selbst lädt (Cover, Hörproben direkt vom Anbieter), meldet die Oberfläche dazu –
teils geschätzt, weil Browser fremde Downloadgrößen nicht immer verraten.
Gespeichert werden nur Tagessummen je Dienst (90 Tage), lokal in der Datenbank.
"""

from __future__ import annotations

import ipaddress
import json
import socket
import ssl
import threading
import time
from collections import deque

_lock = threading.Lock()
_FD: dict[int, str] = {}           # Socket-Nummer -> Hostname (nur ausgehende Verbindungen)
_IPHOST: dict[str, str] = {}       # IP -> Hostname (aus der Namensauflösung)
_installed = False

START = time.time()
_tot = {"in": 0, "out": 0}                      # seit Programmstart
_sess: dict[str, list] = {}                     # Dienst -> [in, out, geschätzt?]
_day_pending: dict[str, list] = {}              # noch nicht gespeicherte Tageswerte
_samples: deque = deque(maxlen=180)             # (t, in, out) – je Sekunde
KEEP_DAYS = 90
_META = "traffic_days"

# Hostname -> Dienst (erstes passendes Stück gewinnt)
GROUPS = [
    ("generativelanguage.googleapis", "KI: Gemini"), ("anthropic", "KI: Claude"), ("openai", "KI: OpenAI"),
    ("dzcdn", "Deezer"), ("deezer", "Deezer"), ("shazam", "Shazam"), ("mzstatic", "Apple / iTunes"),
    ("apple.com", "Apple / iTunes"), ("itunes", "Apple / iTunes"), ("audioscrobbler", "Last.fm"), ("last.fm", "Last.fm"),
    ("lastfm", "Last.fm"), ("musicbrainz", "MusicBrainz"), ("coverartarchive", "MusicBrainz"), ("archive.org", "MusicBrainz"),
    ("tidal", "TIDAL"), ("spotify", "Spotify"), ("scdn.co", "Spotify"), ("googleapis", "YouTube"), ("youtube", "YouTube"),
    ("ytimg", "YouTube"), ("ggpht", "YouTube"), ("soundcloud", "SoundCloud"), ("sndcdn", "SoundCloud"),
    ("song.link", "song.link"), ("odesli", "song.link"), ("audd", "AudD"), ("acrcloud", "ACRCloud"),
    ("github", "GitHub (Updates)"), ("huggingface", "Hugging Face (Modelle)"), ("hf.co", "Hugging Face (Modelle)"),
    ("bs002.de", "SH-Tunebridge-Server"), ("discord", "Discord"),
]


def group(host: str) -> str:
    h = (host or "").lower()
    for part, name in GROUPS:
        if part in h:
            return name
    return h or "Sonstige"


def _local(ip: str) -> bool:
    try:
        return ipaddress.ip_address(ip.split("%")[0]).is_loopback
    except ValueError:
        return False


def add(host: str, n_in: int = 0, n_out: int = 0, estimated: bool = False) -> None:
    g = group(host)
    with _lock:
        _tot["in"] += n_in
        _tot["out"] += n_out
        for d in (_sess, _day_pending):
            e = d.setdefault(g, [0, 0, False])
            e[0] += n_in
            e[1] += n_out
            e[2] = e[2] or estimated


# ------------------------------------------------------------------ Sockets anzapfen
def _mark(sock, address) -> None:
    try:
        if sock.family not in (socket.AF_INET, socket.AF_INET6) or not isinstance(address, tuple):
            return
        ip = str(address[0])
        if _local(ip):
            return
        _FD[sock.fileno()] = _IPHOST.get(ip, ip)
    except Exception:  # noqa: BLE001 – Messen darf das Netz nie stören
        pass


def _count(sock, n_in: int, n_out: int) -> None:
    try:
        h = _FD.get(sock.fileno())
    except Exception:  # noqa: BLE001
        return
    if h is not None and (n_in or n_out):
        add(h, n_in, n_out)


def install() -> None:
    """Einmal beim Start: Namensauflösung, Verbindungsaufbau und Lesen/Schreiben mitzählen."""
    global _installed
    if _installed:
        return
    _installed = True
    S, raw = socket.socket, socket.socket.__mro__[1]           # Python-Klasse / C-Basis (_socket.socket)
    o_gai = socket.getaddrinfo

    def getaddrinfo(host, *a, **k):
        res = o_gai(host, *a, **k)
        try:
            if isinstance(host, (str, bytes)) and len(_IPHOST) < 5000:
                hn = host.decode() if isinstance(host, bytes) else host
                for r in res:
                    _IPHOST[str(r[4][0])] = hn
        except Exception:  # noqa: BLE001
            pass
        return res
    socket.getaddrinfo = getaddrinfo

    o_connect, o_connect_ex = S.connect, S.connect_ex

    def connect(self, address):
        _mark(self, address)
        return o_connect(self, address)

    def connect_ex(self, address):
        _mark(self, address)
        return o_connect_ex(self, address)

    def recv(self, *a, **k):
        d = raw.recv(self, *a, **k)
        _count(self, len(d), 0)
        return d

    def recv_into(self, *a, **k):
        n = raw.recv_into(self, *a, **k)
        _count(self, n or 0, 0)
        return n

    def send(self, *a, **k):
        n = raw.send(self, *a, **k)
        _count(self, 0, n or 0)
        return n

    def sendall(self, data, *a, **k):
        r = raw.sendall(self, data, *a, **k)
        try:
            _count(self, 0, memoryview(data).nbytes)
        except TypeError:
            pass
        return r

    o_real_close = S._real_close

    def _real_close(self, *a, **k):
        try:
            _FD.pop(self.fileno(), None)
        except Exception:  # noqa: BLE001
            pass
        return o_real_close(self, *a, **k)

    o_accept = S.accept

    def accept(self):
        conn, addr = o_accept(self)
        try:
            _FD.pop(conn.fileno(), None)            # eingehend (z. B. das eigene Fenster) – nicht zählen
        except Exception:  # noqa: BLE001
            pass
        return conn, addr

    S.connect, S.connect_ex, S.recv, S.recv_into, S.send, S.sendall = connect, connect_ex, recv, recv_into, send, sendall
    S._real_close, S.accept = _real_close, accept

    # TLS (requests/httpx synchron): entschlüsselte Nutzdaten zählen
    T = ssl.SSLSocket
    o_read, o_write, o_ssend = T.read, T.write, T.send

    def read(self, *a, **k):
        r = o_read(self, *a, **k)
        _count(self, r if isinstance(r, int) else len(r), 0)
        return r

    def write(self, data):
        n = o_write(self, data)
        _count(self, 0, n or 0)
        return n

    def tsend(self, data, flags=0):
        if self._sslobj is None:
            return o_ssend(self, data, flags)       # unverschlüsselt -> zählt schon socket.send
        n = o_ssend(self, data, flags)
        _count(self, 0, n or 0)
        return n
    T.read, T.write, T.send = read, write, tsend

    threading.Thread(target=_sampler, name="traffic", daemon=True).start()


# ------------------------------------------------------------------ Verlauf & Speichern
def _today() -> str:
    return time.strftime("%Y-%m-%d")


def _load_days() -> dict:
    from . import store
    try:
        return json.loads(store.meta_get(_META) or "{}")
    except Exception:  # noqa: BLE001
        return {}


def flush() -> None:
    """Tageswerte in die lokale Datenbank schreiben (alle 30 s und beim Beenden)."""
    from . import store
    with _lock:
        pend = {k: v[:] for k, v in _day_pending.items()}
        _day_pending.clear()
    if not pend:
        return
    days = _load_days()
    day = days.setdefault(_today(), {})
    for g, (i, o, est) in pend.items():
        e = day.setdefault(g, [0, 0, False])
        e[0] += i
        e[1] += o
        e[2] = bool(e[2] or est)
    for d in sorted(days)[:-KEEP_DAYS]:
        days.pop(d, None)
    store.meta_set(_META, json.dumps(days))


def _sampler() -> None:
    n = 0
    while True:
        with _lock:
            _samples.append((time.time(), _tot["in"], _tot["out"]))
        n += 1
        if n % 30 == 0:
            try:
                flush()
            except Exception:  # noqa: BLE001
                pass
        time.sleep(1)


def live() -> dict:
    """Aktuelle Rate (Bytes/s, Mittel der letzten 3 s), Sitzung und heute."""
    with _lock:
        s = list(_samples)
        tot = dict(_tot)
        pend = sum(v[0] + v[1] for v in _day_pending.values())
    rate_in = rate_out = 0.0
    if len(s) >= 2:
        a, b = s[max(0, len(s) - 4)], s[-1]
        dt = max(b[0] - a[0], 0.5)
        rate_in, rate_out = (b[1] - a[1]) / dt, (b[2] - a[2]) / dt
    today = _load_days().get(_today(), {})
    return {"rate_in": round(rate_in), "rate_out": round(rate_out), "session": tot["in"] + tot["out"],
            "today": sum(v[0] + v[1] for v in today.values()) + pend}


def summary() -> dict:
    flush()
    days = _load_days()
    keys = sorted(days)
    t = _today()

    def total(ds):
        agg: dict[str, list] = {}
        for d in ds:
            for g, (i, o, est) in days.get(d, {}).items():
                e = agg.setdefault(g, [0, 0, False])
                e[0] += i
                e[1] += o
                e[2] = bool(e[2] or est)
        return agg
    last30 = [d for d in keys if d >= time.strftime("%Y-%m-%d", time.localtime(time.time() - 29 * 86400))]
    with _lock:
        s = list(_samples)[-120:]
        sess = {g: v[:] for g, v in _sess.items()}
    rows = lambda agg: sorted(({"name": g, "in": v[0], "out": v[1], "est": v[2]} for g, v in agg.items()),  # noqa: E731
                              key=lambda r: -(r["in"] + r["out"]))
    hist = [{"t": round(b[0]), "in": max(0, b[1] - a[1]), "out": max(0, b[2] - a[2])} for a, b in zip(s, s[1:])]
    return {**live(), "since": START, "first_day": keys[0] if keys else t,
            "rows": {"session": rows(sess), "today": rows(total([t])), "days30": rows(total(last30)), "all": rows(total(keys))},
            "daily": [{"day": d, "bytes": sum(v[0] + v[1] for v in days[d].values())} for d in keys[-14:]],
            "history": hist}


def reset() -> None:
    from . import store
    with _lock:
        _day_pending.clear()
        _sess.clear()
        _tot.update({"in": 0, "out": 0})
        _samples.clear()
    store.meta_set(_META, "{}")

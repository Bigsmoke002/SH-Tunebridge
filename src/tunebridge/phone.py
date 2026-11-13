"""Handys koppeln und abgleichen – direkt im eigenen Netz, ohne Server dazwischen.

Ablauf
* **Koppeln:** Die App am PC zeigt einen QR-Code mit den Netzwerk-Adressen des PCs und einem Einmal-Code
  (100 Bit, 5 Minuten gültig, nur einmal). Aus dem Code leiten PC und Handy denselben Schlüssel ab (HKDF);
  das Handy schickt damit verschlüsselt ein neues, zufälliges Geräte-Geheimnis (32 Byte).
  **Beide Seiten bestätigen ausdrücklich:** erst das Handy (nachdem es angezeigt hat, was wann wohin geht),
  dann der PC („Zulassen“). Beide zeigen dieselbe vierstellige Prüfzahl – so ist klar, dass es dasselbe Gerät ist.
* **Abgleich:** Jede Anfrage und Antwort ist mit AES-256-GCM verschlüsselt (Schlüssel aus dem Geheimnis),
  enthält Zeitstempel und Einmal-ID gegen Wiederholung. Wer im WLAN mitliest, sieht nur, dass abgeglichen wird.
* **Netzwerke:** Der PC erkennt seine Heimnetze (z. B. 192.168.178.0/24) und VPNs. Du wählst, wo er
  Handys annimmt: in allen, nur in bestimmten oder nur im Haupt-Heimnetz. Er lauscht dann **nur** auf seinen
  Adressen in diesen Netzen und nimmt nur Anfragen aus diesen Netzen an. Virtuelle Netze (Docker, VMs) nie.
* **Erreichbarkeit:** Ein eigener kleiner Server nur für diese Anfragen, auf einem eigenen Port. Er läuft nur,
  während ein Kopplungs-Code offen ist oder mindestens ein Handy gekoppelt und der Abgleich eingeschaltet ist.
  Die eigentliche App-Oberfläche bleibt wie bisher nur auf 127.0.0.1.

Gleiches Verschlüsselungs-Format wie beim Teilen (share.seal/unseal), damit die Android-App eine Umsetzung braucht.
"""

from __future__ import annotations

import base64
import ipaddress
import json
import os
import secrets
import socket
import threading
import time
from collections import OrderedDict
from dataclasses import asdict

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from . import config, consent, store
from . import debuglog as dbg
from .models import Track
from .share import ShareError, seal, unseal

PORT = int(os.environ.get("TUNEBRIDGE_PHONE_PORT") or 8766)
PAIR_SECONDS = 300
PAIR_TRIES = 8
CONFIRM_SECONDS = 120          # so lange wartet das Handy, bis am PC „Zulassen“ geklickt wird
MAX_BODY = 8 << 20
MAX_SKEW = 600                 # Sekunden Uhr-Abweichung zwischen Handy und PC
MAX_DEVICES = 10
RECS_PER_SYNC = 400
MAX_PLAYLIST_TRACKS = 40_000
NET_MODES = ("all", "some", "primary")
CGNAT = ipaddress.ip_network("100.64.0.0/10")         # Netz vieler VPN-Dienste (CGNAT-Bereich)
_VIRTUAL = ("docker", "br-", "veth", "virbr", "vmnet", "vboxnet", "lxc", "lxd", "podman", "cni", "flannel",
            "vethernet", "hyper-v", "virtualbox", "vmware")
_VPN = ("wireguard", "wg", "tun", "utun", "zt", "zerotier", "vpn")
_SALT = b"sh-tunebridge-phone-v1"
_B32 = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
_FILE = lambda: config.DATA / "tokens" / "phone.json"  # noqa: E731

_lock = threading.RLock()
_pairing: dict | None = None   # {"code", "expires", "tries", "request": {...} | None, "paired": device_id | None}
_seen: OrderedDict[str, float] = OrderedDict()     # Einmal-IDs der letzten Minuten (Schutz gegen Wiederholung)
_server: dict = {}             # {"thread", "server", "ips"}
_nets_cache: dict = {"t": 0.0, "v": []}


class PhoneError(RuntimeError):
    def __init__(self, msg: str, status: int = 400):
        super().__init__(msg)
        self.status = status


# ------------------------------------------------------------------ Zustand (nur lokal, Datei nur für dich lesbar)
def _load() -> dict:
    try:
        st = json.loads(_FILE().read_text())
    except (OSError, ValueError):
        st = {}
    st.setdefault("pc_id", secrets.token_hex(8))
    st.setdefault("devices", {})
    st.setdefault("enabled", True)
    net = st.setdefault("net", {})
    if net.get("mode") not in NET_MODES:
        net["mode"] = "all"
    net.setdefault("selected", [])
    st.setdefault("net_consent", False)   # Netzwerke erkennen erst nach ausdrücklicher Zustimmung
    return st


def _save(st: dict) -> None:
    p = _FILE()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(st, ensure_ascii=False, indent=1))
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    tmp.replace(p)


def _kdf(ikm: bytes, info: str, length: int = 32) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=length, salt=_SALT, info=info.encode()).derive(ikm)


def confirm_code(code: str, dev_id: str) -> str:
    """Vierstellige Prüfzahl, die PC und Handy unabhängig voneinander aus Code + Geräte-ID berechnen."""
    return f"{int.from_bytes(_kdf(_norm_code(code).encode(), f'confirm:{dev_id}', 4), 'big') % 10000:04d}"


def _pc_name() -> str:
    return (socket.gethostname() or "PC").split(".")[0][:40]


def _norm_code(s: str) -> str:
    return "".join(ch for ch in (s or "").upper() if ch in _B32)


# ------------------------------------------------------------------ Netzwerke erkennen
def _primary_ip() -> str | None:
    """Adresse, über die der PC normalerweise ins Netz geht (Routing-Tabelle; UDP-„connect“ sendet nichts)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.168.0.1", 9))
            return s.getsockname()[0]
    except OSError:
        return None


def networks(fresh: bool = False) -> list[dict]:
    """Heimnetze und VPNs dieses PCs: [{cidr, ip, iface, kind: lan|vpn, label, primary}].
    Ohne Loopback, Link-Local und virtuelle Netze (Docker, VMs) – dort sind keine Handys."""
    if not _load()["net_consent"]:      # ohne Zustimmung keine Netzwerkkarten auslesen – serverseitig erzwungen
        _nets_cache.update(t=0.0, v=[])
        return []
    now = time.time()
    if not fresh and now - _nets_cache["t"] < 10:
        return [dict(n) for n in _nets_cache["v"]]
    import ifaddr
    primary = _primary_ip()
    out: list[dict] = []
    for a in ifaddr.get_adapters():
        name = a.nice_name or a.name
        low = f"{a.name} {name}".lower()
        if any(low.startswith(v) or f" {v}" in low for v in _VIRTUAL):
            continue
        for ip in a.ips:
            if not isinstance(ip.ip, str):            # nur IPv4 – Handys im Heimnetz haben immer eine
                continue
            addr = ipaddress.ip_address(ip.ip)
            if addr.is_loopback or addr.is_link_local:
                continue
            cgnat = addr in CGNAT
            if not (addr.is_private or cgnat):
                continue
            vpn = cgnat or any(low.startswith(v) or v in low.split() for v in _VPN)
            net = CGNAT if cgnat else ipaddress.ip_interface(f"{ip.ip}/{ip.network_prefix}").network
            if vpn:
                label = "VPN"
            else:
                wifi = a.name.startswith(("wl", "wlan")) or any(w in low for w in ("wi-fi", "wlan", "wireless", "airport"))
                label = "Heimnetz · WLAN" if wifi else "Heimnetz · Kabel"
            item = {"cidr": str(net), "ip": ip.ip, "iface": name, "kind": "vpn" if vpn else "lan", "label": label,
                    "primary": ip.ip == primary}
            if not any(o["cidr"] == item["cidr"] and o["ip"] == item["ip"] for o in out):
                out.append(item)
    out.sort(key=lambda n: (not n["primary"], n["kind"] != "lan", n["cidr"]))
    _nets_cache.update(t=now, v=out)
    return [dict(n) for n in out]


def effective(st: dict | None = None) -> list[dict]:
    """Netze, in denen der PC Handys annimmt – nach deiner Auswahl (alle / bestimmte / nur das Haupt-Heimnetz)."""
    st = st or _load()
    nets, mode = networks(), st["net"]["mode"]
    if mode == "primary":
        return [n for n in nets if n["primary"]] or [n for n in nets if n["kind"] == "lan"][:1]
    if mode == "some":
        sel = set(st["net"]["selected"])
        return [n for n in nets if n["cidr"] in sel]
    return nets


def addresses() -> list[str]:
    """Adressen für den QR-Code: nur die in den gewählten Netzen, Haupt-Heimnetz zuerst."""
    return [f"{n['ip']}:{PORT}" for n in effective()]


def _allowed(client: str | None, nets: list[dict] | None = None) -> bool:
    try:
        a = ipaddress.ip_address((client or "").split("%")[0])
    except ValueError:
        return False
    for n in effective() if nets is None else nets:
        if a in ipaddress.ip_network(n["cidr"]):
            return True
    return False


# ------------------------------------------------------------------ Oberfläche am PC
def status() -> dict:
    st = _load()
    with _lock:
        p = _pairing if _pairing and _pairing["expires"] > time.time() else None
        req = p.get("request") if p else None
        pairing = None if not p else {
            "expires": p["expires"], "paired": p.get("paired") or False,
            "request": {k: req[k] for k in ("name", "ip", "app", "check", "at")} if req and req.get("decision") is None else None,
        }
    nets, eff = networks(), effective(st)
    eff_ids = {(n["cidr"], n["ip"]) for n in eff}
    srv = _server.get("thread")
    return {
        "enabled": st["enabled"], "net_consent": st["net_consent"], "port": PORT, "pc_name": _pc_name(),
        "running": bool(srv and srv.is_alive()), "listening": [f"{ip}:{PORT}" for ip in _server.get("ips", [])] if srv and srv.is_alive() else [],
        "addresses": [f"{n['ip']}:{PORT}" for n in eff],
        "net": st["net"],
        "networks": [{**n, "active": (n["cidr"], n["ip"]) in eff_ids} for n in nets],
        "devices": [{"id": k, "name": d.get("name"), "added": d.get("added"), "last_seen": d.get("last_seen"),
                     "app": d.get("app"), "last_counts": d.get("last_counts"), "ip": d.get("ip"),
                     "relay": bool(d.get("relay")), "via": d.get("via")}
                    for k, d in sorted(st["devices"].items(), key=lambda kv: -(kv[1].get("last_seen") or kv[1].get("added") or 0))],
        "pairing": pairing, "relay_allowed": consent.server("relay"),
    }


def start_pairing() -> dict:
    """Neuen Einmal-Code anlegen und den Server starten. -> Code, Adressen, QR-Inhalt (für den QR-Code)."""
    global _pairing
    st = _load()
    if len(st["devices"]) >= MAX_DEVICES:
        raise PhoneError(f"Höchstens {MAX_DEVICES} Handys – bitte erst eines entfernen")
    if not st["net_consent"]:
        raise PhoneError("Bitte erst erlauben, dass SH-Tunebridge die Netzwerke dieses PCs erkennt", 403)
    if not st["enabled"]:
        raise PhoneError("Der Handy-Abgleich ist ausgeschaltet – erst unten „Abgleich im Netz erlauben“ einschalten")
    addrs = addresses()
    if not addrs:
        raise PhoneError("Kein passendes Netzwerk – ist der PC im WLAN/LAN, und ist unter „Netzwerke“ eines ausgewählt?")
    code = "".join(secrets.choice(_B32) for _ in range(20))
    with _lock:
        old = _pairing
        _pairing = {"code": code, "expires": time.time() + PAIR_SECONDS, "tries": 0, "request": None, "paired": None}
    _reject_waiting(old)
    ensure_server(force=True)
    from urllib.parse import quote
    uri = f"shtb://pair?v=1&a={','.join(addrs)}&c={code}&n={quote(_pc_name())}&p={st['pc_id']}"
    return {"code": "-".join(code[i:i + 4] for i in range(0, 20, 4)), "addresses": addrs, "uri": uri,
            "expires": _pairing["expires"], "pc_name": _pc_name()}


def _reject_waiting(p: dict | None) -> None:
    req = p and p.get("request")
    if req and req.get("decision") is None:
        req["decision"] = False
        req["event"].set()


def cancel_pairing() -> None:
    global _pairing
    with _lock:
        old, _pairing = _pairing, None
    _reject_waiting(old)
    ensure_server()


def decide(ok: bool) -> dict:
    """„Zulassen“ oder „Ablehnen“ am PC für die wartende Kopplungsanfrage."""
    global _pairing
    with _lock:
        p = _pairing
        req = p and p.get("request")
        if not req or req.get("decision") is not None:
            raise PhoneError("Es wartet gerade keine Anfrage", 404)
        req["decision"] = bool(ok)
        req["event"].set()
        if not ok:
            _pairing = None             # abgelehnt: Code ist verbraucht, für einen neuen Versuch neuen Code zeigen
    return status()


def qr_svg(text: str) -> str:
    import io

    import segno
    buf = io.BytesIO()
    # omitsize: nur viewBox, keine feste Pixelgröße – sonst schneidet ein skaliertes Fenster (HiDPI) den Code ab
    segno.make(text, error="m").save(buf, kind="svg", scale=6, border=3, dark="#0e1013", light="#ffffff", xmldecl=False,
                                    svgns=True, nl=False, omitsize=True)
    return buf.getvalue().decode().replace("<svg ", '<svg shape-rendering="crispEdges" ', 1)


def remove_device(dev_id: str) -> None:
    st = _load()
    d = st["devices"].pop(dev_id, None)
    _save(st)
    if d and d.get("relay"):
        _relay_delete(d)
    ensure_server()


def set_enabled(on: bool) -> None:
    st = _load()
    st["enabled"] = bool(on)
    _save(st)
    if not on:
        cancel_pairing()
    ensure_server()


def set_net_consent(ok: bool) -> dict:
    """Zustimmung, dass die App die Netzwerkkarten dieses PCs ausliest (Adressen, Netze, Name der Karte).
    Widerruf: sofort nichts mehr auslesen, Kopplung abbrechen, Handy-Zugang schließen."""
    st = _load()
    st["net_consent"] = bool(ok)
    if ok:
        st["net_consent_at"] = time.time()
    else:
        st.pop("net_consent_at", None)
    _save(st)
    _nets_cache.update(t=0.0, v=[])
    if not ok:
        cancel_pairing()
    ensure_server()
    return status()


def set_network(mode: str, selected: list[str] | None = None) -> dict:
    if mode not in NET_MODES:
        raise PhoneError("Unbekannte Auswahl")
    sel = []
    for c in selected or []:
        try:
            sel.append(str(ipaddress.ip_network(str(c), strict=False)))
        except ValueError:
            raise PhoneError(f"Kein gültiges Netz: {c}") from None
    if mode == "some" and not sel:
        raise PhoneError("Bitte mindestens ein Netz auswählen")
    st = _load()
    st["net"] = {"mode": mode, "selected": sel}
    _save(st)
    networks(fresh=True)
    ensure_server()
    return status()


# ------------------------------------------------------------------ Anfragen vom Handy
def handle_pair(body: dict, client: str | None = None) -> dict:
    global _pairing
    dev_id = str(body.get("id") or "")[:32]
    if not dev_id.isalnum():
        raise PhoneError("Ungültige Anfrage")
    with _lock:
        p = _pairing
        if not p or p["expires"] < time.time() or p.get("paired"):
            raise PhoneError("Kein Kopplungs-Code offen – am PC „Handy koppeln“ neu starten", 403)
        p["tries"] += 1
        if p["tries"] > PAIR_TRIES:
            _pairing = None
            raise PhoneError("Zu viele Versuche – am PC einen neuen Code anzeigen lassen", 429)
        code = p["code"]
        key = _kdf(code.encode(), "pair")
    try:
        inner = unseal(key, f"pair:{dev_id}", str(body.get("box") or ""))
    except ShareError:
        raise PhoneError("Code passt nicht – Tippfehler oder abgelaufen?", 403) from None
    secret = base64.b64decode(inner.get("secret") or "")
    if len(secret) != 32:
        raise PhoneError("Ungültige Anfrage")
    name = str(inner.get("name") or "Handy")[:60]
    app = str(inner.get("app") or "")[:20]

    # Am PC bestätigen lassen: Anfrage anzeigen und warten, bis „Zulassen“ oder „Ablehnen“ geklickt wird
    with _lock:
        if p is not _pairing:
            raise PhoneError("Der Kopplungs-Code wurde am PC beendet", 403)
        cur = p.get("request")
        if cur and cur.get("decision") is None and cur["dev_id"] != dev_id:
            raise PhoneError("Am PC wartet schon eine andere Kopplungsanfrage", 409)
        _reject_waiting(p)        # gleiches Handy fragt erneut (z. B. Verbindung abgebrochen): alte Anfrage ersetzen
        req = {"dev_id": dev_id, "name": name, "ip": client, "app": app, "check": confirm_code(code, dev_id),
               "at": time.time(), "event": threading.Event(), "decision": None}
        p["request"] = req
        p["expires"] = max(p["expires"], time.time() + CONFIRM_SECONDS + 10)
    dbg.event("handy", "Kopplungsanfrage – wartet auf Bestätigung am PC", name=name)
    answered = req["event"].wait(CONFIRM_SECONDS)
    if not answered:
        with _lock:
            if req.get("decision") is None:
                req["decision"] = False
        raise PhoneError("Am PC wurde nicht rechtzeitig bestätigt – bitte neu versuchen", 408)
    if not req["decision"]:
        raise PhoneError("Am PC abgelehnt", 403)

    st = _load()
    # Dasselbe Handy neu gekoppelt (z. B. App neu installiert): alten Eintrag ersetzen statt doppelt führen
    for old in [k for k, d in st["devices"].items() if d.get("name") == name]:
        st["devices"].pop(old)
    st["devices"][dev_id] = {"name": name, "secret": base64.b64encode(secret).decode(), "added": time.time(),
                             "app": app, "last_seen": None, "ip": client}
    _save(st)
    with _lock:
        if _pairing is p:
            p["paired"] = dev_id
            p["request"] = None
            p["expires"] = time.time() + 20      # Oberfläche bekommt noch mit, dass es geklappt hat
    dbg.event("handy", "Handy gekoppelt", name=name)
    return {"box": seal(key, f"pair-ok:{dev_id}", {"pc_id": st["pc_id"], "pc_name": _pc_name(), "addrs": addresses()})}


def _device(dev_id: str) -> dict:
    d = _load()["devices"].get(dev_id)
    if not d:
        raise PhoneError("Dieses Handy ist nicht (mehr) gekoppelt – bitte neu koppeln", 403)
    return d


def _replay_check(ts_ms: int, rid: str) -> None:
    now = time.time()
    if abs(now - ts_ms / 1000) > MAX_SKEW:
        raise PhoneError("Uhrzeit von Handy und PC weicht zu stark ab", 403)
    with _lock:
        for k in [k for k, t in _seen.items() if now - t > 2 * MAX_SKEW]:
            _seen.pop(k, None)
        if rid in _seen:
            raise PhoneError("Anfrage wurde schon verarbeitet", 409)
        _seen[rid] = now


def handle_sync(body: dict, client: str | None = None) -> dict:
    dev_id = str(body.get("id") or "")[:32]
    d = _device(dev_id)
    key = _kdf(base64.b64decode(d["secret"]), "sync")
    try:
        req = unseal(key, f"sync:{dev_id}", str(body.get("box") or ""))
    except ShareError:
        raise PhoneError("Anfrage ließ sich nicht prüfen – bitte neu koppeln", 403) from None
    rid = str(req.get("rid") or "")[:64]
    _replay_check(int(req.get("ts") or 0), rid)
    answer = apply(req, d.get("name") or "Handy")
    _touch(dev_id, req, answer, client)
    return {"box": seal(key, f"sync-ok:{dev_id}:{rid}", answer, limit=None)}


def _touch(dev_id: str, req: dict, answer: dict, client: str | None, via: str = "netz") -> None:
    st = _load()
    if dev_id in st["devices"]:
        dev = st["devices"][dev_id]
        dev["last_seen"] = time.time()
        dev["via"] = via
        if via == "netz":
            dev["ip"] = client or dev.get("ip")
        dev["app"] = str((req.get("device") or {}).get("app") or dev.get("app") or "")[:20]
        dev["name"] = str((req.get("device") or {}).get("name") or dev.get("name") or "Handy")[:60]
        dev["last_counts"] = {"empfangen": len(req.get("recs") or []), "gesendet": len(answer["recs"])}
        _save(st)


def handle_similar(body: dict, client: str | None = None) -> dict:
    """Ähnliche Songs für das Handy (Mehr dazu: similar.py) – gleiche Verschlüsselung wie der Abgleich.
    Das Handy schickt nur Titel/Künstler/ISRC des Songs; der PC fragt Last.fm/Deezer wie bei sich selbst."""
    dev_id = str(body.get("id") or "")[:32]
    d = _device(dev_id)
    key = _kdf(base64.b64decode(d["secret"]), "sync")
    try:
        req = unseal(key, f"similar:{dev_id}", str(body.get("box") or ""))
    except ShareError:
        raise PhoneError("Anfrage ließ sich nicht prüfen – bitte neu koppeln", 403) from None
    rid = str(req.get("rid") or "")[:64]
    _replay_check(int(req.get("ts") or 0), rid)
    t = _track(req.get("track") or {})
    if not t.artists or t.title == "?":
        raise PhoneError("Song fehlt")
    from . import ratelimit, similar
    try:
        cands = similar.find(t, limit=max(1, min(int(req.get("limit") or 15), 30)))
    except ratelimit.LimitReached as e:
        raise PhoneError(f"{e} – bitte gleich nochmal versuchen", 429) from None
    from dataclasses import asdict
    items = [{**_slim(asdict(c)), "match": round(m, 2)} for c, m in cands]
    return {"box": seal(key, f"similar-ok:{dev_id}:{rid}", {"items": items}, limit=None)}


def handle_versions(body: dict, client: str | None = None) -> dict:
    """Remixe, Covers & andere Versionen für das Handy (remixes.py) – Verschlüsselung wie bei handle_similar.
    Das Handy schickt nur Titel/Künstler des Songs; der PC fragt Deezer wie bei sich selbst."""
    dev_id = str(body.get("id") or "")[:32]
    d = _device(dev_id)
    key = _kdf(base64.b64decode(d["secret"]), "sync")
    try:
        req = unseal(key, f"versions:{dev_id}", str(body.get("box") or ""))
    except ShareError:
        raise PhoneError("Anfrage ließ sich nicht prüfen – bitte neu koppeln", 403) from None
    rid = str(req.get("rid") or "")[:64]
    _replay_check(int(req.get("ts") or 0), rid)
    t = _track(req.get("track") or {})
    if t.title == "?":
        raise PhoneError("Song fehlt")
    from . import ratelimit, remixes
    try:
        items = remixes.find(t)
    except ratelimit.LimitReached as e:
        raise PhoneError(f"{e} – bitte gleich nochmal versuchen", 429) from None
    keep = ("title", "artists", "album", "duration_ms", "cover", "ids", "link", "kind", "label")
    out = [{k: v[k] for k in keep if v.get(k) not in (None, "", [], {})} for v in items]
    return {"box": seal(key, f"versions-ok:{dev_id}:{rid}", {"core": remixes.core_title(t.title),
                                                              "kinds": [{"id": k, "name": n} for k, n in remixes.KINDS],
                                                              "items": out}, limit=None)}


def handle_discover(body: dict, client: str | None = None) -> dict:
    """„Entdecken“ fürs Handy (discover.py): Suche, Künstler, Album, Charts, Genres im Deezer-Katalog.
    Das Handy schickt nur Suchbegriff bzw. Deezer-Kennung; der PC fragt Deezer wie bei sich selbst."""
    dev_id = str(body.get("id") or "")[:32]
    d = _device(dev_id)
    key = _kdf(base64.b64decode(d["secret"]), "sync")
    try:
        req = unseal(key, f"discover:{dev_id}", str(body.get("box") or ""))
    except ShareError:
        raise PhoneError("Anfrage ließ sich nicht prüfen – bitte neu koppeln", 403) from None
    rid = str(req.get("rid") or "")[:64]
    _replay_check(int(req.get("ts") or 0), rid)
    from . import discover, ratelimit
    what, arg = str(req.get("what") or ""), req.get("arg")
    try:
        if what == "search":
            kind = str(req.get("kind") or "all")
            res = discover.search_all(str(arg or "")) if kind == "all" else discover.search(str(arg or ""), kind)
        elif what == "artist":
            res = discover.artist_page(arg)
        elif what == "album":
            res = discover.album_page(arg)
        elif what == "charts":
            res = discover.charts(arg if arg not in (None, "") else 0)
        elif what == "genres":
            res = {"genres": discover.genres()}
        else:
            raise PhoneError("Unbekannte Anfrage")
    except ratelimit.LimitReached as e:
        raise PhoneError(f"{e} – bitte gleich nochmal versuchen", 429) from None
    except LookupError as e:
        raise PhoneError(str(e), 404) from None
    except ValueError as e:
        raise PhoneError(str(e)) from None
    return {"box": seal(key, f"discover-ok:{dev_id}:{rid}", res, limit=None)}


def handle_fallback(body: dict, client: str | None = None) -> dict:
    """Ersatz-Player fürs Handy (fallback.py): Kennung des YouTube-Videos bzw. Spotify-Songs. Das Handy nennt die
    Anbieter, für die du *am Handy* eingewilligt hast (consent); ohne Angabe sucht der PC nichts."""
    dev_id = str(body.get("id") or "")[:32]
    d = _device(dev_id)
    key = _kdf(base64.b64decode(d["secret"]), "sync")
    try:
        req = unseal(key, f"fallback:{dev_id}", str(body.get("box") or ""))
    except ShareError:
        raise PhoneError("Anfrage ließ sich nicht prüfen – bitte neu koppeln", 403) from None
    rid = str(req.get("rid") or "")[:64]
    _replay_check(int(req.get("ts") or 0), rid)
    from . import fallback
    kinds = [k for k in (req.get("consent") or []) if k in fallback.KINDS]
    if not kinds:
        raise PhoneError("Ersatz-Player ist am Handy nicht erlaubt", 403)
    t = _track(req.get("track") or {})
    if t.title == "?":
        raise PhoneError("Song fehlt")
    known = {k: str((req.get("known") or {}).get(k) or "")[:22] for k in fallback.KINDS}
    res = fallback.resolve(t, known, kinds=kinds)
    return {"box": seal(key, f"fallback-ok:{dev_id}:{rid}", res, limit=None)}


def _items_out(items: list[dict]) -> list[dict]:
    keep = ("title", "artists", "album", "cover", "duration_ms", "isrc", "ids", "preview_url", "bpm", "camelot", "key", "energy",
            "genre", "subgenre")
    out = []
    for it in items:
        d = {k: it.get(k) for k in keep if it.get(k) not in (None, "", [], {})}
        if d.get("ids"):
            d["ids"] = {str(k): str(v) for k, v in d["ids"].items() if v is not None}
        for k in ("bpm", "energy"):
            if isinstance(d.get(k), float):
                d[k] = round(d[k], 2)
        out.append(d)
    return out


def _job_status(kind: str, jid: str) -> dict:
    from . import mixgen, setplan
    if kind == "mix":
        j = mixgen.job(jid)
        out = {"state": j["state"], "phase": j.get("phase"), "done": j.get("done", 0), "total": j.get("total", 0),
               "note": j.get("note") or "", "error": j.get("error")}
        if j["state"] == "done":
            out.update(items=_items_out(j["items"]), order=j.get("order") or [], reserve=j.get("reserve") or [])
        return out
    j = setplan.job(jid)
    out = {"state": j["state"], "done": j.get("done", 0), "total": j.get("total", 0), "error": j.get("error"),
           "cut": j.get("cut", 0)}
    if j["state"] == "done":
        curve = j.get("curve") or "peak"
        idx = setplan.order(j["items"], curve)
        d = setplan.describe(j["items"], idx, curve)
        out.update(items=_items_out(j["items"]), order=idx, harmonisch=d["harmonisch"], bekannt=d["bekannt"],
                   minuten=d["minuten"], curve=curve)
    return out


def handle_job(body: dict, client: str | None = None) -> dict:
    """Mix erstellen und Set-Planer vom Handy aus – der PC rechnet (Tempo/Tonart aus Hörproben, Künstler-/Genre-Suche)
    wie bei sich selbst; das Handy fragt den Stand ab und kann das Ergebnis als PC-Playlist speichern.
    Gleiche Verschlüsselung wie der Abgleich; jede Anfrage einmalig (rid)."""
    from . import mixgen, ratelimit, setplan
    dev_id = str(body.get("id") or "")[:32]
    d = _device(dev_id)
    key = _kdf(base64.b64decode(d["secret"]), "sync")
    try:
        req = unseal(key, f"job:{dev_id}", str(body.get("box") or ""))
    except ShareError:
        raise PhoneError("Anfrage ließ sich nicht prüfen – bitte neu koppeln", 403) from None
    rid = str(req.get("rid") or "")[:64]
    _replay_check(int(req.get("ts") or 0), rid)
    act = str(req.get("act") or "")
    kind = "mix" if req.get("kind") == "mix" else "set"
    jid = str(req.get("job") or "")[:20]
    try:
        if act == "artists":
            out = {"artists": [{"id": a["id"], "name": a["name"], "fans": a["fans"]}
                               for a in mixgen.search_artists(str(req.get("q") or ""), 8)]}
        elif act == "genres":
            from .genres.taxonomy import TAXONOMY
            out = {"genres": [{"genre": g, "subs": [s for s in subs if s != "_"]} for g, subs in TAXONOMY.items()],
                   "levels": [{"id": k, "name": v["name"], "hint": v["hint"]} for k, v in mixgen.LEVELS.items()],
                   "curves": [{"id": k, "name": v[0], "hint": v[1]} for k, v in setplan.CURVES.items()]}
        elif act == "mix-start":
            opts = req.get("opts") if isinstance(req.get("opts"), dict) else {}
            out = {"job": mixgen.start(req.get("seeds") if isinstance(req.get("seeds"), list) else None, opts,
                                       req.get("genre") if isinstance(req.get("genre"), dict) else None)}
        elif act == "set-start":
            jid = setplan.start(str(req.get("playlist") or "")[:200])
            curve = req.get("curve") if req.get("curve") in setplan.CURVES else "peak"
            setplan.job(jid)["curve"] = curve
            out = {"job": jid}
        elif act == "status":
            out = _job_status(kind, jid)
        elif act == "cancel":
            (mixgen.job(jid) if kind == "mix" else setplan.job(jid))["cancel"] = True
            out = {"ok": True}
        elif act == "save":
            idx = [int(i) for i in (req.get("idx") or []) if isinstance(i, int)]
            name = str(req.get("name") or "")
            out = mixgen.save(jid, idx, name) if kind == "mix" else setplan.save(jid, idx, name)
        else:
            raise PhoneError("Unbekannte Anfrage")
    except ratelimit.LimitReached as e:
        raise PhoneError(f"{e} – bitte gleich nochmal versuchen", 429) from None
    except ValueError as e:
        raise PhoneError(str(e)) from None
    return {"box": seal(key, f"job-ok:{dev_id}:{rid}", out, limit=None)}


# ------------------------------------------------------------------ Abgleich: Daten übernehmen und zurückgeben
_TRACK_FIELDS = {f for f in Track.__dataclass_fields__}


def _track(d: dict) -> Track:
    t = {k: v for k, v in (d or {}).items() if k in _TRACK_FIELDS}
    t["title"] = str(t.get("title") or "?")[:300]
    t["artists"] = [str(a)[:200] for a in (t.get("artists") or [])][:20]
    return Track(**t)


def _slim(t: dict) -> dict:
    """Für das Handy reicht das Nötige – Tags u. Ä. bleiben am PC."""
    if t.get("ids"):
        t = {**t, "ids": {str(k): str(v) for k, v in t["ids"].items() if v is not None}}
    return {k: v for k, v in t.items() if k in ("title", "artists", "album", "duration_ms", "isrc", "ids", "genre",
                                                 "subgenre", "niche", "cover", "preview_url") and v not in (None, "", [], {})}


def _rec_out(r: dict) -> dict:
    return {"uid": r["uid"], "ts": r["ts"], "host": r["host"], "source": r["source"], "engine": r["engine"],
            "track": _slim(r["track"]), "extra": {k: v for k, v in (r["extra"] or {}).items()
                                                  if k in ("links", "label", "year", "bpm", "engines", "agreement", "genre_source",
                                                           "shazam_genre", "unsure", "confirmed", "version")}}


def apply(req: dict, device_name: str) -> dict:
    host = f"Handy · {device_name}"[:80]
    new = []
    for r in (req.get("recs") or [])[:1000]:
        uid = str(r.get("uid") or "")[:80]
        if not uid.startswith("android-"):
            continue
        t = _track(r.get("track") or {})
        extra = {k: v for k, v in (r.get("extra") or {}).items() if isinstance(k, str)}
        extra["handy"] = True
        if store.import_recognition(uid, float(r.get("ts") or time.time()), host, str(r.get("source") or "handy")[:40],
                                    str(r.get("engine") or "shazam")[:20], int(extra.get("agreement") or 1), t, extra):
            new.append(uid)
        else:
            store.update_recognition_extra_by_uid(uid, extra)
    shz = any(str(r.get("source")) == "shazam-app" for r in (req.get("recs") or [])[:1000])
    for uid in (req.get("deleted") or [])[:1000]:
        if str(uid).startswith("android-"):
            store.delete_recognition_uid(str(uid))
            shz = shz or str(uid).startswith("android-shz-")
    if shz:                                          # Shazams aus der Shazam-App -> Playlists unter „Shazam“
        from . import dataexport
        try:
            dataexport.refresh_phone_shazams()
        except Exception as e:  # noqa: BLE001 – Abgleich soll daran nicht scheitern
            dbg.error("handy", "Shazam-Playlists vom Handy", e)
    for op in (req.get("ops") or [])[:1000]:
        name = str(op.get("playlist") or "").strip()[:120]
        if not name:
            continue
        t = _track(op.get("track") or {})
        if op.get("op") == "add":
            store.add_to_playlist(name, t)
        elif op.get("op") == "remove":
            store.remove_from_playlist(name, store.track_key(t))
    if new:
        _enrich_later(new)

    cursor = float(req.get("cursor") or 0)
    recs = store.recognitions_since(cursor, RECS_PER_SYNC, exclude_prefix="android-")
    updates = [_rec_out(r) for r in store.recognitions_by_uid([str(u) for u in (req.get("need_info") or [])[:300]])
               if r["track"].get("genre")]
    # Welche Playlists das Handy haben will (None = alle). Die Übersicht (Name + Anzahl) geht immer mit – zum Auswählen.
    want = req.get("lists")
    want = {str(x)[:120] for x in want[:2000]} if isinstance(want, list) else None
    lists, catalog, n = [], [], 0
    for name in store.playlist_names():
        entries = store.playlist_entries(name)
        catalog.append({"name": name, "n": len(entries)})
        if want is not None and name not in want:
            continue
        tracks = [_slim(e["track"]) for e in entries][:max(0, MAX_PLAYLIST_TRACKS - n)]
        n += len(tracks)
        lists.append({"name": name, "tracks": tracks, "updated": 0.0})
    return {"cursor": recs[-1]["ts"] if recs else cursor, "recs": [_rec_out(r) for r in recs], "updates": updates,
            "playlists": lists, "catalog": catalog, "pc_name": _pc_name(), "addrs": addresses(),
            "more": len(recs) >= RECS_PER_SYNC}


def _enrich_later(uids: list[str]) -> None:
    """Genre, BPM, Links usw. wie bei einer Erkennung am PC nachschlagen – im Hintergrund, die Antwort wartet nicht."""
    def run():
        from .enrich import enrich
        from .recognize.engines import Recognition
        for uid in uids:
            r = next(iter(store.recognitions_by_uid([uid])), None)
            if not r:
                continue
            t, x = r["track"], r["extra"] or {}
            try:
                rec = Recognition(engine="shazam", title=t["title"], artists=t.get("artists") or [], album=t.get("album"),
                                  isrc=t.get("isrc"), cover=t.get("cover"), preview_url=t.get("preview_url"),
                                  links=x.get("links") or {}, label=x.get("label"), year=x.get("year"),
                                  genres=[x["shazam_genre"]] if x.get("shazam_genre") else [])
                track, extra = enrich(rec)
                store.update_recognition(r["id"], asdict(track), {**x, **extra, "engines": x.get("engines") or ["shazam"]})
            except Exception as e:  # noqa: BLE001 – offline o. Ä.: bleibt wie vom Handy geliefert
                dbg.error("handy", "Song vom Handy nicht angereichert", e, song=t.get("title"))
    threading.Thread(target=run, name="handy-anreichern", daemon=True).start()


# ------------------------------------------------------------------ Abgleich übers Internet (Relais)
# Für unterwegs: Handy und PC tauschen den Abgleich über zwei verschlüsselte Ablagen auf shtunebridge.bs002.de aus
# (dieselben Teilen-Räume wie bei „Playlists teilen“). Raum-IDs, Schreib-Token und Schlüssel leiten beide aus dem
# Geräte-Geheimnis der Kopplung ab – der Server sieht nur zufällige Kennungen und unlesbare Blöcke.
# Nur mit Einwilligung „relay“ am PC und je Handy eingeschaltet (am Handy zusätzlich je PC).
RELAY_MAX_AGE = 7 * 86400        # ältere Anfragen werden verworfen (Handy schickt dann eine neue)
RELAY_LIMIT = 190 * 1024         # Server nimmt höchstens 200 KB je Block
RELAY_TRACKS = 1500              # Playlists übers Internet nur bis zu so vielen Songs (sonst bleiben die alten)
RELAY_EVERY = 360                # so oft schaut der PC nach (Server erlaubt ohne Konto nur wenige Anfragen pro Stunde)
_relay_err: dict = {"t": 0.0}
_relay_next: dict = {"t": 0.0}


class _RelayConflict(Exception):
    def __init__(self, rev: int):
        super().__init__("conflict")
        self.rev = rev


def _relay_keys(d: dict, direction: str) -> dict:
    """direction: "to-pc" (Handy schreibt, PC liest) oder "to-phone" (PC schreibt, Handy liest)."""
    from .share import derive
    return derive(_kdf(base64.b64decode(d["secret"]), f"relay-{direction}"))


def _relay_http(method: str, k: dict, body: dict | None = None):
    import httpx

    from . import upload
    from .share import _tok
    if not consent.server("relay"):
        raise PhoneError("Abgleich übers Internet ist nicht erlaubt (Einstellungen › Datenschutz)", 403)
    path = f"/v1/share/{k['space']}" + ("/private" if method == "GET" else "")
    try:
        return httpx.request(method, upload.URL + path, json=body, timeout=20,
                             headers={"User-Agent": "SH-Tunebridge-Relay", "X-Share-Token": _tok(k["token"])})
    except httpx.HTTPError as e:
        raise PhoneError(f"Server nicht erreichbar: {e}", 502) from e


def _relay_get(k: dict) -> tuple[dict | None, int]:
    r = _relay_http("GET", k)
    if r.status_code == 404:
        return None, 0
    _limited(r)
    if r.status_code != 200:
        raise PhoneError(f"Server-Ablage: Fehler {r.status_code}", 502)
    j = r.json()
    return unseal(k["kpriv"], k["space"] + "/private", j["blob"]), int(j["rev"])


def _relay_put(k: dict, rev: int, doc: dict) -> int:
    r = _relay_http("PUT", k, {"rev": rev, "priv": seal(k["kpriv"], k["space"] + "/private", doc, limit=RELAY_LIMIT)})
    if r.status_code == 409:
        raise _RelayConflict(int(r.json().get("rev") or 0))
    _limited(r)
    if r.status_code != 200:
        raise PhoneError(f"Server-Ablage: Fehler {r.status_code}", 502)
    return int(r.json()["rev"])


def _limited(r) -> None:
    """Server sagt „zu viele Anfragen“: so lange gar nicht mehr nachsehen, wie er verlangt (mindestens 10 Minuten)."""
    if r.status_code == 429:
        try:
            wait = int(r.headers.get("Retry-After") or 3600)
        except ValueError:
            wait = 3600
        _relay_next["t"] = time.time() + max(600, min(wait, 6 * 3600))
        raise PhoneError("Server: gerade zu viele Anfragen – Abgleich übers Internet macht kurz Pause", 429)


def _relay_delete(d: dict) -> None:
    """Beim Entfernen des Handys oder Ausschalten: beide Ablagen auf dem Server löschen (wenn erlaubt)."""
    for direction in ("to-pc", "to-phone"):
        try:
            _relay_http("DELETE", _relay_keys(d, direction))
        except PhoneError:
            pass


def _fit(answer: dict, key: dict) -> dict:
    """Antwort so kürzen, dass sie in einen Server-Block passt: erst Playlists weglassen, dann weniger Erkennungen."""
    def ok(a: dict) -> bool:
        try:
            seal(key["kpriv"], "x", {"ans": a}, limit=RELAY_LIMIT - 512)
            return True
        except ShareError:
            return False
    a = dict(answer)
    if a.get("playlists") is not None and sum(len(p["tracks"]) for p in a["playlists"]) > RELAY_TRACKS:
        a["playlists"] = None
    if not ok(a):
        a["playlists"] = None
    while not ok(a) and (a["recs"] or a["updates"]):
        if a["updates"]:
            a["updates"] = a["updates"][: len(a["updates"]) // 2]
            continue
        a["recs"] = a["recs"][: len(a["recs"]) // 2]
        a["more"] = True
        if a["recs"]:
            a["cursor"] = a["recs"][-1]["ts"]
    if not ok(a):
        a["catalog"] = []
    return a


def _relay_one(dev_id: str, d: dict) -> bool:
    """Eine wartende Anfrage dieses Handys abholen, abgleichen und die Antwort ablegen. True = etwas getan."""
    a = _relay_keys(d, "to-pc")
    doc, rev = _relay_get(a)
    req = (doc or {}).get("req")
    if not isinstance(req, dict):
        return False
    rid, ts = str(req.get("rid") or "")[:64], int(req.get("ts") or 0)
    stale = ts <= int(d.get("relay_ts") or 0) or time.time() - ts / 1000 > RELAY_MAX_AGE or ts / 1000 > time.time() + MAX_SKEW
    if not stale:
        st = _load()                             # erst merken, dann anwenden – eine Anfrage wird nie doppelt übernommen
        if dev_id not in st["devices"]:
            return False
        st["devices"][dev_id]["relay_ts"] = ts
        _save(st)
        answer = _fit(apply(req, d.get("name") or "Handy"), a)
        _touch(dev_id, req, answer, None, via="internet")
        b = _relay_keys(d, "to-phone")
        brev = int(d.get("relay_rev") or 0)
        for _ in range(3):
            try:
                brev = _relay_put(b, brev, {"rid": rid, "ans": answer})
                break
            except _RelayConflict as e:
                brev = e.rev
        st = _load()
        if dev_id in st["devices"]:
            st["devices"][dev_id]["relay_rev"] = brev
            _save(st)
        dbg.event("handy", "Abgleich übers Internet", name=d.get("name"), empfangen=len(req.get("recs") or []),
                  gesendet=len(answer["recs"]))
    try:
        _relay_put(a, rev, {"done": rid})        # Ablage leeren; hat das Handy inzwischen neu geschrieben, bleibt das stehen
    except _RelayConflict:
        pass
    return not stale


def relay_poll(force: bool = False) -> int:
    """Alle Handys mit eingeschaltetem Internet-Abgleich prüfen (der Wächter ruft alle 30 s auf, nachgesehen wird
    höchstens alle RELAY_EVERY Sekunden – und nach „zu viele Anfragen“ erst, wenn der Server es wieder erlaubt)."""
    if not consent.server("relay"):
        return 0
    now = time.time()
    if not force and now < _relay_next["t"]:
        return 0
    if not any(d.get("relay") for d in _load()["devices"].values()):
        return 0
    _relay_next["t"] = max(_relay_next["t"], now + RELAY_EVERY)
    n = 0
    for dev_id, d in list(_load()["devices"].items()):
        if not d.get("relay"):
            continue
        try:
            n += _relay_one(dev_id, d)
        except (PhoneError, ShareError) as e:
            if time.time() - _relay_err["t"] > 3600:      # Server weg: höchstens einmal pro Stunde ins Protokoll
                _relay_err["t"] = time.time()
                dbg.event("handy", "Abgleich übers Internet gerade nicht möglich", fehler=str(e)[:200])
    return n


def set_relay(dev_id: str, on: bool) -> dict:
    """Internet-Abgleich für ein Handy ein-/ausschalten. Ausschalten löscht beide Ablagen auf dem Server."""
    st = _load()
    d = st["devices"].get(dev_id)
    if not d:
        raise PhoneError("Dieses Handy ist nicht gekoppelt", 404)
    if on and not consent.server("relay"):
        raise PhoneError("Bitte erst unter Einstellungen › Datenschutz „Handy-Abgleich übers Internet“ erlauben", 403)
    if not on and d.get("relay") and consent.server("relay"):
        _relay_delete(d)
    d["relay"] = bool(on)
    d.pop("relay_rev", None)
    _save(st)
    return status()


# ------------------------------------------------------------------ Kleiner Server nur fürs Handy
def _client(request: Request) -> str | None:
    return request.client.host if request.client else None


def _make_app():
    api = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    async def body_of(request: Request) -> dict:
        if not _allowed(_client(request)):
            raise PhoneError("Nur aus den freigegebenen Netzen", 403)
        data = bytearray()
        async for chunk in request.stream():
            data += chunk
            if len(data) > MAX_BODY:
                raise PhoneError("Zu groß", 413)
        try:
            return json.loads(data)
        except ValueError:
            raise PhoneError("Ungültige Anfrage") from None

    @api.exception_handler(PhoneError)
    async def _err(_request, e: PhoneError):
        return JSONResponse({"detail": str(e)}, status_code=e.status)

    @api.post("/phone/v1/pair")
    async def pair(request: Request):
        import asyncio
        return await asyncio.to_thread(handle_pair, await body_of(request), _client(request))

    @api.post("/phone/v1/sync")
    async def sync(request: Request):
        import asyncio
        return await asyncio.to_thread(handle_sync, await body_of(request), _client(request))

    @api.post("/phone/v1/similar")
    async def similar_songs(request: Request):
        import asyncio
        return await asyncio.to_thread(handle_similar, await body_of(request), _client(request))

    @api.post("/phone/v1/fallback")
    async def fallback_player(request: Request):
        import asyncio
        return await asyncio.to_thread(handle_fallback, await body_of(request), _client(request))

    @api.post("/phone/v1/versions")
    async def versions_songs(request: Request):
        import asyncio
        return await asyncio.to_thread(handle_versions, await body_of(request), _client(request))

    @api.post("/phone/v1/discover")
    async def discover_songs(request: Request):
        import asyncio
        return await asyncio.to_thread(handle_discover, await body_of(request), _client(request))

    @api.post("/phone/v1/job")
    async def job(request: Request):
        import asyncio
        return await asyncio.to_thread(handle_job, await body_of(request), _client(request))

    @api.get("/phone/v1/hello")
    async def hello(request: Request):
        if not _allowed(_client(request)):
            raise PhoneError("Nur aus den freigegebenen Netzen", 403)
        return {"app": "SH-Tunebridge", "v": 1}
    return api


def _wanted() -> bool:
    st = _load()
    if not st["enabled"]:
        return False
    with _lock:
        if _pairing and _pairing["expires"] > time.time():
            return True
    return bool(st["devices"])


def _stop() -> None:
    srv, t = _server.get("server"), _server.get("thread")
    if srv and t and t.is_alive():
        srv.should_exit = True
        t.join(5)
    _server.clear()


def ensure_server(force: bool = False) -> None:
    """Server starten, wenn er gebraucht wird – nur auf den Adressen in den gewählten Netzen – und beenden,
    wenn nicht. Ändern sich Netze oder Auswahl, wird neu gebunden."""
    with _lock:
        alive = bool(_server.get("thread") and _server["thread"].is_alive())
        want = (force and _load()["enabled"]) or _wanted()
        ips = sorted({n["ip"] for n in effective()}) if want else []
        if alive and (not want or ips != _server.get("want")):
            _stop()
            dbg.event("handy", "Handy-Zugang geschlossen" if not want else "Handy-Zugang: Netze geändert")
            alive = False
        if want and ips and not alive:
            import uvicorn
            socks, bound = [], []
            for ip in ips:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                try:
                    s.bind((ip, PORT))
                except OSError as e:
                    s.close()
                    dbg.error("handy", "Adresse ließ sich nicht öffnen", e, adresse=f"{ip}:{PORT}")
                    continue
                socks.append(s)
                bound.append(ip)
            if not socks:
                return
            server = uvicorn.Server(uvicorn.Config(_make_app(), log_level="warning", access_log=False, lifespan="off"))
            t = threading.Thread(target=server.run, kwargs={"sockets": socks}, name="handy-server", daemon=True)
            t.start()
            _server.update(thread=t, server=server, ips=bound, want=ips)
            dbg.event("handy", "Handy-Zugang geöffnet", adressen=", ".join(f"{ip}:{PORT}" for ip in bound))


def watchdog() -> None:
    """Abgelaufene Kopplungs-Codes aufräumen und den Server passend an/aus schalten (läuft alle 30 s)."""
    global _pairing
    with _lock:
        if _pairing and _pairing["expires"] < time.time():
            old, _pairing = _pairing, None
            _reject_waiting(old)
    try:
        networks(fresh=True)
        ensure_server()
    except Exception as e:  # noqa: BLE001 – z. B. Port belegt: Oberfläche zeigt „läuft nicht“
        dbg.error("handy", "Handy-Zugang ließ sich nicht starten", e, port=PORT)
    try:
        relay_poll()
    except Exception as e:  # noqa: BLE001 – Server weg o. Ä.: beim nächsten Mal wieder
        dbg.error("handy", "Abgleich übers Internet", e)

"""Daten an den Entwickler senden – nur mit Einwilligung (consent.py): auf Klick mit Vorschau oder automatisch (outbox.py).

* Ziel: https://shtunebridge.bs002.de (Betreiber: der Entwickler von SH-Tunebridge).
* Gesendet wird genau das, was die Vorschau zeigt (siehe web/app.py::_miss_export) –
  kein Ton, kein Rechner- oder Gerätename, kein Konto.
* Jede Installation erzeugt beim ersten Senden ein eigenes Schlüsselpaar (P-256) und
  unterschreibt damit jede Anfrage. Der Server kennt dich nur als Hash dieses Schlüssels –
  und nur damit kannst du deine Einträge dort jederzeit wieder löschen.
* Auf dem Server werden die Einträge sofort verschlüsselt; lesen kann sie nur der
  Entwickler auf seinem eigenen Rechner. Aufbewahrung: 12 Monate. Die Annahme-Software speichert keine IP-Adressen;
  Firewall und Proxy davor protokollieren sie (Abwehr von DDoS, Hacking, Bots, Spam) – siehe DATENSCHUTZ.md.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import time

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

from . import config
from . import debuglog as dbg

URL = os.environ.get("TUNEBRIDGE_UPLOAD_URL", "https://shtunebridge.bs002.de").rstrip("/")
KEY_FILE = config.DATA / "upload-identity.pem"


class UploadError(RuntimeError):
    pass


def _key() -> ec.EllipticCurvePrivateKey:
    if KEY_FILE.exists():
        return serialization.load_pem_private_key(KEY_FILE.read_bytes(), None)
    k = ec.generate_private_key(ec.SECP256R1())
    KEY_FILE.write_bytes(k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                         serialization.NoEncryption()))
    os.chmod(KEY_FILE, 0o600)
    return k


def _pub(k) -> bytes:
    return k.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)


def identity() -> str | None:
    """Kurzkennung dieser Installation beim Server (oder None, wenn noch nie gesendet)."""
    if not KEY_FILE.exists():
        return None
    return hashlib.sha256(_pub(_key())).hexdigest()[:8]


def canonical(method: str, path: str, ts: str, nonce: str, body: bytes) -> bytes:
    return f"SHTB1\n{method.upper()}\n{path}\n{ts}\n{nonce}\n{hashlib.sha256(body).hexdigest()}".encode()


def _signed_post(path: str, payload: dict, timeout: float = 20) -> dict:
    k = _key()
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
    ts, nonce = str(int(time.time())), secrets.token_urlsafe(18)
    r, s = decode_dss_signature(k.sign(canonical("POST", path, ts, nonce, body), ec.ECDSA(hashes.SHA256())))
    sig = r.to_bytes(32, "big") + s.to_bytes(32, "big")
    headers = {"Content-Type": "application/json", "X-TB-Key": base64.b64encode(_pub(k)).decode(),
               "X-TB-Time": ts, "X-TB-Nonce": nonce, "X-TB-Sig": base64.b64encode(sig).decode(),
               "User-Agent": "SH-Tunebridge"}
    try:
        resp = httpx.post(URL + path, content=body, headers=headers, timeout=timeout)
    except httpx.HTTPError as e:
        dbg.error("senden", "Server nicht erreichbar", e)
        raise UploadError(f"Server nicht erreichbar: {e}") from e
    try:
        data = resp.json()
    except ValueError:
        data = {}
    if resp.status_code >= 400:
        msg = data.get("error") or f"HTTP {resp.status_code}"
        dbg.problem("senden", f"Server lehnt ab: {msg}", status=resp.status_code)
        raise UploadError(msg)
    return data


def send(export: dict) -> dict:
    """export = Ergebnis von _miss_export (genau das, was die Vorschau zeigt). In Paketen à 200."""
    items = export["eintraege"]
    total = {"angenommen": 0, "schon_da": 0}
    for i in range(0, len(items), 200):
        part = {**export, "eintraege": items[i:i + 200]}
        r = _signed_post("/v1/misses", part)
        total["angenommen"] += r.get("angenommen", 0)
        total["schon_da"] += r.get("schon_da", 0)
        total["aufbewahrung_tage"] = r.get("aufbewahrung_tage")
    dbg.event("senden", "Nicht-erkannt-Einträge gesendet", **total)
    return total


def status() -> dict:
    if not KEY_FILE.exists():
        return {"gespeichert": 0}
    return _signed_post("/v1/misses/status", {})


def delete_all() -> dict:
    """Alle Einträge dieser Installation beim Entwickler löschen."""
    if not KEY_FILE.exists():
        return {"geloescht": 0}
    r = _signed_post("/v1/misses/delete", {"alle": True})
    dbg.event("senden", "Eigene Einträge auf dem Server gelöscht", **r)
    return r

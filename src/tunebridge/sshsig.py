"""SSH-Signaturen prüfen (Format „SSHSIG“, wie `ssh-keygen -Y verify`) – in reinem Python.

Grund: Unter Windows hängt das mitgelieferte ssh-keygen bei ungültigen Signaturen, und nicht jeder Rechner hat es.
Unterstützt Ed25519 (unser Release-Schlüssel). Spezifikation: OpenSSH PROTOCOL.sshsig, ALLOWED SIGNERS in ssh-keygen(1).
"""

from __future__ import annotations

import base64
import fnmatch
import hashlib
import re
import struct

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


class SigError(Exception):
    pass


def _read_string(buf: bytes, pos: int) -> tuple[bytes, int]:
    if pos + 4 > len(buf):
        raise SigError("Signatur abgeschnitten")
    (n,) = struct.unpack(">I", buf[pos:pos + 4])
    pos += 4
    if pos + n > len(buf):
        raise SigError("Signatur abgeschnitten")
    return buf[pos:pos + n], pos + n


def _string(b: bytes) -> bytes:
    return struct.pack(">I", len(b)) + b


def _unarmor(sig: bytes) -> bytes:
    text = sig.decode("ascii", "replace")
    m = re.search(r"-----BEGIN SSH SIGNATURE-----(.*?)-----END SSH SIGNATURE-----", text, re.S)
    if not m:
        raise SigError("Keine SSH-Signatur")
    try:
        return base64.b64decode("".join(m.group(1).split()), validate=True)
    except ValueError as e:
        raise SigError("Signatur nicht lesbar") from e


def _allowed(signers_text: str, identity: str, namespace: str) -> list[bytes]:
    """Öffentliche Schlüssel (SSH-Wire-Format), die für identity + namespace zugelassen sind."""
    keys = []
    for line in signers_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r'(\S+)\s+(?:((?:[\w-]+(?:="[^"]*")?,?)+)\s+)?(ssh-ed25519)\s+(\S+)', line)
        if not m:
            continue
        principals, opts, _ktype, b64 = m.groups()
        if not any(fnmatch.fnmatchcase(identity, p) for p in principals.split(",")):
            continue
        ns = re.search(r'namespaces="([^"]*)"', opts or "")
        if ns and not any(fnmatch.fnmatchcase(namespace, n.strip()) for n in ns.group(1).split(",")):
            continue
        if opts and re.search(r"(^|,)cert-authority(,|$)", opts):
            continue  # Zertifikate werden hier nicht unterstützt
        try:
            keys.append(base64.b64decode(b64, validate=True))
        except ValueError:
            continue
    return keys


def verify(message: bytes, signature: bytes, signers_text: str, identity: str, namespace: str) -> None:
    """Wirft SigError, wenn die Signatur nicht gültig von einem zugelassenen Schlüssel stammt."""
    blob = _unarmor(signature)
    if blob[:6] != b"SSHSIG":
        raise SigError("Kein SSHSIG-Format")
    pos = 6
    if struct.unpack(">I", blob[pos:pos + 4])[0] != 1:
        raise SigError("Unbekannte Signatur-Version")
    pos += 4
    pubkey, pos = _read_string(blob, pos)
    ns, pos = _read_string(blob, pos)
    reserved, pos = _read_string(blob, pos)
    hash_alg, pos = _read_string(blob, pos)
    sig, pos = _read_string(blob, pos)
    if ns.decode() != namespace:
        raise SigError("Falscher Namensraum")
    if hash_alg not in (b"sha512", b"sha256"):
        raise SigError("Unbekanntes Hash-Verfahren")
    if pubkey not in _allowed(signers_text, identity, namespace):
        raise SigError("Schlüssel nicht zugelassen")
    ktype, kp = _read_string(pubkey, 0)
    raw_key, _ = _read_string(pubkey, kp)
    stype, sp = _read_string(sig, 0)
    raw_sig, _ = _read_string(sig, sp)
    if ktype != b"ssh-ed25519" or stype != b"ssh-ed25519" or len(raw_key) != 32 or len(raw_sig) != 64:
        raise SigError("Nur Ed25519 wird unterstützt")
    digest = (hashlib.sha512 if hash_alg == b"sha512" else hashlib.sha256)(message).digest()
    signed = b"SSHSIG" + _string(ns) + _string(reserved) + _string(hash_alg) + _string(digest)
    try:
        Ed25519PublicKey.from_public_bytes(raw_key).verify(raw_sig, signed)
    except InvalidSignature as e:
        raise SigError("Signatur ungültig") from e

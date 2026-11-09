"""Playlists teilen – mit zwei Schlüsseln, Ende-zu-Ende verschlüsselt.

* **Privater Schlüssel** (SHT-P-…): lesen und schreiben. Nur für dich selbst (z. B. zweiter Rechner) oder Menschen,
  die mit dir zusammen pflegen sollen. Wie ein Passwort behandeln.
* **Öffentlicher Schlüssel** (SHT-O-…): nur lesen – und nur die Playlists, die du als „öffentlich“ markierst.
  Den gibst du Freunden.

Alles wird in der App verschlüsselt (AES-256-GCM, Schlüssel per HKDF aus dem privaten Schlüssel abgeleitet).
Der Server (shtunebridge.bs002.de) sieht nur zufällige Raum-ID, Hash des Schreib-Tokens, Chiffrate und Datum –
keine Playlist-Namen, keine Songs, keine Personen. Geteilt werden nur Metadaten (Titel, Künstler, Album, ISRC,
Dienst-IDs) – nie Musik, Cover-Dateien oder Hörproben. Nur mit Einwilligung „share“ (Einstellungen › Datenschutz).
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import time
import zlib

import httpx
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from . import config, consent, store
from .models import Track

PRIV, PUB = "SHT-P-", "SHT-O-"
MAX_PLAYLISTS = 200
MAX_TRACKS = 2000
MAX_BLOB = 200 * 1024
MAX_FRIENDS = 100
_FILE = lambda: config.DATA / "tokens" / "share.json"  # noqa: E731


class ShareError(RuntimeError):
    pass


# ------------------------------------------------------------------ Schlüssel
def _kdf(root: bytes, info: str, n: int = 32) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=n, salt=b"sh-tunebridge-share-v1", info=info.encode()).derive(root)


def derive(root: bytes) -> dict:
    return {"space": _kdf(root, "space", 16).hex(), "token": _kdf(root, "write"),
            "kpriv": _kdf(root, "private"), "kpub": _kdf(root, "public")}


def _b32(b: bytes) -> str:
    s = base64.b32encode(b + hashlib.sha256(b).digest()[:2]).decode().rstrip("=")
    return "-".join(s[i:i + 5] for i in range(0, len(s), 5))


def _unb32(s: str, n: int) -> bytes:
    s = "".join(ch for ch in s.upper() if ch.isalnum())
    try:
        raw = base64.b32decode(s + "=" * (-len(s) % 8))
    except ValueError as e:
        raise ShareError("Der Schlüssel ist ungültig (Tippfehler?)") from e
    body, chk = raw[:-2], raw[-2:]
    if len(body) != n or hashlib.sha256(body).digest()[:2] != chk:
        raise ShareError("Der Schlüssel ist ungültig (Tippfehler oder unvollständig kopiert?)")
    return body


def private_key(root: bytes) -> str:
    return PRIV + _b32(root)


def public_key(root: bytes) -> str:
    d = derive(root)
    return PUB + _b32(bytes.fromhex(d["space"]) + d["kpub"])


def parse_key(key: str) -> dict:
    # tolerant: Leerzeichen, Zeilenumbrüche, Bindestriche, Groß-/Kleinschreibung beim Einfügen egal
    flat = "".join(ch for ch in (key or "").upper() if ch.isalnum())
    if flat.startswith("SHTP"):
        root = _unb32(flat[4:], 32)
        return {"kind": "private", "root": root, **derive(root)}
    if flat.startswith("SHTO"):
        raw = _unb32(flat[4:], 48)
        return {"kind": "public", "space": raw[:16].hex(), "kpub": raw[16:]}
    raise ShareError("Das ist kein SH-Tunebridge-Schlüssel (beginnt mit SHT-P- oder SHT-O-)")


# ------------------------------------------------------------------ Verschlüsseln
def seal(key: bytes, aad: str, obj: dict, limit: int | None = MAX_BLOB) -> str:
    data = zlib.compress(json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode(), 9)
    nonce = os.urandom(12)
    blob = nonce + AESGCM(key).encrypt(nonce, data, aad.encode())
    if limit and len(blob) > limit:
        raise ShareError("Zu viele Songs zum Teilen (max. etwa 200 KB verschlüsselt) – bitte weniger Playlists")
    return base64.b64encode(blob).decode()


def unseal(key: bytes, aad: str, b64: str) -> dict:
    try:
        blob = base64.b64decode(b64)
        data = AESGCM(key).decrypt(blob[:12], blob[12:], aad.encode())
        z = zlib.decompressobj()
        raw = z.decompress(data, 8 << 20)          # höchstens 8 MB entpackt (Schutz vor „Zip-Bomben“)
        if z.unconsumed_tail:
            raise ValueError("zu groß")
        return json.loads(raw)
    except Exception as e:  # noqa: BLE001 – falscher Schlüssel oder beschädigt
        raise ShareError("Konnte nicht entschlüsselt werden – Schlüssel passt nicht") from e


# ------------------------------------------------------------------ Lokaler Zustand (nur für dich lesbar)
def _load() -> dict:
    p = _FILE()
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except ValueError:
            pass
    return {"root": None, "name": "", "rev": 0, "playlists": [], "friends": []}


def _save(st: dict) -> None:
    p = _FILE()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(st, ensure_ascii=False), encoding="utf-8")
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    os.replace(tmp, p)


def _root(st: dict) -> bytes | None:
    return base64.b64decode(st["root"]) if st.get("root") else None


# ------------------------------------------------------------------ Server
def _url() -> str:
    from . import upload
    return upload.URL


def _need_consent() -> None:
    if not consent.server("share"):
        raise ShareError("Teilen ist noch nicht erlaubt – bitte unter Einstellungen › Datenschutz „Playlists teilen“ "
                         "einschalten (verschlüsselt, der Server kann nichts lesen).")


def _tok(token: bytes) -> str:
    return base64.urlsafe_b64encode(token).decode().rstrip("=")


def _http(method: str, path: str, token: bytes | None = None, body: dict | None = None) -> httpx.Response:
    _need_consent()
    headers = {"User-Agent": "SH-Tunebridge-Share"}
    if token:
        headers["X-Share-Token"] = _tok(token)
    try:
        return httpx.request(method, _url() + path, headers=headers, json=body, timeout=20)
    except httpx.HTTPError as e:
        raise ShareError(f"Server nicht erreichbar: {e}") from e


def _err(r: httpx.Response) -> str:
    try:
        return r.json().get("error") or r.reason_phrase
    except ValueError:
        return r.reason_phrase


# ------------------------------------------------------------------ Inhalt
def _tr(t: Track | dict) -> dict:
    """Nur Metadaten – keine Cover-Dateien, keine Hörproben, keine Musik."""
    if isinstance(t, dict):
        t = Track(title=t.get("title", ""), artists=t.get("artists") or [], album=t.get("album"), isrc=t.get("isrc"),
                  ids=t.get("ids") or {}, duration_ms=t.get("duration_ms"), genre=t.get("genre"), subgenre=t.get("subgenre"))
    d = {"title": t.title[:300], "artists": [a[:200] for a in t.artists[:10]]}
    for k in ("album", "isrc", "duration_ms", "genre", "subgenre"):
        v = getattr(t, k, None)
        if v:
            d[k] = v if not isinstance(v, str) else v[:200]
    ids = {k: str(v)[:100] for k, v in (t.ids or {}).items() if k in ("spotify", "deezer", "tidal", "apple", "youtube", "isrc")}
    if ids:
        d["ids"] = ids
    return d


def _doc(st: dict, public: bool) -> dict:
    lists = [p for p in st["playlists"] if p.get("public") or not public]
    return {"format": 1, "name": st.get("name", "")[:80], "updated": int(time.time()),
            "playlists": [{"id": p["id"], "name": p["name"], "tracks": p["tracks"],
                           **({} if public else {"public": bool(p.get("public")), "local": p.get("local")})}
                          for p in lists]}


def _push(st: dict) -> None:
    root = _root(st)
    d = derive(root)
    body = {"rev": st.get("rev", 0),
            "priv": seal(d["kpriv"], d["space"] + "/private", _doc(st, False)),
            "pub": seal(d["kpub"], d["space"] + "/public", _doc(st, True))}
    r = _http("PUT", f"/v1/share/{d['space']}", d["token"], body)
    if r.status_code == 409:
        raise _Conflict()
    if r.status_code != 200:
        raise ShareError(f"Hochladen fehlgeschlagen: {_err(r)}")
    st["rev"] = r.json()["rev"]
    _save(st)


class _Conflict(Exception):
    pass


def _pull(st: dict) -> dict:
    root = _root(st)
    d = derive(root)
    r = _http("GET", f"/v1/share/{d['space']}/private", d["token"])
    if r.status_code == 404:
        st["rev"] = 0
        return st
    if r.status_code != 200:
        raise ShareError(f"Laden fehlgeschlagen: {_err(r)}")
    j = r.json()
    doc = unseal(d["kpriv"], d["space"] + "/private", j["blob"])
    st.update(name=doc.get("name", ""), rev=j["rev"],
              playlists=[{"id": p["id"], "name": p["name"], "tracks": p["tracks"], "public": bool(p.get("public")),
                          "local": p.get("local")} for p in doc.get("playlists", [])][:MAX_PLAYLISTS])
    _save(st)
    return st


def _mutate(fn) -> dict:
    """Neuesten Stand holen, ändern, hochladen. Hat jemand anderes (z. B. dein zweiter Rechner) gerade geschrieben,
    wird einmal neu geladen und die Änderung erneut angewendet."""
    st = _load()
    if not _root(st):
        raise ShareError("Noch kein Teilen-Bereich angelegt")
    for _ in range(3):
        st = _pull(st)
        fn(st)
        try:
            _push(st)
            return status()
        except _Conflict:
            continue
    raise ShareError("Gerade gleichzeitig an anderer Stelle geändert – bitte erneut versuchen")


# ------------------------------------------------------------------ Öffentliche Funktionen (für die Web-App)
def status() -> dict:
    st = _load()
    root = _root(st)
    return {"active": bool(root), "allowed": consent.server("share"), "name": st.get("name", ""),
            "private_key": private_key(root) if root else None, "public_key": public_key(root) if root else None,
            "playlists": [{"id": p["id"], "name": p["name"], "count": len(p["tracks"]), "public": bool(p.get("public")),
                           "local": p.get("local")} for p in st["playlists"]],
            "friends": [{"id": f["id"], "nick": f.get("nick", ""), "name": f.get("name", ""), "added": f.get("added")}
                        for f in st.get("friends", [])]}


def create(name: str = "") -> dict:
    _need_consent()
    st = _load()
    if _root(st):
        raise ShareError("Es gibt schon einen Teilen-Bereich")
    st.update(root=base64.b64encode(secrets.token_bytes(32)).decode(), name=(name or "").strip()[:80], rev=0, playlists=[])
    _push(st)
    return status()


def join(key: str) -> dict:
    """Mit einem privaten Schlüssel verbinden (z. B. zweiter Rechner) – liest und schreibt dann denselben Bereich."""
    k = parse_key(key)
    if k["kind"] != "private":
        raise ShareError("Das ist ein öffentlicher Schlüssel – den bitte unter „Freunde“ hinzufügen")
    st = _load()
    st.update(root=base64.b64encode(k["root"]).decode(), rev=0, playlists=[])
    st = _pull(st)
    if st["rev"] == 0:
        raise ShareError("Zu diesem Schlüssel gibt es keinen Bereich auf dem Server (gelöscht?)")
    return status()


def leave() -> dict:
    """Nur auf diesem Rechner vergessen – der Bereich bleibt auf dem Server (wieder verbinden mit dem Schlüssel)."""
    st = _load()
    st.update(root=None, rev=0, playlists=[], name="")
    _save(st)
    return status()


def delete_space() -> dict:
    st = _load()
    root = _root(st)
    if root:
        d = derive(root)
        r = _http("DELETE", f"/v1/share/{d['space']}", d["token"])
        if r.status_code not in (200, 403, 404):
            raise ShareError(f"Löschen fehlgeschlagen: {_err(r)}")
    return leave()


def rename(name: str) -> dict:
    return _mutate(lambda st: st.update(name=(name or "").strip()[:80]))


def _local_tracks(name: str) -> list[dict]:
    for p in store.local_playlists():
        if p.name == name:
            return [_tr(t) for t in p.tracks[:MAX_TRACKS]]
    raise ShareError(f"Playlist „{name}“ nicht gefunden")


def add_local(names: list[str], public: bool = False) -> dict:
    lists = {n: _local_tracks(n) for n in names}

    def fn(st):
        for n, tracks in lists.items():
            cur = next((p for p in st["playlists"] if p.get("local") == n), None)
            if cur:
                cur["tracks"] = tracks
            else:
                if len(st["playlists"]) >= MAX_PLAYLISTS:
                    raise ShareError(f"Höchstens {MAX_PLAYLISTS} Playlists")
                st["playlists"].append({"id": secrets.token_hex(6), "name": n[:200], "tracks": tracks,
                                        "public": public, "local": n})
    return _mutate(fn)


def update_local() -> dict:
    """Alle verknüpften Playlists mit dem aktuellen Stand deiner lokalen Playlists hochladen."""
    have = {p.name: p for p in store.local_playlists()}

    def fn(st):
        for p in st["playlists"]:
            if p.get("local") in have:
                p["tracks"] = [_tr(t) for t in have[p["local"]].tracks[:MAX_TRACKS]]
    return _mutate(fn)


def set_public(pid: str, public: bool) -> dict:
    def fn(st):
        for p in st["playlists"]:
            if p["id"] == pid:
                p["public"] = bool(public)
    return _mutate(fn)


def remove(pid: str) -> dict:
    return _mutate(lambda st: st.update(playlists=[p for p in st["playlists"] if p["id"] != pid]))


def space_playlist(pid: str) -> dict:
    st = _load()
    for p in st["playlists"]:
        if p["id"] == pid:
            return p
    raise ShareError("Playlist nicht im Teilen-Bereich")


# ------------------------------------------------------------------ Freunde (öffentliche Schlüssel, nur lesen)
_FRIEND_RAM: dict[str, tuple[float, dict]] = {}


def _fetch_public(space: str, kpub: bytes) -> dict:
    hit = _FRIEND_RAM.get(space)
    if hit and time.time() - hit[0] < 300:
        return hit[1]
    r = _http("GET", f"/v1/share/{space}/public")
    if r.status_code == 404:
        raise ShareError("Unter diesem Schlüssel ist (nicht mehr) etwas geteilt")
    if r.status_code != 200:
        raise ShareError(f"Laden fehlgeschlagen: {_err(r)}")
    doc = unseal(kpub, space + "/public", r.json()["blob"])
    doc["rev"] = r.json().get("rev")
    _FRIEND_RAM[space] = (time.time(), doc)
    return doc


def add_friend(key: str, nick: str = "") -> dict:
    k = parse_key(key)
    if k["kind"] == "private":
        raise ShareError("Das ist ein privater Schlüssel – damit liest UND schreibst du. Für Freunde bitte nur den "
                         "öffentlichen Schlüssel (SHT-O-…) verwenden. Für deinen zweiten Rechner: „Mit privatem Schlüssel verbinden“.")
    doc = _fetch_public(k["space"], k["kpub"])
    st = _load()
    st.setdefault("friends", [])
    if any(f["space"] == k["space"] for f in st["friends"]):
        raise ShareError("Diesen Schlüssel hast du schon hinzugefügt")
    if len(st["friends"]) >= MAX_FRIENDS:
        raise ShareError(f"Höchstens {MAX_FRIENDS} Freunde")
    st["friends"].append({"id": secrets.token_hex(6), "space": k["space"], "kpub": base64.b64encode(k["kpub"]).decode(),
                          "nick": (nick or "").strip()[:60], "name": doc.get("name", "")[:80], "added": time.time()})
    _save(st)
    return status()


def remove_friend(fid: str) -> dict:
    st = _load()
    st["friends"] = [f for f in st.get("friends", []) if f["id"] != fid]
    _save(st)
    return status()


def _friend(fid: str) -> dict:
    for f in _load().get("friends", []):
        if f["id"] == fid:
            return f
    raise ShareError("Freund nicht gefunden")


def friend_lists(fid: str, fresh: bool = False) -> dict:
    f = _friend(fid)
    if fresh:
        _FRIEND_RAM.pop(f["space"], None)
    doc = _fetch_public(f["space"], base64.b64decode(f["kpub"]))
    return {"id": fid, "nick": f.get("nick", ""), "name": doc.get("name", ""), "updated": doc.get("updated"),
            "playlists": [{"id": p["id"], "name": p["name"], "count": len(p.get("tracks", []))} for p in doc.get("playlists", [])]}


def friend_playlist(fid: str, pid: str) -> tuple[str, list[Track]]:
    f = _friend(fid)
    doc = _fetch_public(f["space"], base64.b64decode(f["kpub"]))
    for p in doc.get("playlists", []):
        if p["id"] == pid:
            return p["name"], [Track(title=t.get("title", ""), artists=t.get("artists") or [], album=t.get("album"),
                                     isrc=t.get("isrc"), ids=t.get("ids") or {}, duration_ms=t.get("duration_ms"),
                                     genre=t.get("genre"), subgenre=t.get("subgenre"))
                               for t in p.get("tracks", [])[:MAX_TRACKS] if t.get("title")]
    raise ShareError("Playlist nicht (mehr) geteilt")


def copy_to_local(name: str, tracks: list[Track]) -> int:
    n = 0
    for t in tracks:
        n += bool(store.add_to_playlist(name, t))
    return n

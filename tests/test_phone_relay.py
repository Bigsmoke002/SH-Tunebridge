"""Handy-Abgleich übers Internet: Handy und PC tauschen Anfrage/Antwort über zwei verschlüsselte Teilen-Räume aus.
Das Handy wird hier so nachgespielt wie in der Android-App (android/…/sync/PcSync.kt, relaySync)."""
import base64
import json
import time
import uuid

import httpx
import pytest

from tunebridge import consent, phone, share, store
from tunebridge.models import Track

from test_phone import _no_net, _pair, _rec        # noqa: F401 – _no_net ist eine Fixture (automatisch aktiv)
from test_share import FakeServer


@pytest.fixture()
def srv(monkeypatch):
    s = FakeServer()
    monkeypatch.setattr(httpx, "request", s)
    return s


def _allow():
    consent.save({"privacy": True, "server": {"domain": True, "relay": True}})


def _keys(secret: bytes, direction: str) -> dict:
    return share.derive(phone._kdf(secret, f"relay-{direction}"))


def _phone_put(srv, secret, req):
    """Handy legt eine Anfrage ab (wie relaySync: Raum „to-pc“)."""
    k = _keys(secret, "to-pc")
    room = srv.rooms.get(k["space"])
    body = {"rev": room["rev"] if room else 0, "priv": share.seal(k["kpriv"], k["space"] + "/private", {"req": req})}
    r = httpx.request("PUT", f"https://shtunebridge.bs002.de/v1/share/{k['space']}",
                      headers={"X-Share-Token": share._tok(k["token"])}, json=body)
    assert r.status_code == 200


def _phone_get(secret):
    k = _keys(secret, "to-phone")
    r = httpx.request("GET", f"https://shtunebridge.bs002.de/v1/share/{k['space']}/private",
                      headers={"X-Share-Token": share._tok(k["token"])})
    if r.status_code == 404:
        return None
    return share.unseal(k["kpriv"], k["space"] + "/private", r.json()["blob"])


def _req(**kw):
    return {"ts": int(time.time() * 1000), "rid": uuid.uuid4().hex, "device": {"name": "S23", "app": "0.11.0"},
            "cursor": 0, "recs": [], "deleted": [], "ops": [], "need_info": [], **kw}


def test_relay_needs_consent_and_switch(srv):
    dev, secret, _ = _pair()
    with pytest.raises(phone.PhoneError, match="Datenschutz"):
        phone.set_relay(dev, True)
    assert phone.relay_poll(force=True) == 0
    assert srv.seen == []                                          # ohne Einwilligung: keine einzige Anfrage
    _allow()
    assert phone.relay_poll(force=True) == 0 and srv.seen == []              # Einwilligung allein reicht nicht – je Handy einschalten
    st = phone.set_relay(dev, True)
    assert st["relay_allowed"] and st["devices"][0]["relay"] is True


def test_relay_roundtrip_is_encrypted(srv):
    _allow()
    dev, secret, _ = _pair()
    phone.set_relay(dev, True)
    store.import_recognition("pc-1", time.time() - 50, "PC", "mikrofon", "shazam", 1,
                             Track(title="Geheimer PC-Song", artists=["PC-Künstler"]), {})
    req = _req(recs=[_rec("android-r1", "Geheimer Handy-Song")])
    _phone_put(srv, secret, req)
    assert phone.relay_poll(force=True) == 1
    ans = _phone_get(secret)
    assert ans["rid"] == req["rid"]
    assert [r["track"]["title"] for r in ans["ans"]["recs"]] == ["Geheimer PC-Song"]
    assert store.recognitions_by_uid(["android-r1"])[0]["track"]["title"] == "Geheimer Handy-Song"
    d = phone.status()["devices"][0]
    assert d["via"] == "internet" and d["last_counts"] == {"empfangen": 1, "gesendet": 1}
    # Der Server sieht nur Chiffrate und zufällige Kennungen
    raw = json.dumps([s[2] for s in srv.seen if s[2]])
    assert "Geheim" not in raw and "Künstler" not in raw and "S23" not in raw
    # Anfrage wurde abgeholt: Ablage geleert, nochmaliges Nachsehen tut nichts
    assert phone.relay_poll(force=True) == 0


def test_relay_rejects_replay_and_old_requests(srv):
    _allow()
    dev, secret, _ = _pair()
    phone.set_relay(dev, True)
    req = _req(recs=[_rec("android-r2")])
    _phone_put(srv, secret, req)
    assert phone.relay_poll(force=True) == 1
    store.delete_recognition_uid("android-r2")
    _phone_put(srv, secret, req)                                    # dieselbe Anfrage noch einmal (z. B. vom Server zurückgespielt)
    assert phone.relay_poll(force=True) == 0
    assert not store.recognitions_by_uid(["android-r2"])
    old = _req(recs=[_rec("android-r3")])
    old["ts"] = int((time.time() - 8 * 86400) * 1000)
    _phone_put(srv, secret, old)
    assert phone.relay_poll(force=True) == 0                                  # älter als 7 Tage: verworfen
    assert not store.recognitions_by_uid(["android-r3"])


def test_relay_wrong_key_cannot_read_or_write(srv):
    _allow()
    dev, secret, _ = _pair()
    phone.set_relay(dev, True)
    _phone_put(srv, secret, _req())
    other = _keys(b"x" * 32, "to-pc")
    assert other["space"] != _keys(secret, "to-pc")["space"]
    k = _keys(secret, "to-pc")
    r = httpx.request("GET", f"https://shtunebridge.bs002.de/v1/share/{k['space']}/private",
                      headers={"X-Share-Token": share._tok(other["token"])})
    assert r.status_code == 403


def test_relay_answer_fits_server_limit(srv):
    _allow()
    dev, secret, _ = _pair()
    phone.set_relay(dev, True)
    import os
    for i in range(400):                                            # viele Erkennungen mit schwer komprimierbaren Daten
        store.import_recognition(f"pc-{i}", time.time() - 1000 + i, "PC", "mikrofon", "shazam", 1,
                                 Track(title=os.urandom(150).hex(), artists=[os.urandom(100).hex(), os.urandom(100).hex(), os.urandom(100).hex()]), {})
    for i in range(1600):
        store.add_to_playlist("Groß", Track(title=f"Song {i}", artists=["A"]))
    _phone_put(srv, secret, _req())
    assert phone.relay_poll(force=True) == 1
    k = _keys(secret, "to-phone")
    assert len(base64.b64decode(srv.rooms[k["space"]]["priv"])) <= phone.RELAY_LIMIT
    a = _phone_get(secret)["ans"]
    assert a["playlists"] is None and a["more"] is True              # große Playlists nur im Heimnetz, Rest in Runden
    assert 0 < len(a["recs"]) < 400 and a["cursor"] == a["recs"][-1]["ts"]
    assert any(c["name"] == "Groß" for c in a["catalog"])


def test_relay_off_and_remove_delete_server_rooms(srv):
    _allow()
    dev, secret, _ = _pair()
    phone.set_relay(dev, True)
    _phone_put(srv, secret, _req())
    phone.relay_poll(force=True)
    assert _keys(secret, "to-pc")["space"] in srv.rooms and _keys(secret, "to-phone")["space"] in srv.rooms
    phone.set_relay(dev, False)
    assert srv.rooms == {}
    phone.set_relay(dev, True)
    _phone_put(srv, secret, _req())
    phone.remove_device(dev)
    assert srv.rooms == {}


def test_relay_api_route(srv):
    from fastapi.testclient import TestClient
    from tunebridge.web.app import app
    client = TestClient(app)                                        # ohne Start-Schleifen
    dev, _, _ = _pair()
    r = client.post(f"/api/phone/devices/{dev}/relay", json={"enabled": True})
    assert r.status_code == 403
    _allow()
    r = client.post(f"/api/phone/devices/{dev}/relay", json={"enabled": True})
    assert r.status_code == 200 and r.json()["devices"][0]["relay"] is True


def test_relay_polls_rarely_and_backs_off(srv, monkeypatch):
    _allow()
    dev, secret, _ = _pair()
    phone.set_relay(dev, True)
    phone._relay_next["t"] = 0
    phone.relay_poll()
    n = len(srv.seen)
    assert n == 1                                                   # eine Abfrage (Ablage leer)
    phone.relay_poll()
    assert len(srv.seen) == n                                       # 30 s später: noch nicht wieder
    def limited(method, url, **kw):
        return httpx.Response(429, headers={"Retry-After": "3600"}, json={"error": "zu viele"}, request=httpx.Request(method, url))
    monkeypatch.setattr(httpx, "request", limited)
    phone.relay_poll(force=True)
    assert phone._relay_next["t"] > time.time() + 3000             # Server sagt „zu viele“: eine Stunde Pause

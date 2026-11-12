"""Handy koppeln und abgleichen: das Handy wird hier mit derselben Verschlüsselung nachgespielt wie in der
Android-App (android/…/sync/PcSync.kt)."""
import base64
import os
import threading
import time
import uuid
from urllib.parse import parse_qs, urlparse

import pytest

from tunebridge import phone, store
from tunebridge.models import Track
from tunebridge.share import seal, unseal


NETS = [
    {"cidr": "192.168.1.0/24", "ip": "192.168.1.20", "iface": "wlan0", "kind": "lan", "label": "Heimnetz · WLAN", "primary": True},
    {"cidr": "10.8.0.0/24", "ip": "10.8.0.5", "iface": "eth1", "kind": "lan", "label": "Heimnetz · Kabel", "primary": False},
    {"cidr": "100.64.0.0/10", "ip": "100.100.1.2", "iface": "wg0", "kind": "vpn", "label": "VPN", "primary": False},
]


@pytest.fixture(autouse=True)
def _no_net(monkeypatch):
    monkeypatch.setattr(phone, "ensure_server", lambda force=False: None)
    monkeypatch.setattr(phone, "_enrich_later", lambda uids: None)
    monkeypatch.setattr(phone, "networks", lambda fresh=False: [dict(n) for n in NETS])
    phone.set_net_consent(True)
    phone._pairing = None
    phone._seen.clear()


def _request(body, client="192.168.1.50", decide=True):
    """Kopplungsanfrage wie vom Handy; der PC entscheidet (decide=None: niemand klickt)."""
    out = {}

    def run():
        try:
            out["ans"] = phone.handle_pair(body, client)
        except phone.PhoneError as e:
            out["err"] = e
    t = threading.Thread(target=run)
    t.start()
    for _ in range(300):
        p = phone.status()["pairing"]
        if (p and p["request"]) or not t.is_alive():
            break
        time.sleep(0.01)
    if decide is not None and t.is_alive():
        out["shown"] = phone.status()["pairing"]["request"]
        phone.decide(decide)
    t.join(5)
    if "err" in out:
        out["err"].shown = out.get("shown")
        raise out["err"]
    out["ans"]["shown"] = out.get("shown")
    return out["ans"]


def _pair(dev="a1b2c3d4", code=None):
    p = phone.start_pairing()
    q = parse_qs(urlparse(p["uri"]).query)
    c = phone._norm_code(code or q["c"][0])
    kp = phone._kdf(c.encode(), "pair")
    secret = os.urandom(32)
    box = seal(kp, f"pair:{dev}", {"name": "Galaxy S23 Ultra", "secret": base64.b64encode(secret).decode(), "app": "0.11.0"})
    ans = _request({"v": 1, "id": dev, "box": box})
    return dev, secret, unseal(kp, f"pair-ok:{dev}", ans["box"])


def _sync(dev, secret, **payload):
    ks = phone._kdf(secret, "sync")
    rid = uuid.uuid4().hex
    req = {"ts": int(time.time() * 1000), "rid": rid, "device": {"name": "S23", "app": "0.11.0"}, "cursor": 0,
           "recs": [], "deleted": [], "ops": [], "need_info": [], **payload}
    ans = phone.handle_sync({"v": 1, "id": dev, "box": seal(ks, f"sync:{dev}", req)})
    return unseal(ks, f"sync-ok:{dev}:{rid}", ans["box"])


def _rec(uid, title="Song", ts=None):
    return {"uid": uid, "ts": ts or time.time(), "host": "Handy · SM-S918B", "source": "mikrofon", "engine": "shazam",
            "track": {"title": title, "artists": ["Künstler"]}, "extra": {"agreement": 1}}


def test_invite_and_pair():
    p = phone.start_pairing()
    assert p["uri"].startswith("shtb://pair?v=1&a=192.168.1.20:8766,10.8.0.5:8766,100.100.1.2:8766&c=")
    assert "&p=" in p["uri"]
    assert len(p["code"]) == 24 and p["code"].count("-") == 4
    svg = phone.qr_svg(p["uri"])
    assert svg.startswith("<svg") and "viewBox=" in svg and ' width="' not in svg.split(">")[0]   # skaliert, nie abgeschnitten
    phone._pairing = None
    dev, _, ok = _pair()
    assert ok["pc_name"] and ok["pc_id"]
    assert ok["addrs"] == ["192.168.1.20:8766", "10.8.0.5:8766", "100.100.1.2:8766"]   # auch bei eingetipptem Code
    st = phone.status()
    assert [d["name"] for d in st["devices"]] == ["Galaxy S23 Ultra"]
    assert "secret" not in st["devices"][0]


def test_code_is_one_time_and_typed_code_works():
    p = phone.start_pairing()
    typed = p["code"].lower()                       # Eingabe von Hand: Kleinschreibung, Bindestriche
    kp = phone._kdf(phone._norm_code(typed).encode(), "pair")
    box = seal(kp, "pair:dev1", {"name": "X", "secret": base64.b64encode(os.urandom(32)).decode()})
    _request({"id": "dev1", "box": box})
    with pytest.raises(phone.PhoneError):            # zweites Mal mit demselben Code: abgelehnt
        phone.handle_pair({"id": "dev2", "box": seal(kp, "pair:dev2", {"name": "Y", "secret": "x"})})


def test_wrong_code_and_try_limit():
    phone.start_pairing()
    wrong = phone._kdf(b"A" * 20, "pair")
    for _ in range(phone.PAIR_TRIES):
        with pytest.raises(phone.PhoneError) as e:
            phone.handle_pair({"id": "dev", "box": seal(wrong, "pair:dev", {"secret": ""})})
        assert e.value.status == 403
    with pytest.raises(phone.PhoneError) as e:
        phone.handle_pair({"id": "dev", "box": "x"})
    assert e.value.status == 429 and phone._pairing is None


def test_expired_code_rejected():
    p = phone.start_pairing()
    phone._pairing["expires"] = time.time() - 1
    kp = phone._kdf(phone._norm_code(p["code"]).encode(), "pair")
    with pytest.raises(phone.PhoneError):
        phone.handle_pair({"id": "dev", "box": seal(kp, "pair:dev", {"secret": base64.b64encode(os.urandom(32)).decode()})})


def test_sync_imports_phone_recognitions_once_and_returns_pc_ones():
    dev, secret, _ = _pair()
    store.add_recognition("mikrofon", "shazam", 2, Track(title="Vom PC", artists=["A"], genre="Techno"), {"bpm": 128})
    ans = _sync(dev, secret, recs=[_rec("android-1", "Vom Handy")])
    assert [r["track"]["title"] for r in ans["recs"]] == ["Vom PC"]     # eigene Handy-Songs nicht zurück
    assert "192.168.1.20:8766" in ans["addrs"]                           # neue PC-IP erreicht das Handy
    assert ans["recs"][0]["extra"] == {"bpm": 128}
    titles = [r["track"]["title"] for r in store.history()]
    assert sorted(titles) == ["Vom Handy", "Vom PC"]
    h = next(r for r in store.history() if r["uid"] == "android-1")
    assert h["host"] == "Handy · Galaxy S23 Ultra" and h["extra"]["handy"] is True
    _sync(dev, secret, recs=[_rec("android-1", "Vom Handy")], cursor=ans["cursor"])
    assert len(store.history()) == 2                                     # kein Doppelter
    again = _sync(dev, secret, cursor=ans["cursor"])
    assert again["recs"] == [] and again["cursor"] == ans["cursor"]


def test_sync_only_accepts_android_uids_and_deletes():
    dev, secret, _ = _pair()
    pc = store.add_recognition("mikrofon", "shazam", 1, Track(title="PC", artists=["A"]), {})
    pc_uid = store.history()[0]["uid"]
    _sync(dev, secret, recs=[_rec(pc_uid, "Überschrieben?")], deleted=[pc_uid])
    assert [r["id"] for r in store.history()] == [pc]                    # PC-Einträge kann das Handy nicht anfassen
    _sync(dev, secret, recs=[_rec("android-9")])
    _sync(dev, secret, deleted=["android-9"])
    assert [r["id"] for r in store.history()] == [pc]


def test_playlist_ops_and_playlists_back():
    dev, secret, _ = _pair()
    t = {"title": "Song", "artists": ["Künstler"], "isrc": "DEX123"}
    ans = _sync(dev, secret, ops=[{"op": "add", "playlist": "Unterwegs", "track": t}])
    assert ans["playlists"][0]["name"] == "Unterwegs" and ans["playlists"][0]["tracks"][0]["isrc"] == "DEX123"
    ans = _sync(dev, secret, ops=[{"op": "remove", "playlist": "Unterwegs", "track": t}])
    assert ans["playlists"][0]["tracks"] == []


def test_confirm_on_phone_keeps_pc_details():
    dev, secret, _ = _pair()
    _sync(dev, secret, recs=[{**_rec("android-2"), "extra": {"unsure": True}}])
    r = store.recognitions_by_uid(["android-2"])[0]
    store.update_recognition(r["id"], {**r["track"], "genre": "House"}, {**r["extra"], "genre_source": "lastfm"})
    ans = _sync(dev, secret, recs=[{**_rec("android-2"), "extra": {"unsure": False, "confirmed": True}}],
                need_info=["android-2"])
    x = store.recognitions_by_uid(["android-2"])[0]["extra"]
    assert x["confirmed"] is True and x["unsure"] is False and x["genre_source"] == "lastfm"
    assert ans["updates"][0]["track"]["genre"] == "House"


def test_replay_and_clock_and_wrong_key():
    dev, secret, _ = _pair()
    ks = phone._kdf(secret, "sync")
    req = {"ts": int(time.time() * 1000), "rid": "r1", "cursor": 0}
    body = {"id": dev, "box": seal(ks, f"sync:{dev}", req)}
    phone.handle_sync(body)
    with pytest.raises(phone.PhoneError) as e:
        phone.handle_sync(body)
    assert e.value.status == 409
    old = {"id": dev, "box": seal(ks, f"sync:{dev}", {"ts": int((time.time() - 3600) * 1000), "rid": "r2"})}
    with pytest.raises(phone.PhoneError):
        phone.handle_sync(old)
    with pytest.raises(phone.PhoneError):
        phone.handle_sync({"id": dev, "box": seal(os.urandom(32), f"sync:{dev}", {"ts": 0, "rid": "r3"})})
    phone.remove_device(dev)
    with pytest.raises(phone.PhoneError) as e:
        _sync(dev, secret)
    assert e.value.status == 403


def test_only_chosen_networks():
    assert phone._allowed("192.168.1.40") and phone._allowed("10.8.0.9") and phone._allowed("100.99.1.2")
    assert not phone._allowed("192.168.178.40")                      # privat, aber kein Netz dieses PCs
    assert not phone._allowed("127.0.0.1") and not phone._allowed("8.8.8.8")
    assert not phone._allowed("testclient") and not phone._allowed(None)
    phone.set_network("primary")
    assert phone.addresses() == ["192.168.1.20:8766"]
    assert phone._allowed("192.168.1.40") and not phone._allowed("100.99.1.2") and not phone._allowed("10.8.0.9")
    phone.set_network("some", ["10.8.0.0/24", "100.64.0.0/10"])
    assert phone.addresses() == ["10.8.0.5:8766", "100.100.1.2:8766"]
    assert not phone._allowed("192.168.1.40") and phone._allowed("100.99.1.2")
    st = phone.status()
    assert [n["active"] for n in st["networks"]] == [False, True, True]
    with pytest.raises(phone.PhoneError):
        phone.set_network("some", [])
    with pytest.raises(phone.PhoneError):
        phone.set_network("some", ["kein-netz"])
    with pytest.raises(phone.PhoneError):
        phone.set_network("irgendwo")


def test_no_network_selected_no_pairing():
    phone.set_network("some", ["172.31.0.0/16"])
    with pytest.raises(phone.PhoneError):
        phone.start_pairing()


def test_pc_shows_request_with_check_number_and_must_allow():
    p = phone.start_pairing()
    kp = phone._kdf(phone._norm_code(p["code"]).encode(), "pair")
    box = seal(kp, "pair:dev7", {"name": "Pixel 9", "secret": base64.b64encode(os.urandom(32)).decode(), "app": "0.11.0"})
    ans = _request({"id": "dev7", "box": box}, client="192.168.1.77")
    shown = ans["shown"]
    assert shown["name"] == "Pixel 9" and shown["ip"] == "192.168.1.77" and shown["app"] == "0.11.0"
    assert shown["check"] == phone.confirm_code(p["code"], "dev7") and len(shown["check"]) == 4
    assert [d["ip"] for d in phone.status()["devices"]] == ["192.168.1.77"]


def test_pc_rejects():
    p = phone.start_pairing()
    kp = phone._kdf(phone._norm_code(p["code"]).encode(), "pair")
    box = seal(kp, "pair:dev8", {"name": "Fremdes Handy", "secret": base64.b64encode(os.urandom(32)).decode()})
    with pytest.raises(phone.PhoneError) as e:
        _request({"id": "dev8", "box": box}, decide=False)
    assert e.value.status == 403 and "abgelehnt" in str(e.value)
    assert phone.status()["devices"] == [] and phone.status()["pairing"] is None    # Code verbraucht


def test_no_answer_on_pc_times_out(monkeypatch):
    monkeypatch.setattr(phone, "CONFIRM_SECONDS", 0.2)
    p = phone.start_pairing()
    kp = phone._kdf(phone._norm_code(p["code"]).encode(), "pair")
    box = seal(kp, "pair:dev9", {"name": "X", "secret": base64.b64encode(os.urandom(32)).decode()})
    with pytest.raises(phone.PhoneError) as e:
        _request({"id": "dev9", "box": box}, decide=None)
    assert e.value.status == 408 and phone.status()["devices"] == []


def test_cancel_on_pc_ends_waiting_request():
    p = phone.start_pairing()
    kp = phone._kdf(phone._norm_code(p["code"]).encode(), "pair")
    box = seal(kp, "pair:devA", {"name": "X", "secret": base64.b64encode(os.urandom(32)).decode()})
    out = {}

    def run():
        try:
            phone.handle_pair({"id": "devA", "box": box}, "192.168.1.5")
        except phone.PhoneError as e:
            out["e"] = e
    t = threading.Thread(target=run)
    t.start()
    for _ in range(300):
        if (phone.status()["pairing"] or {}).get("request"):
            break
        time.sleep(0.01)
    phone.cancel_pairing()
    t.join(5)
    assert out["e"].status == 403


def test_http_endpoints(monkeypatch):
    from fastapi.testclient import TestClient
    c = TestClient(phone._make_app())
    assert c.get("/phone/v1/hello").status_code == 403                  # „testclient“ ist keine private Adresse
    monkeypatch.setattr(phone, "_allowed", lambda h, nets=None: True)
    assert c.get("/phone/v1/hello").json()["app"] == "SH-Tunebridge"
    r = c.post("/phone/v1/pair", json={"id": "dev", "box": "x"})
    assert r.status_code == 403 and "Kopplungs-Code" in r.json()["detail"]
    assert c.post("/phone/v1/sync", content=b"{kaputt").status_code == 400


def test_api_pair_shows_qr(monkeypatch):
    from fastapi.testclient import TestClient
    from tunebridge.web.app import app
    with TestClient(app) as c:
        p = c.post("/api/phone/pair").json()
        assert p["qr"].startswith("<svg") and p["uri"].startswith("shtb://pair")
        assert c.get("/api/phone").json()["pairing"]
        assert c.post("/api/phone/pair/cancel").json()["pairing"] is None


def test_repairing_same_phone_replaces_old_entry():
    _pair(dev="alt1")
    _pair(dev="neu2")
    assert [d["id"] for d in phone.status()["devices"]] == ["neu2"]


def test_status_after_pairing_window_closed():
    _pair()
    assert phone.status()["pairing"]["paired"]            # Oberfläche sieht „gekoppelt“
    assert phone.status()["pairing"]["request"] is None
    phone._pairing["expires"] = time.time() - 1          # 20 s später, Aufräumen noch nicht gelaufen
    assert phone.status()["pairing"] is None


def test_shazams_from_phone_become_sortable_playlists_next_to_csv():
    from tunebridge import dataexport
    dataexport.save("shazam", {"playlists": [{"name": "Meine Shazams", "tracks": [Track(title="Aus CSV", artists=["X"])]}],
                               "liked": []}, "shazamlibrary.csv")
    dev, secret, _ = _pair()
    old = time.mktime((2025, 6, 1, 12, 0, 0, 0, 0, -1))
    recs = [{**_rec("android-shz-1", "Neu"), "source": "shazam-app", "extra": {"shazam_key": "123"}},
            {**_rec("android-shz-2", "Alt", ts=old), "source": "shazam-app"},
            {**_rec("android-shz-3", "Neu"), "source": "shazam-app"},            # doppelt -> nur einmal
            _rec("android-9", "Mikro")]                                           # normale Erkennung -> nicht dabei
    _sync(dev, secret, recs=recs)
    names = [p["name"] for p in dataexport.playlists("shazam")]
    assert names[:3] == ["Shazams vom Handy", f"Shazams vom Handy {time.strftime('%Y')}", "Shazams vom Handy 2025"]
    assert "Meine Shazams" in names                                               # CSV bleibt
    name, tracks = dataexport.load("shazam", "h0")
    assert [t.title for t in tracks] == ["Neu", "Alt"] and tracks[0].ids == {"shazam": "123"}
    _sync(dev, secret, deleted=["android-shz-1", "android-shz-3"])
    _, tracks = dataexport.load("shazam", "h0")
    assert [t.title for t in tracks] == ["Alt"]
    dataexport.save("shazam", {"playlists": [{"name": "Meine Shazams", "tracks": [Track(title="CSV neu", artists=["Y"])]}],
                               "liked": []}, "neu.csv")                          # neue CSV: Handy-Liste bleibt
    assert "Shazams vom Handy" in [p["name"] for p in dataexport.playlists("shazam")]


def test_similar_for_phone_is_encrypted_and_replay_safe(monkeypatch):
    from tunebridge import similar
    from tunebridge.models import Track
    seen = {}

    def fake_find(t, limit=15):
        seen["t"] = t
        return [(Track(title="Strobe", artists=["deadmau5"], isrc="X1", ids={"deezer": "42"}, tags={"house": 1.0}), 0.9)]
    monkeypatch.setattr(similar, "find", fake_find)
    dev, secret, _ = _pair()
    ks = phone._kdf(secret, "sync")
    req = {"ts": int(time.time() * 1000), "rid": "s1", "track": {"title": "One More Time", "artists": ["Daft Punk"]}, "limit": 5}
    body = {"id": dev, "box": seal(ks, f"similar:{dev}", req)}
    ans = unseal(ks, f"similar-ok:{dev}:s1", phone.handle_similar(body)["box"])
    assert seen["t"].title == "One More Time" and seen["t"].artists == ["Daft Punk"]
    assert ans["items"] == [{"title": "Strobe", "artists": ["deadmau5"], "isrc": "X1", "ids": {"deezer": "42"}, "match": 0.9}]
    with pytest.raises(phone.PhoneError) as e:          # gleiche Anfrage nochmal
        phone.handle_similar(body)
    assert e.value.status == 409
    with pytest.raises(phone.PhoneError):               # mit dem Sync-Kontext versiegelt -> passt nicht
        phone.handle_similar({"id": dev, "box": seal(ks, f"sync:{dev}", {**req, "rid": "s2"})})


def test_versions_for_phone_is_encrypted_and_replay_safe(monkeypatch):
    from tunebridge import remixes
    seen = {}

    def fake_find(t, limit=80):
        seen["t"] = t
        return [{"title": "Faded (X Remix)", "artists": ["Alan Walker"], "album": None, "duration_ms": 200000, "cover": "https://c/1",
                 "preview_url": "https://p/1", "ids": {"deezer": "1"}, "link": "https://www.deezer.com/track/1",
                 "kind": "remix", "label": "Remix von X", "rank": 5}]
    monkeypatch.setattr(remixes, "find", fake_find)
    dev, secret, _ = _pair()
    ks = phone._kdf(secret, "sync")
    req = {"ts": int(time.time() * 1000), "rid": "v1", "track": {"title": "Faded", "artists": ["Alan Walker"]}}
    body = {"id": dev, "box": seal(ks, f"versions:{dev}", req)}
    ans = unseal(ks, f"versions-ok:{dev}:v1", phone.handle_versions(body)["box"])
    assert seen["t"].title == "Faded" and ans["core"] == "Faded" and ans["kinds"][0]["id"] == "original"
    assert ans["items"] == [{"title": "Faded (X Remix)", "artists": ["Alan Walker"], "duration_ms": 200000, "cover": "https://c/1",
                             "ids": {"deezer": "1"}, "link": "https://www.deezer.com/track/1", "kind": "remix", "label": "Remix von X"}]
    with pytest.raises(phone.PhoneError) as e:
        phone.handle_versions(body)
    assert e.value.status == 409
    with pytest.raises(phone.PhoneError):               # anderer Kontext -> passt nicht
        phone.handle_versions({"id": dev, "box": seal(ks, f"similar:{dev}", {**req, "rid": "v2"})})


def test_fallback_for_phone_needs_phone_consent(monkeypatch):
    from tunebridge import fallback
    monkeypatch.setattr(fallback, "_youtube_search", lambda t: "ddddddddddd")
    monkeypatch.setattr(fallback, "_spotify_search", lambda t: (_ for _ in ()).throw(AssertionError("nicht erlaubt")))
    dev, secret, _ = _pair()
    ks = phone._kdf(secret, "sync")
    base = {"track": {"title": "Faded", "artists": ["Alan Walker"]}}
    with pytest.raises(phone.PhoneError) as e:                 # ohne Einwilligung am Handy: nichts
        phone.handle_fallback({"id": dev, "box": seal(ks, f"fallback:{dev}", {**base, "ts": int(time.time() * 1000), "rid": "f0"})})
    assert e.value.status == 403
    req = {**base, "ts": int(time.time() * 1000), "rid": "f1", "consent": ["youtube"], "known": {"spotify": "x"}}
    ans = unseal(ks, f"fallback-ok:{dev}:f1", phone.handle_fallback({"id": dev, "box": seal(ks, f"fallback:{dev}", req)})["box"])
    assert ans["youtube"] == "ddddddddddd" and ans["spotify"] is None


def test_phone_can_choose_which_playlists_it_gets():
    from tunebridge import store
    from tunebridge.models import Track
    dev, secret, _ = _pair()
    store.add_to_playlist("Techno", Track(title="A", artists=["X"]))
    store.add_to_playlist("Chill", Track(title="B", artists=["Y"]))
    store.add_to_playlist("Chill", Track(title="C", artists=["Z"]))
    all_ = _sync(dev, secret)
    assert {p["name"] for p in all_["playlists"]} >= {"Techno", "Chill"}
    assert {"name": "Chill", "n": 2} in all_["catalog"]
    some = _sync(dev, secret, lists=["Chill"])
    assert [p["name"] for p in some["playlists"]] == ["Chill"]
    assert {c["name"] for c in some["catalog"]} >= {"Techno", "Chill"}      # Übersicht bleibt vollständig
    none = _sync(dev, secret, lists=[])
    assert none["playlists"] == []


def _job(dev, secret, rid, **req):
    ks = phone._kdf(secret, "sync")
    req = {"ts": int(time.time() * 1000), "rid": rid, **req}
    return unseal(ks, f"job-ok:{dev}:{rid}", phone.handle_job({"id": dev, "box": seal(ks, f"job:{dev}", req)})["box"])


def test_phone_set_planner_runs_on_pc_and_saves(monkeypatch):
    from tunebridge import audiofeat, store
    from tunebridge.models import Track
    feats = {"A": (120, "8A", 0.3), "B": (124, "9A", 0.8), "C": (122, "8A", 0.5)}
    monkeypatch.setattr(audiofeat, "features", lambda t: dict(zip(("bpm", "camelot", "energy"), feats[t.title])))
    for n in "ABC":
        store.add_to_playlist("Party", Track(title=n, artists=["X"]))
    dev, secret, _ = _pair()
    g = _job(dev, secret, "g1", act="genres")
    assert g["genres"] and {c["id"] for c in g["curves"]} >= {"peak", "aufbau"}
    jid = _job(dev, secret, "j1", act="set-start", playlist="Party", curve="aufbau")["job"]
    for k in range(50):
        st = _job(dev, secret, f"s{k}", act="status", kind="set", job=jid)
        if st["state"] == "done":
            break
        time.sleep(0.05)
    assert st["state"] == "done" and sorted(st["order"]) == [0, 1, 2] and st["curve"] == "aufbau"
    assert {it["title"] for it in st["items"]} == {"A", "B", "C"} and st["items"][0]["bpm"]
    _job(dev, secret, "sv", act="save", kind="set", job=jid, idx=st["order"], name="Party (Set)")
    saved = next(p for p in store.local_playlists() if p.name == "Party (Set)")
    assert [t.title for t in saved.tracks] == [st["items"][i]["title"] for i in st["order"]]
    with pytest.raises(phone.PhoneError):                       # Name schon vergeben -> verständlicher Fehler
        _job(dev, secret, "sv2", act="save", kind="set", job=jid, idx=st["order"], name="Party (Set)")


def test_phone_job_needs_its_own_seal_and_no_replay():
    dev, secret, _ = _pair()
    ks = phone._kdf(secret, "sync")
    req = {"ts": int(time.time() * 1000), "rid": "x1", "act": "genres"}
    with pytest.raises(phone.PhoneError):                       # mit dem Kontext „similar“ versiegelt -> passt nicht
        phone.handle_job({"id": dev, "box": seal(ks, f"similar:{dev}", req)})
    body = {"id": dev, "box": seal(ks, f"job:{dev}", {**req, "rid": "x2"})}
    phone.handle_job(body)
    with pytest.raises(phone.PhoneError) as e:
        phone.handle_job(body)
    assert e.value.status == 409


def test_phone_mix_start_validates(monkeypatch):
    from tunebridge import mixgen
    monkeypatch.setattr(mixgen, "_run", lambda job: job.update(state="done", items=[{"title": "S", "artists": ["Y"], "artist": "Y"}],
                                                                 order=[0], reserve=[]))
    dev, secret, _ = _pair()
    with pytest.raises(phone.PhoneError):
        _job(dev, secret, "m0", act="mix-start", seeds=[], opts={})
    jid = _job(dev, secret, "m1", act="mix-start", seeds=[{"id": 27, "name": "Daft Punk"}], opts={"level": "locker", "count": 10})["job"]
    time.sleep(0.05)
    st = _job(dev, secret, "m2", act="status", kind="mix", job=jid)
    assert st["state"] == "done" and st["items"][0]["title"] == "S" and st["order"] == [0]

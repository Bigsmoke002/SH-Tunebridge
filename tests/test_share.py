"""Playlists teilen: privater Schlüssel (lesen+schreiben), öffentlicher (nur lesen, nur freigegebene Playlists).
Der Server wird hier nachgebildet (gleiche Regeln wie der echte) – er bekommt nur Chiffrate zu sehen."""
import base64
import hashlib
import json

import httpx
import pytest

from tunebridge import consent, share, store
from tunebridge.models import Track


class FakeServer:
    def __init__(self):
        self.rooms = {}
        self.seen = []                                     # alles, was beim Server ankommt

    def __call__(self, method, url, headers=None, json=None, timeout=None):
        path = url.split("bs002.de")[-1]
        self.seen.append((method, path, json, dict(headers or {})))
        tok = (headers or {}).get("X-Share-Token")
        th = hashlib.sha256(base64.urlsafe_b64decode(tok + "==")).hexdigest() if tok else None
        parts = path.strip("/").split("/")                 # v1 share <space> [public|private]
        space = parts[2]
        room = self.rooms.get(space)
        req = httpx.Request(method, url)
        if method == "PUT":
            if room is None:
                if json["rev"] != 0:
                    return httpx.Response(409, json={"rev": 0}, request=req)
                self.rooms[space] = room = {"token": th, "rev": 0}
            elif room["token"] != th:
                return httpx.Response(403, json={"error": "Falscher Schlüssel"}, request=req)
            elif room["rev"] != json["rev"]:
                return httpx.Response(409, json={"rev": room["rev"]}, request=req)
            room.update(rev=room["rev"] + 1, priv=json["priv"], pub=json["pub"])
            return httpx.Response(200, json={"rev": room["rev"]}, request=req)
        if room is None:
            return httpx.Response(404, json={"error": "nicht da"}, request=req)
        if method == "DELETE":
            if room["token"] != th:
                return httpx.Response(403, json={}, request=req)
            del self.rooms[space]
            return httpx.Response(200, json={"geloescht": True}, request=req)
        if parts[3] == "private":
            if room["token"] != th:
                return httpx.Response(403, json={"error": "Falscher Schlüssel"}, request=req)
            return httpx.Response(200, json={"blob": room["priv"], "rev": room["rev"]}, request=req)
        return httpx.Response(200, json={"blob": room["pub"], "rev": room["rev"]}, request=req)


@pytest.fixture()
def srv(monkeypatch):
    s = FakeServer()
    monkeypatch.setattr(httpx, "request", s)
    return s


def _allow():
    consent.save({"privacy": True, "server": {"domain": True, "share": True}})


def _pl(name, *songs):
    for a, t in songs:
        store.add_to_playlist(name, Track(title=t, artists=[a], cover="https://x/cover.jpg", preview_url="https://x/p.mp3"))


def test_keys_roundtrip_and_typos():
    root = bytes(range(32))
    pk, ok = share.private_key(root), share.public_key(root)
    assert pk.startswith("SHT-P-") and ok.startswith("SHT-O-")
    assert share.parse_key(pk)["root"] == root
    assert share.parse_key(ok.lower().replace("-", " "))["space"] == share.derive(root)["space"]   # tolerant beim Einfügen
    bad = ok[:-3] + ("A" if ok[-3] != "A" else "B") + ok[-2:]
    with pytest.raises(share.ShareError, match="ungültig"):
        share.parse_key(bad)
    with pytest.raises(share.ShareError):
        share.parse_key("hallo")


def test_needs_consent(srv):
    with pytest.raises(share.ShareError, match="Datenschutz"):
        share.create("Leon")
    assert srv.seen == []                                   # ohne Einwilligung: keine einzige Anfrage


def test_share_private_and_public(srv, tmp_path):
    _allow()
    _pl("Hardtekk Bretter", ("Kloud", "AGAINST"), ("TEKKCAT", "In My Skin"))
    _pl("Geheim", ("Netsky", "Rio"))
    st = share.create("Leons Playlists")
    share.add_local(["Hardtekk Bretter"], public=True)
    st = share.add_local(["Geheim"], public=False)
    assert [(p["name"], p["public"]) for p in st["playlists"]] == [("Hardtekk Bretter", True), ("Geheim", False)]
    # Der Server sieht nur Chiffrate – keine Namen, keine Songs
    dump = json.dumps([x[2] for x in srv.seen])
    for word in ("Hardtekk", "Kloud", "Geheim", "Netsky", "Leons"):
        assert word not in dump
    # Cover/Hörproben werden nie geteilt
    doc = share.unseal(share.derive(base64.b64decode(share._load()["root"]))["kpriv"],
                       share.derive(base64.b64decode(share._load()["root"]))["space"] + "/private",
                       next(iter(srv.rooms.values()))["priv"])
    assert "cover" not in json.dumps(doc) and "preview" not in json.dumps(doc)

    # Freund mit öffentlichem Schlüssel: sieht nur die öffentliche Playlist
    pub, priv = st["public_key"], st["private_key"]
    share.leave()                                           # „anderer Rechner“
    with pytest.raises(share.ShareError, match="privater Schlüssel"):
        share.add_friend(priv)
    fs = share.add_friend(pub, "Leon")
    fid = fs["friends"][0]["id"]
    lists = share.friend_lists(fid)
    assert lists["name"] == "Leons Playlists" and [p["name"] for p in lists["playlists"]] == ["Hardtekk Bretter"]
    name, tracks = share.friend_playlist(fid, lists["playlists"][0]["id"])
    assert [t.title for t in tracks] == ["AGAINST", "In My Skin"]
    assert share.copy_to_local("Von Leon", tracks) == 2
    # mit öffentlichem Schlüssel kann man nicht schreiben
    with pytest.raises(share.ShareError, match="öffentlicher Schlüssel"):
        share.join(pub)

    # zweiter Rechner mit privatem Schlüssel: liest alles und darf schreiben
    st2 = share.join(priv)
    assert {p["name"] for p in st2["playlists"]} == {"Hardtekk Bretter", "Geheim"}
    gid = next(p["id"] for p in st2["playlists"] if p["name"] == "Geheim")
    share.set_public(gid, True)
    share._FRIEND_RAM.clear()
    assert {p["name"] for p in share.friend_lists(fid)["playlists"]} == {"Hardtekk Bretter", "Geheim"}


def test_conflict_is_merged(srv):
    _allow()
    _pl("A", ("X", "1"))
    _pl("B", ("Y", "2"))
    share.create("")
    share.add_local(["A"])
    space = next(iter(srv.rooms))
    saved = share._load()
    saved["rev"] = 0                                        # dieser Rechner ist veraltet
    share._save(saved)
    srv.rooms[space]["rev"] += 0
    st = share.add_local(["B"])                             # holt erst den neuen Stand, dann schreiben
    assert {p["name"] for p in st["playlists"]} == {"A", "B"}


def test_wrong_token_cannot_overwrite(srv):
    _allow()
    share.create("echt")
    space = next(iter(srv.rooms))
    evil = share.derive(b"\x01" * 32)
    r = httpx.request("PUT", f"https://shtunebridge.bs002.de/v1/share/{space}",
                      headers={"X-Share-Token": share._tok(evil["token"])}, json={"rev": 1, "priv": "x", "pub": None})
    assert r.status_code == 403


def test_delete_space(srv):
    _allow()
    st = share.create("weg")
    pub = st["public_key"]
    share.delete_space()
    assert not srv.rooms and not share.status()["active"]
    with pytest.raises(share.ShareError, match="nicht mehr"):
        share.add_friend(pub)


def test_friend_playlists_as_service(srv):
    from tunebridge import services
    _allow()
    _pl("Phonk", ("Kordhell", "Murder In My Mind"))
    st = share.create("K")
    st = share.add_local(["Phonk"], public=True)
    share.leave()
    fid = share.add_friend(st["public_key"])["friends"][0]["id"]
    lists = services.playlists(f"friend-{fid}")
    assert lists[0]["name"] == "Phonk"
    assert services.load(f"friend-{fid}", lists[0]["id"])[1][0].artists == ["Kordhell"]

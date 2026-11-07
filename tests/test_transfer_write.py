"""Übertragen zu YouTube und SoundCloud (vorher nur lesend angebunden) – ohne Netz, mit nachgebauten APIs."""
import time

import httpx
import pytest
from fastapi.testclient import TestClient

from tunebridge import store, transfer
from tunebridge.models import Track
from tunebridge.providers import oauth
from tunebridge.providers.soundcloud import SoundCloud
from tunebridge.providers.youtube import QuotaExceeded, YouTube


def _tok(p, scope=""):
    p.tok = {"access_token": "x", "refresh_token": "r", "expires": time.time() + 999, "scope": scope}
    return p


class FakeHttp:
    """Ersetzt httpx.request; route(method, url, params, json) -> (status, body)."""
    def __init__(self, route):
        self.route, self.calls = route, []

    def __call__(self, method, url, params=None, json=None, **kw):
        self.calls.append((method, url, params or {}, json))
        st, body = self.route(method, url, params or {}, json)
        return httpx.Response(st, json=body, request=httpx.Request(method, url))


def test_youtube_write_needs_extra_scope_only_on_request(monkeypatch):
    yt = _tok(YouTube(), "https://www.googleapis.com/auth/youtube.readonly")
    assert not yt.can_write()
    with pytest.raises(oauth.OAuthError, match="Schreibrecht"):
        yt.create_playlist("X")
    monkeypatch.setattr(YouTube, "configured", lambda self: True)
    monkeypatch.setattr(YouTube, "client_id", lambda self: "cid")
    assert "auth%2Fyoutube+" not in yt.login()["url"] and "auth%2Fyoutube&" not in yt.login()["url"]   # normal: nur Lesen
    assert "auth%2Fyoutube.readonly+https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fyoutube" in yt.login(write=True)["url"]


def test_youtube_transfer_skips_existing_and_reports_quota(monkeypatch):
    yt = _tok(YouTube(), "https://www.googleapis.com/auth/youtube.readonly https://www.googleapis.com/auth/youtube")

    def route(m, url, p, j):
        if url.endswith("/search"):
            return 200, {"items": [{"id": {"videoId": "v-" + p["q"].split()[-1]},
                                    "snippet": {"title": "K - " + p["q"].split()[-1], "channelTitle": "K - Topic"}}]}
        if url.endswith("/playlists") and m == "POST":
            return 200, {"id": "PL1"}
        if url.endswith("/playlistItems") and m == "GET":
            return 200, {"items": [{"contentDetails": {"videoId": "v-A"}}]}
        if url.endswith("/playlistItems") and m == "POST":
            return 200, {}
        return 404, {}
    fake = FakeHttp(route)
    monkeypatch.setattr(httpx, "request", fake)
    monkeypatch.setattr(httpx, "get", lambda url, **kw: fake("GET", url, **kw))
    found = [yt.find(Track(t, ["K"])) for t in ("A", "B")]
    assert [f.ids["youtube"] for f in found] == ["v-A", "v-B"]
    assert yt.create_playlist("Mix") == "PL1"
    yt.add_to_playlist("PL1", found)
    inserted = [c[3]["snippet"]["resourceId"]["videoId"] for c in fake.calls if c[0] == "POST" and c[1].endswith("playlistItems")]
    assert inserted == ["v-B"]                                       # v-A war schon drin
    assert next(c for c in fake.calls if c[1].endswith("/playlists"))[3]["status"]["privacyStatus"] == "private"

    quota = FakeHttp(lambda *a: (403, {"error": {"message": "q", "errors": [{"reason": "quotaExceeded"}]}}))
    monkeypatch.setattr(httpx, "get", lambda url, **kw: quota("GET", url, **kw))
    with pytest.raises(QuotaExceeded, match="Tageskontingent"):
        yt.find(Track("C", ["K"]))


def test_soundcloud_add_keeps_existing_tracks(monkeypatch):
    sc = _tok(SoundCloud())

    def route(m, url, p, j):
        if url.endswith("/tracks") and m == "GET":
            return 200, {"collection": [{"id": 7, "title": "B", "user": {"username": "K"}, "permalink_url": "https://sc/k/b"}]}
        if url.endswith("/playlists") and m == "POST":
            return 201, {"id": 55, "permalink_url": "https://sc/k/sets/mix"}
        if url.endswith("/playlists/55") and m == "GET":
            return 200, {"id": 55, "tracks": [{"id": 3}], "permalink_url": "https://sc/k/sets/mix"}
        if url.endswith("/playlists/55") and m == "PUT":
            return 200, {}
        return 404, {}
    fake = FakeHttp(route)
    monkeypatch.setattr(httpx, "request", fake)
    monkeypatch.setattr(httpx, "get", lambda url, **kw: fake("GET", url, **kw))
    hit = sc.find(Track("B", ["K"]))
    assert hit and hit.ids["soundcloud"] == "https://sc/k/b"
    pid = sc.create_playlist("Mix")
    assert pid == "55" and next(c for c in fake.calls if c[0] == "POST")[3]["playlist"]["sharing"] == "private"
    sc.add_to_playlist(pid, [hit, Track("Alt", ["K"], ids={"soundcloud": "3"})])
    put = next(c for c in fake.calls if c[0] == "PUT")
    assert put[3] == {"playlist": {"tracks": [{"id": 3}, {"id": 7}]}}   # vorhandene bleiben, keine Doppelten
    assert sc.playlist_url(pid) == "https://sc/k/sets/mix"


class FakeProv:
    name, title = "youtube", "YouTube"

    def __init__(self, write=True, fail_after=None):
        self.write, self.fail_after, self.n, self.added, self.created = write, fail_after, 0, [], []

    def can_write(self):
        return self.write

    def find(self, t):
        self.n += 1
        if self.fail_after is not None and self.n > self.fail_after:
            raise QuotaExceeded("Tageskontingent aufgebraucht")
        return Track(t.title, t.artists, ids={"youtube": "v" + t.title})

    def create_playlist(self, name, description=""):
        self.created.append(name)
        return "NEW"

    def add_to_playlist(self, pid, tracks):
        self.added.append((pid, [t.title for t in tracks]))

    def playlist_url(self, pid):
        return f"u/{pid}"


def _run(monkeypatch, prov, **kw):
    for t in ("A", "B", "C"):
        store.add_to_playlist("Quelle", Track(t, ["K"]))
    monkeypatch.setattr(transfer, "get_provider", lambda n: prov)
    job = {"id": "j", "src": "local", "src_id": "Quelle", "dst": "youtube", "name": "Ziel", "like": False,
           "state": "queued", "done": 0, "total": 0, "cancel": False, **kw}
    transfer._run(job)
    return job


def test_transfer_into_existing_service_playlist(monkeypatch):
    p = FakeProv()
    job = _run(monkeypatch, p, dst_pid="PL9")
    assert job["state"] == "done" and p.created == []                 # nichts neu angelegt
    assert p.added[0][0] == "PL9" and sorted(p.added[0][1]) == ["A", "B", "C"] and job["url"] == "u/PL9"


def test_transfer_quota_stops_partway_keeps_found(monkeypatch):
    p = FakeProv(fail_after=2)
    job = _run(monkeypatch, p)
    assert job["state"] == "done" and job["found"] == 2 and "Tageskontingent" in job["stopped"]
    assert len(job["missing"]) == 1 and p.created == ["Ziel"]


def test_transfer_without_write_permission(monkeypatch):
    job = _run(monkeypatch, FakeProv(write=False))
    assert job["state"] == "error" and "Schreibrecht" in job["error"]
    from tunebridge.web import app as webapp
    monkeypatch.setattr(webapp, "_can_write", lambda pid: False)
    monkeypatch.setattr(webapp, "_prov", lambda pid: _tok(YouTube()))
    r = TestClient(webapp.app).post("/api/transfer", json={"src": "local", "src_id": "Quelle", "dst": "youtube", "name": "X"})
    assert r.status_code == 409 and "Schreibrecht" in r.json()["detail"]

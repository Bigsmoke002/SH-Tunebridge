"""YouTube-/SoundCloud-Login (OAuth mit eigener App, nur im Client) und automatischer Abgleich – ohne Netz."""
import json
import sys
import time
from urllib.parse import parse_qs, urlparse

import pytest

from tunebridge import autosync, store
from tunebridge.models import Track


@pytest.fixture(autouse=True)
def db(tmp_path, monkeypatch):
    """Nie die echte Datenbank oder echte Token anfassen."""
    from tunebridge import config
    from tunebridge import providers
    monkeypatch.setattr(config, "DATA", tmp_path)
    monkeypatch.setattr(store, "DB", tmp_path / "t.db")
    monkeypatch.setattr(providers, "_instances", {})
    for k in ("YOUTUBE_OAUTH_CLIENT_ID", "YOUTUBE_OAUTH_CLIENT_SECRET", "SOUNDCLOUD_CLIENT_ID", "SOUNDCLOUD_CLIENT_SECRET"):
        monkeypatch.delenv(k, raising=False)
    store.ram_clear()
    yield store
    store.ram_clear()


class _Resp:
    def __init__(self, data, code=200):
        self._d, self.status_code, self.text = data, code, json.dumps(data)

    def json(self):
        return self._d


def test_soundcloud_login_flow(monkeypatch, tmp_path):
    from tunebridge.providers import get_provider
    from tunebridge.providers.oauth import OAuthError
    sc = get_provider("soundcloud")
    with pytest.raises(OAuthError, match="Client-ID"):
        sc.login()
    monkeypatch.setenv("SOUNDCLOUD_CLIENT_ID", "abcdefghijklmnop")
    monkeypatch.setenv("SOUNDCLOUD_CLIENT_SECRET", "geheim123")
    # Vorab-Prüfung der Zugangsdaten: falsch -> klare Meldung statt weißer SoundCloud-Seite
    class _R:
        def __init__(self, code, body): self.status_code, self._b = code, body
        def json(self): return self._b
    monkeypatch.setattr("tunebridge.providers.soundcloud.httpx.post", lambda *a, **k: _R(401, {"error": "invalid_client"}))
    with pytest.raises(OAuthError, match="Zugangsdaten"):
        sc.login()
    monkeypatch.setattr("tunebridge.providers.soundcloud.httpx.post", lambda *a, **k: _R(200, {"access_token": "x"}))
    st = sc.login()
    q = parse_qs(urlparse(st["url"]).query)
    assert st["url"].startswith("https://secure.soundcloud.com/authorize")
    assert q["redirect_uri"] == ["http://127.0.0.1:8765/api/oauth/soundcloud/callback"]
    assert q["code_challenge_method"] == ["S256"]
    with pytest.raises(OAuthError):
        sc.finish_login("code", "falscher-state")          # CSRF-Schutz
    sent = {}

    def post(url, data=None, **k):
        sent.update(data)
        return _Resp({"access_token": "AT", "refresh_token": "RT", "expires_in": 3600})
    monkeypatch.setattr("tunebridge.providers.oauth.httpx.post", post)
    sc.finish_login("code", q["state"][0])
    assert sent["code_verifier"] and sent["client_secret"] == "geheim123"
    tok = tmp_path / "tokens" / "soundcloud.json"
    assert tok.exists()
    if sys.platform != "win32":                                   # Windows kennt keine Unix-Dateirechte
        assert oct(tok.stat().st_mode)[-3:] == "600"
    assert sc.login_state()["state"] == "connected"
    # abgelaufen -> Refresh, neues Refresh-Token wird übernommen (SoundCloud: nur einmal gültig)
    sc.tok["expires"] = time.time() - 1
    monkeypatch.setattr("tunebridge.providers.oauth.httpx.post",
                        lambda url, data=None, **k: _Resp({"access_token": "AT2", "refresh_token": "RT2", "expires_in": 3600}))
    assert sc._access() == "AT2" and sc.tok["refresh_token"] == "RT2"
    sc.logout()
    assert not tok.exists()


def test_soundcloud_tracks(monkeypatch):
    from tunebridge.providers import soundcloud
    t = soundcloud.to_track({"title": "Artist X - Cool Song", "user": {"username": "uploader"}, "duration": 1000,
                             "artwork_url": "https://i1.sndcdn.com/a-large.jpg", "permalink_url": "https://soundcloud.com/x/y"})
    assert t.title == "Cool Song" and t.artists == ["Artist X"]
    assert t.cover.endswith("-t300x300.jpg") and t.ids["soundcloud"] == "https://soundcloud.com/x/y"
    t2 = soundcloud.to_track({"title": "Song", "publisher_metadata": {"artist": "Real", "isrc": "DEX1"}, "user": {}})
    assert t2.artists == ["Real"] and t2.isrc == "DEX1"


def test_youtube_playlists(monkeypatch):
    from tunebridge.providers import get_provider
    monkeypatch.setenv("YOUTUBE_OAUTH_CLIENT_ID", "x.apps.googleusercontent.com")
    monkeypatch.setenv("YOUTUBE_OAUTH_CLIENT_SECRET", "s")
    yt = get_provider("youtube")
    yt.tok = {"access_token": "AT", "expires": time.time() + 999}
    calls = []

    def get(url, params=None, headers=None, **k):
        calls.append((url, params))
        assert headers["Authorization"] == "Bearer AT"
        if url.endswith("/playlistItems"):
            return _Resp({"items": [{"snippet": {"title": "Muse - Uprising (Official Video)", "videoOwnerChannelTitle": "MuseVEVO",
                                                 "resourceId": {"videoId": "v1"}, "thumbnails": {"medium": {"url": "https://i.ytimg.com/1.jpg"}}}},
                                    {"snippet": {"title": "Private video"}}]})
        if url.endswith("/videos"):
            return _Resp({"items": [{"id": "v1", "snippet": {"categoryId": "10"}}]})
        return _Resp({"items": [{"id": "PL1", "snippet": {"title": "Meine Liste"}, "contentDetails": {"itemCount": 1}}]})
    monkeypatch.setattr("tunebridge.providers.youtube.httpx.get", get)
    assert yt.playlist_list()[0]["name"] == "Meine Liste"
    tr = yt.liked()
    assert len(tr) == 1 and tr[0].ids == {"youtube": "v1"} and "Uprising" in tr[0].title
    assert calls[-2][1]["playlistId"] == "LL"
    assert calls[-1][0].endswith("/videos") and calls[-1][1]["id"] == "v1" and not tr[0].tags   # Musik: unmarkiert
    from tunebridge.providers.oauth import OAuthError
    with pytest.raises(OAuthError, match="Schreibrecht"):     # nur Lese-Token: Übertragen erst nach Freigabe
        yt.create_playlist("x")


def test_services_overview_states(monkeypatch):
    from tunebridge import services
    ov = {s["id"]: s for s in services.overview(lambda sid: (False, None))}
    assert ov["soundcloud"]["kind"] == "account" and ov["soundcloud"]["needs"] == "setup"
    monkeypatch.setenv("SOUNDCLOUD_CLIENT_ID", "abcdefghijklmnop")
    monkeypatch.setenv("SOUNDCLOUD_CLIENT_SECRET", "geheim123")
    ov = {s["id"]: s for s in services.overview(lambda sid: (sid == "youtube", "Kanal" if sid == "youtube" else None))}
    assert ov["soundcloud"]["needs"] == "connect"
    assert ov["youtube"]["ready"] and ov["youtube"]["account"] == "Kanal"


def test_oauth_callback_route(monkeypatch):
    from fastapi.testclient import TestClient
    from tunebridge.web.app import app
    monkeypatch.setenv("SOUNDCLOUD_CLIENT_ID", "abcdefghijklmnop")
    monkeypatch.setenv("SOUNDCLOUD_CLIENT_SECRET", "geheim123")
    c = TestClient(app)
    r = c.get("/api/oauth/soundcloud/callback", params={"error": "access_denied"})
    assert "abgebrochen" in r.text
    assert c.get("/api/oauth/evil/callback").status_code == 404
    r = c.post("/api/transfer", json={"src": "local", "src_id": "x", "dst": "soundcloud", "name": "x"})
    assert r.status_code == 400 and "nicht verbunden" in r.json()["detail"]     # Ziel möglich, aber erst verbinden


def _fake_sources(monkeypatch, data: dict):
    """data: sid -> {playlist name: [Track, …]}"""
    from tunebridge import services
    monkeypatch.setattr(autosync, "sources", lambda: [{"id": sid, "name": sid.title(), "kind": "account"} for sid in data])
    monkeypatch.setattr(services, "playlists", lambda sid: [{"id": n, "name": n} for n in data[sid]])
    monkeypatch.setattr(services, "load", lambda sid, pid: ("", data[sid][pid]))
    monkeypatch.setattr("tunebridge.linkimport._analyse_one", lambda t: {
        "title": t.title, "artists": t.artists, "genre": "Drum & Bass", "subgenre": "Liquid", "bpm": 174, "ids": t.ids})


def test_autosync_baseline_then_new(monkeypatch):
    a, b, c = Track("Alt", ["A"]), Track("Neu", ["B"]), Track("Noch neuer", ["C"])
    data = {"spotify": {"__liked__": [a]}}
    _fake_sources(monkeypatch, data)
    r = autosync.run_once()
    assert r["ok"] and r["found"] == 0 and autosync.inbox() == []       # erster Durchgang: nur Grundstand
    data["spotify"]["__liked__"] = [a, b]
    assert autosync.run_once()["found"] == 1
    item = autosync.inbox()[0]
    assert item["title"] == "Neu" and item["genre"] == "Drum & Bass" and item["sid"] == "spotify"
    assert any(s["new"] for s in item["suggestions"])                   # Vorschlag neue Genre-Playlist
    # gespeichert werden nur Prüfsummen, keine Titel
    raw = store.meta_get("autosync_seen")
    assert "Alt" not in raw and "Neu" not in raw
    # kein zweites Mal
    assert autosync.run_once()["found"] == 0
    # schon lokal einsortiert -> nicht in die Inbox
    store.add_to_playlist("Meins", c)
    data["spotify"]["__liked__"].append(c)
    assert autosync.run_once()["found"] == 0


def test_autosync_inbox_api(monkeypatch):
    from fastapi.testclient import TestClient
    from tunebridge.web.app import app
    data = {"soundcloud": {"__liked__": []}}
    _fake_sources(monkeypatch, data)
    autosync.run_once()
    data["soundcloud"]["__liked__"] = [Track("X", ["Y"]), Track("Z", ["W"])]
    autosync.run_once()
    cl = TestClient(app)
    d = cl.get("/api/autosync").json()
    assert d["count"] == 2 and len(d["items"]) == 2
    first, second = d["items"]
    r = cl.post(f"/api/autosync/inbox/{first['id']}/add", json={"playlist": "DnB"}).json()
    assert r["added"]
    assert any(p.name == "DnB" for p in store.local_playlists())
    cl.post(f"/api/autosync/inbox/{second['id']}/done")
    assert cl.get("/api/autosync/status").json()["count"] == 0
    s = cl.post("/api/autosync", json={"interval_h": 999, "enabled": False}).json()
    assert s["settings"]["interval_h"] == 48 and not s["settings"]["enabled"] and s["next_run"] is None


def test_autosync_budget_and_disabled_service(monkeypatch):
    data = {"spotify": {"__liked__": []}, "deezer": {"__liked__": []}}
    _fake_sources(monkeypatch, data)
    autosync.run_once()
    monkeypatch.setattr(autosync, "MAX_NEW_PER_RUN", 3)
    data["spotify"]["__liked__"] = [Track(f"S{i}", ["A"]) for i in range(5)]
    data["deezer"]["__liked__"] = [Track("D", ["B"])]
    autosync.save({"services": {"deezer": False}})
    assert autosync.run_once()["found"] == 3
    assert autosync.run_once()["found"] == 2         # Rest beim nächsten Mal
    assert all(x["sid"] == "spotify" for x in autosync.inbox())


def test_spotify_premium_block_is_reported(monkeypatch, tmp_path):
    """Login ok, aber Spotify sperrt (App-Besitzer ohne Premium) -> nicht „verbunden“ melden, Grund anzeigen."""
    import tunebridge.providers.spotify as sp
    from tunebridge import config
    monkeypatch.setattr(config, "DATA", tmp_path)
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "0123456789abcdef0123456789abcdef")
    prov = sp.Spotify()
    st = prov.login()
    csrf = parse_qs(urlparse(st["url"]).query)["state"][0]

    class R:
        def __init__(self, code, body): self.status_code, self._b, self.content, self.headers = code, body, b"x", {}
        def json(self): return self._b
    monkeypatch.setattr(sp.httpx, "post", lambda *a, **k: R(200, {"access_token": "AT", "refresh_token": "RT", "expires_in": 3600}))
    monkeypatch.setattr(sp.httpx, "request", lambda *a, **k: R(403, {"error": {"message": "Active premium subscription required for the owner of the app."}}))
    with pytest.raises(sp.SpotifyError, match="Premium"):
        prov.finish_login("code", csrf)
    assert prov.login_state()["state"] == "failed" and "Premium" in prov.login_state()["error"]
    assert prov.connected() is False and "Premium" in prov.last_error
    monkeypatch.setattr(sp.httpx, "request", lambda *a, **k: R(200, {"id": "me"}))
    assert prov.connected() is True and prov.last_error is None


def test_autosync_auto_sort_and_undo(monkeypatch):
    """Sichere Treffer landen selbst in der eigenen Playlist; Rückgängig nimmt sie wieder heraus."""
    from fastapi.testclient import TestClient
    from tunebridge.web.app import app
    for i in range(4):
        store.add_to_playlist("Meine Liquid DnB", Track(f"Alt{i}", [f"K{i}"], genre="Drum & Bass", subgenre="Liquid"))
    data = {"spotify": {"__liked__": []}}
    _fake_sources(monkeypatch, data)
    autosync.run_once()
    monkeypatch.setattr("tunebridge.linkimport._analyse_one", lambda t: {"title": t.title, "artists": t.artists,
                        "genre": "Drum & Bass", "subgenre": "Liquid", "ids": {}})
    data["spotify"]["__liked__"] = [Track("Neu1", ["N"])]
    autosync.run_once()                                   # aus: nur Vorschlag
    assert "auto" not in autosync.inbox()[0]
    cl = TestClient(app)
    s = cl.post("/api/autosync", json={"auto_sort": True, "auto_min": 10}).json()["settings"]
    assert s["auto_sort"] and s["auto_min"] == 50         # Untergrenze 50 %
    data["spotify"]["__liked__"].append(Track("Neu2", ["M"]))
    autosync.run_once()
    item = autosync.inbox()[0]
    assert item["title"] == "Neu2" and item["auto"]["playlist"] == "Meine Liquid DnB"
    assert any(t.title == "Neu2" for p in store.local_playlists() for t in p.tracks)
    r = cl.post(f"/api/autosync/inbox/{item['id']}/undo").json()
    assert r["playlist"] == "Meine Liquid DnB"
    assert not any(t.title == "Neu2" for p in store.local_playlists() for t in p.tracks)
    assert "auto" not in autosync.inbox()[0]              # bleibt zum Selbst-Entscheiden
    assert cl.post(f"/api/autosync/inbox/{item['id']}/undo").status_code == 404


def test_auto_target_rules():
    cfg = {"auto_sort": True, "auto_min": 70}
    ok = {"playlist": "A", "score": .8, "new": False, "origin": "lokal"}
    assert autosync.auto_target([ok], cfg) == ok
    assert autosync.auto_target([{**ok, "score": .6}], cfg) is None
    assert autosync.auto_target([{**ok, "new": True}], cfg) is None
    assert autosync.auto_target([{**ok, "origin": "spotify"}], cfg) is None
    assert autosync.auto_target([ok], {**cfg, "auto_sort": False}) is None

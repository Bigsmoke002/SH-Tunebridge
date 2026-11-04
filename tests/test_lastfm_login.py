"""Last.fm-Web-Anmeldung: Signatur, Ablauf, Fehler mit klarer Meldung, Profil wird gesetzt."""
import hashlib
import os
import sys
from urllib.parse import parse_qs, urlparse

import pytest


def test_sign_matches_lastfm_spec():
    from tunebridge.lastfm_auth import sign
    p = {"method": "auth.getSession", "api_key": "K", "token": "T", "format": "json"}
    assert sign(p, "S") == hashlib.md5(b"api_keyKmethodauth.getSessiontokenTS").hexdigest()


@pytest.fixture
def lfm(monkeypatch, tmp_path):
    from tunebridge import config, lastfm_auth
    monkeypatch.setattr(config, "DATA", tmp_path)
    monkeypatch.setenv("LASTFM_API_KEY", "a" * 32)
    monkeypatch.setenv("LASTFM_SHARED_SECRET", "b" * 32)
    return lastfm_auth.LastfmLogin()


class _R:
    def __init__(self, body): self._b = body
    def json(self): return self._b


def test_login_flow(lfm, monkeypatch, tmp_path):
    import tunebridge.lastfm_auth as la
    st = lfm.login()
    u = urlparse(st["url"])
    q = parse_qs(u.query)
    assert st["url"].startswith("https://www.last.fm/api/auth/") and q["api_key"] == ["a" * 32]
    cb = q["cb"][0]
    assert cb.startswith("http://127.0.0.1:8765/api/lastfm/callback/")
    state = cb.rsplit("/", 1)[1]
    with pytest.raises(la.LastfmError):
        lfm.finish_login("tok", "falsch")                     # CSRF-Schutz
    seen = {}

    def get(url, params=None, **k):
        seen.update(params)
        return _R({"session": {"name": "DJ_Test", "key": "SK", "subscriber": 0}})
    monkeypatch.setattr(la.httpx, "get", get)
    assert lfm.finish_login("tok", state) == "DJ_Test"
    assert seen["api_sig"] == la.sign({"method": "auth.getSession", "api_key": "a" * 32, "token": "tok"}, "b" * 32)
    assert lfm.session()["name"] == "DJ_Test" and lfm.login_state()["state"] == "connected"
    f = tmp_path / "tokens" / "lastfm.json"
    if sys.platform != "win32":
        assert oct(f.stat().st_mode)[-3:] == "600"
    lfm.logout()
    assert not f.exists()


def test_wrong_secret_gives_clear_message(lfm, monkeypatch):
    import tunebridge.lastfm_auth as la
    st = lfm.login()
    state = parse_qs(urlparse(st["url"]).query)["cb"][0].rsplit("/", 1)[1]
    monkeypatch.setattr(la.httpx, "get", lambda *a, **k: _R({"error": 13, "message": "Invalid method signature supplied"}))
    with pytest.raises(la.LastfmError, match="Shared secret"):
        lfm.finish_login("tok", state)
    assert lfm.login_state()["state"] == "failed" and "Shared secret" in lfm.login_state()["error"]


def test_login_needs_secret(monkeypatch, tmp_path):
    from tunebridge import config, lastfm_auth
    monkeypatch.setattr(config, "DATA", tmp_path)
    monkeypatch.setenv("LASTFM_API_KEY", "a" * 32)
    monkeypatch.delenv("LASTFM_SHARED_SECRET", raising=False)
    monkeypatch.setattr(config, "opt", lambda k: os.environ.get(k))
    with pytest.raises(lastfm_auth.LastfmError, match="Shared secret"):
        lastfm_auth.LastfmLogin().login()

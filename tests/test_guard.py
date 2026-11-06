"""Schutz der lokalen Schnittstelle: fremde Webseiten / DNS-Rebinding abweisen, App selbst + Begleiter durchlassen."""
import os
import stat

import pytest
from fastapi.testclient import TestClient

from tunebridge.web import guard


@pytest.fixture
def strict(monkeypatch):
    monkeypatch.delenv("TUNEBRIDGE_OPEN_HOST", raising=False)


def test_check_rules(strict):
    ok = {"host": "127.0.0.1:8765"}
    assert guard.check("GET", ok) is None                                         # Begleiter, curl
    assert guard.check("POST", {**ok, "origin": "http://127.0.0.1:8765", "sec-fetch-site": "same-origin"}) is None
    assert guard.check("GET", {"host": "localhost:8765"}) is None
    assert guard.check("GET", {"host": "[::1]:8765"}) is None
    assert guard.check("GET", {"host": "evil.example:8765"}) == "fremder Host"     # DNS-Rebinding
    assert guard.check("POST", {**ok, "origin": "https://evil.example"}) == "fremde Herkunft"
    assert guard.check("POST", {**ok, "origin": "null"}) == "fremde Herkunft"
    assert guard.check("POST", {**ok, "origin": "http://localhost:3000"}) == "fremde Herkunft"   # andere lokale Seite
    assert guard.check("GET", {**ok, "sec-fetch-site": "cross-site", "sec-fetch-mode": "no-cors",
                               "sec-fetch-dest": "image"}) == "Anfrage von fremder Seite"
    # Rückleitung nach Login bei Spotify & Co.: normaler Seitenaufruf von fremder Seite ist erlaubt
    assert guard.check("GET", {**ok, "sec-fetch-site": "cross-site", "sec-fetch-mode": "navigate",
                               "sec-fetch-dest": "document"}) is None
    assert guard.check("POST", {**ok, "sec-fetch-site": "cross-site", "sec-fetch-mode": "navigate"}) is not None
    assert guard.check("GET", {**ok, "sec-fetch-site": "cross-site", "sec-fetch-mode": "navigate",
                               "sec-fetch-dest": "iframe"}) is not None
    assert guard.check("GET", {**ok, "sec-fetch-site": "cross-site"}, ws=True) is not None


def test_open_host_only_skips_host_check(monkeypatch):
    monkeypatch.setenv("TUNEBRIDGE_OPEN_HOST", "1")
    assert guard.check("GET", {"host": "192.168.1.5:8765"}) is None
    assert guard.check("POST", {"host": "192.168.1.5:8765", "origin": "http://192.168.1.5:8765"}) is None
    assert guard.check("POST", {"host": "192.168.1.5:8765", "origin": "https://evil.example"}) == "fremde Herkunft"


def test_middleware_http_and_ws(strict):
    from tunebridge.web.app import app
    c = TestClient(app, base_url="http://127.0.0.1:8765")
    assert c.get("/api/playlists").status_code == 200
    r = c.get("/api/playlists", headers={"origin": "https://evil.example"})
    assert r.status_code == 403 and "fremde Herkunft" in r.json()["detail"]
    assert TestClient(app).get("/api/playlists").status_code == 403          # Host „testserver“
    with pytest.raises(Exception):
        with c.websocket_connect("/ws/level", headers={"origin": "https://evil.example"}):
            pass


@pytest.mark.skipif(os.name != "posix", reason="Dateirechte nur unter Linux/macOS")
def test_db_and_data_dir_private(tmp_path):
    from tunebridge import config, store
    store.add_to_playlist("X", __import__("tunebridge.models", fromlist=["Track"]).Track("S", ["K"]))
    assert stat.S_IMODE(store.DB.stat().st_mode) == 0o600
    d = tmp_path / "d"
    d.mkdir(mode=0o755)
    config.private(d, 0o700)
    assert stat.S_IMODE(d.stat().st_mode) == 0o700

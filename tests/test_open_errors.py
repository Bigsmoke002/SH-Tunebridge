"""Ordner öffnen / Netzwerkfehler: verständliche Meldung statt Serverfehler (gefunden im Windows-Klicktest)."""
import pytest
from fastapi.testclient import TestClient

from tunebridge import osutil


def test_open_path_error_is_friendly(monkeypatch):
    def boom(*a, **k):
        raise OSError("[WinError -2146959355] Starten des Servers fehlgeschlagen")
    monkeypatch.setattr(osutil.subprocess, "Popen", boom)
    monkeypatch.setattr(osutil.os, "startfile", boom, raising=False)
    with pytest.raises(osutil.OpenError, match="du findest ihn hier"):
        osutil.open_path("/irgendwo")


def test_open_folder_endpoint_returns_400(monkeypatch):
    from tunebridge.web import app as webapp
    monkeypatch.setattr(osutil, "open_path", lambda p: (_ for _ in ()).throw(osutil.OpenError("Ordner ließ sich nicht öffnen")))
    r = TestClient(webapp.app).post("/api/backups/open-folder")
    assert r.status_code == 400 and "nicht öffnen" in r.json()["detail"]


def test_friendly_net_error():
    from tunebridge.web.app import _friendly_net_error
    assert "keine Verbindung" in _friendly_net_error(OSError("[WinError 10061] Es konnte keine Verbindung hergestellt werden"))
    assert "keine Verbindung" in _friendly_net_error(ConnectionRefusedError(111, "Connection refused"))
    assert "Zeitüberschreitung" in _friendly_net_error(TimeoutError("timed out"))
    assert _friendly_net_error(ValueError("HTTP 401: Invalid API Key")) == "HTTP 401: Invalid API Key"

"""Hörproben nur streamen (nie speichern) + RAM-Zwischenspeicher bleibt mit der Datenbank im Einklang."""

import time

import pytest

from tunebridge import preview, store


@pytest.fixture
def db(tmp_path, monkeypatch):
    from tunebridge import config
    monkeypatch.setattr(config, "DATA", tmp_path)
    monkeypatch.setattr(store, "DB", tmp_path / "t.db")
    store.ram_clear()
    yield store
    store.ram_clear()


def test_ram_cache_follows_db(db):
    db.cache_set("x", "k", {"a": 1})
    v = db.cache_get("x", "k")
    v["a"] = 99                                  # Aufrufer verändert seine Kopie …
    assert db.cache_get("x", "k") == {"a": 1}    # … der Speicher bleibt unberührt
    db.clear_cache("x")
    assert db.cache_get("x", "k") is None
    db.meta_set("m", "1")
    assert db.meta_get("m") == "1"
    db.bump_saved("shazam")
    assert db.saved_calls() == {"shazam": 1}


def test_preview_streams_without_saving(monkeypatch, tmp_path):
    monkeypatch.setattr(preview, "CACHE", tmp_path / "previews")
    preview._RAM.clear()
    future = int(time.time()) + 3600
    dz = f"https://cdnt-preview.dzcdn.net/api/1/1/a/b/c/x.mp3?hdnea=exp={future}~acl=*~hmac=1"
    apple = "https://audio-ssl.itunes.apple.com/itunes-assets/x.m4a"
    calls = []
    monkeypatch.setattr(preview, "_fresh_deezer_urls", lambda *a: calls.append(a) or [dz])
    # gültiger Deezer-Link: direkt, ohne Nachfrage
    assert preview.resolve(dz, None, None, "A", "T") == {"url": dz, "source": "deezer"} and not calls
    # Apple-Link, Fenster kann kein AAC -> gleiche Hörprobe bei Deezer
    assert preview.resolve(apple, "ISRC1", None, "B", "T")["source"] == "deezer"
    # Apple-Link, Fenster kann AAC -> direkt bei Apple streamen
    assert preview.resolve(apple, "ISRC2", None, "C", "T", aac=True) == {"url": apple, "source": "apple"}
    assert not (tmp_path / "previews").exists()  # nichts auf der Platte


def test_expired_deezer_link_is_renewed(monkeypatch):
    preview._RAM.clear()
    old = "https://cdnt-preview.dzcdn.net/x.mp3?hdnea=exp=1000000000~acl=*"
    new = f"https://cdnt-preview.dzcdn.net/y.mp3?hdnea=exp={int(time.time()) + 3600}~acl=*"
    monkeypatch.setattr(preview, "_fresh_deezer_urls", lambda *a: [new])
    assert preview.resolve(old, None, "123", "A", "T")["url"] == new


def test_service_playlists_ram_only(db, monkeypatch):
    """Dienst-Playlists: zweiter Abruf kommt aus dem Arbeitsspeicher, refresh lädt neu, nichts landet in der DB."""
    from fastapi.testclient import TestClient
    from tunebridge import services, store
    from tunebridge.models import Track
    from tunebridge.web import app as webapp
    calls = []
    monkeypatch.setattr(services, "load", lambda sid, pid: (calls.append(pid) or ("", [Track(title="A", artists=["X"], cover="https://cdn/x.jpg")])))
    webapp._SVC_RAM.clear()
    c = TestClient(webapp.app)
    r1 = c.get("/api/services/deezer/playlists/42/tracks").json()
    r2 = c.get("/api/services/deezer/playlists/42/tracks").json()
    assert r1 == r2 and r1["tracks"][0]["cover"] == "https://cdn/x.jpg" and calls == ["42"]
    c.get("/api/services/deezer/playlists/42/tracks?refresh=1")
    assert calls == ["42", "42"]
    assert store.cache_get("svc_tracks", "42") is None

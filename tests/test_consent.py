"""Einwilligungen: ohne Zustimmung nichts senden, nur das Nötigste, keine lokalen Pfade."""

import pytest


@pytest.fixture
def db(tmp_path, monkeypatch):
    from tunebridge import config, outbox, store
    monkeypatch.setattr(config, "DATA", tmp_path)
    monkeypatch.setattr(store, "DB", tmp_path / "t.db")
    monkeypatch.setattr(outbox, "QUEUE", tmp_path / "q.json")
    return store


def test_default_nothing_to_server_and_onboarding_needed(db):
    from tunebridge import consent
    c = consent.get()
    assert c["needs_onboarding"] and not consent.server_any()
    assert all(c["local"].values()) and not consent.server("genredb")
    assert {k for k, v in c["server"].items() if v} == {"genredb"}      # nur Laden vorausgewählt


def test_privacy_required_and_domain_required(db):
    from tunebridge import consent
    with pytest.raises(ValueError):
        consent.save({"server": {"domain": True, "misses": True}})
    c = consent.save({"privacy": True, "server": {"misses": True, "songs": True}})   # Domain fehlt
    assert not consent.server("misses") and not consent.server("songs")
    consent.save({"privacy": True, "server": {"domain": True, "fehler": True}})
    assert consent.server("fehler") and not consent.server("songs") and not consent.get()["needs_onboarding"]


def test_error_queue_only_with_consent_and_redacted(db):
    from pathlib import Path
    from tunebridge import consent, outbox
    from tunebridge import debuglog as dbg
    dbg.error("test", "kaputt", ValueError("x"))
    assert outbox.pending_errors() == []
    consent.save({"privacy": True, "server": {"domain": True, "fehler": True}})
    try:
        raise RuntimeError(f"Datei {Path.home()}/geheim fehlt")
    except RuntimeError as e:
        dbg.error("test", "kaputt", e)
        dbg.error("test", "kaputt", e)          # doppelt -> nur einmal
    q = outbox.pending_errors()
    assert len(q) == 1 and str(Path.home()) not in str(q) and q[0]["zeit"].count(":") == 0


def test_send_blocked_without_consent(db):
    from fastapi.testclient import TestClient
    from tunebridge.web import app as webapp
    db.miss_add("unerkannt", "desktop", -20.0, None, None, {})
    r = TestClient(webapp.app).post("/api/misses/send", json={})
    assert r.status_code == 403


def test_player_minimal_drops_local_paths_and_tracking():
    from tunebridge.recognize import players
    assert players.clean_url("file:///home/max/Musik/a.mp3") == ""
    assert players.clean_url("https://www.youtube.com/watch?v=abc&list=x&si=track") == "https://www.youtube.com/watch?v=abc"
    assert players.clean_url("https://soundcloud.com/a/b?utm_source=x") == "https://soundcloud.com/a/b"
    p = players.minimal({"player": "vlc", "title": "T", "trackid": "/org/x", "url": "file:///home/max/a.mp3"})
    assert "trackid" not in p and p["url"] == ""


def test_genredb_preselected_but_only_after_dialog_and_without_domain(db):
    from tunebridge import consent
    assert not consent.server("genredb")                       # vor dem Einrichtungsdialog nichts laden
    consent.save({"privacy": True, "server": {"domain": False}})
    assert consent.server("genredb") and not consent.server_any()   # Laden ok, Senden nicht
    consent.save({"privacy": True, "server": {"genredb": False}})
    assert not consent.server("genredb")                       # abwählbar
    consent.save({"privacy": True, "server": {"domain": True, "misses": True}})
    assert not consent.server("genredb") and consent.server_any()   # Abwahl bleibt erhalten

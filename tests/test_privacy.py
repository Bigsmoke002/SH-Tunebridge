"""Datenschutz: Einwilligungen werden serverseitig erzwungen, Aufnahmen nie behalten."""

import json
import sys
import wave

import pytest


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("TUNEBRIDGE_DATA", str(tmp_path))
    from tunebridge import config, store
    monkeypatch.setattr(config, "DATA", tmp_path)
    monkeypatch.setattr(store, "DB", tmp_path / "t.db", raising=False)
    from fastapi.testclient import TestClient
    from tunebridge.web import app as webapp

    rec = {"files": [], "engines": None}

    def fake_record(source, seconds):
        p = tmp_path / f"rec{len(rec['files'])}.wav"
        with wave.open(str(p), "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(8000)
            w.writeframes(b"\x10\x27" * 8000)   # laut genug, keine Stille
        rec["files"].append(p)
        return p

    async def fake_recognize(path, engines=None):
        rec["engines"] = engines
        from tunebridge.recognize.engines import Result
        return Result(None, 0, [], {})

    monkeypatch.setattr(webapp.capture, "record", fake_record)
    monkeypatch.setattr(webapp, "recognize", fake_recognize)

    async def no_variants(path, **kw):
        return None
    monkeypatch.setattr(webapp.variants, "find", no_variants)   # keine echten Shazam-Aufrufe im Test
    from tunebridge.recognize import players
    monkeypatch.setattr(players, "current", lambda: None)
    monkeypatch.setattr(webapp, "available", lambda: ["shazam", "audd", "acrcloud"])
    monkeypatch.setattr(webapp, "_prefs", lambda: {**webapp._PREF_DEFAULTS, **rec.get("prefs", {})})
    return TestClient(webapp.app), rec


def test_mic_needs_acknowledgement(client):
    c, rec = client
    r = c.post("/api/listen", json={"mode": "mic", "source": "mic", "seconds": 3})
    assert r.status_code == 403 and not rec["files"]          # gar nicht erst aufgenommen


def test_default_sends_only_fingerprint(client):
    c, rec = client
    r = c.post("/api/listen", json={"mode": "desktop", "source": "desktop", "seconds": 3})
    assert r.status_code == 200
    assert rec["engines"] == ["shazam"]                         # ohne Einwilligung kein Rohaudio
    assert all(not p.exists() for p in rec["files"])            # Aufnahme sofort gelöscht


def test_audio_only_with_consent(client):
    c, rec = client
    rec["prefs"] = {"send_audio_desktop": True, "mic_ack": True}
    c.post("/api/listen", json={"mode": "desktop", "source": "desktop", "seconds": 3})
    assert rec["engines"] is None                               # alle Dienste
    c.post("/api/listen", json={"mode": "mic", "source": "mic", "seconds": 3})
    assert rec["engines"] == ["shazam"]                         # Mikro-Einwilligung ist getrennt


def test_llm_download_needs_terms(monkeypatch):
    from tunebridge import llm
    monkeypatch.setattr(llm, "settings", lambda: {**llm.DEFAULTS})
    monkeypatch.setattr(llm, "model_path", lambda mid: __import__("pathlib").Path("/nonexistent/x.gguf"))
    with pytest.raises(PermissionError):
        llm.download_model("light")


def test_debug_log_off_by_default_and_redacted(client, tmp_path, monkeypatch):
    c, _ = client
    from tunebridge import config, debuglog
    monkeypatch.setattr(debuglog, "LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr(debuglog, "LOG_FILE", tmp_path / "logs" / "debug.log")
    monkeypatch.setattr(debuglog, "_enabled", None)
    monkeypatch.setattr(debuglog, "_handler", None)
    cfg = tmp_path / "config.env"
    cfg.write_text("LASTFM_API_KEY=abcdef1234567890geheim\n")
    monkeypatch.setattr(config, "CONFIG_FILE", cfg)

    assert c.get("/api/debug").json()["enabled"] is False          # Standard: aus
    debuglog.event("test", "darf nicht im Log landen")
    assert not (tmp_path / "logs" / "debug.log").exists()

    c.post("/api/debug", json={"enabled": True})
    debuglog.event("test", "Abruf", url="https://x/?api_key=abcdef1234567890geheim&q=1",
                   pfad=str(__import__("pathlib").Path.home() / "Musik"))
    report = c.get("/api/debug/report").text
    assert "abcdef1234567890geheim" not in report and "«geschwärzt»" in report
    assert str(__import__("pathlib").Path.home()) not in report

    c.post("/api/debug", json={"enabled": False})
    c.post("/api/debug/clear")
    assert c.get("/api/debug").json()["size"] == 0
    debuglog._handler and debuglog._handler.close()


@pytest.mark.skipif(sys.platform != "linux", reason="Einzelne Anwendungen gibt es nur unter Linux/PipeWire")
def test_voice_chat_apps_never_offered(monkeypatch):
    from tunebridge.recognize import capture
    dump = [{"type": "PipeWire:Interface:Node", "info": {"props": p}} for p in [
        {"media.class": "Stream/Output/Audio", "application.name": "Firefox", "application.process.binary": "firefox", "object.serial": 1},
        {"media.class": "Stream/Output/Audio", "application.name": "WEBRTC VoiceEngine", "application.process.binary": "Discord", "object.serial": 2},
        {"media.class": "Stream/Output/Audio", "application.name": "Zoom", "object.serial": 3},
        {"media.class": "Stream/Output/Audio", "application.name": "Spotify", "media.role": "Communication", "object.serial": 4},
        {"media.class": "Stream/Output/Audio", "application.name": "nvbroadcast", "media.name": "nvbroadcast mic output", "object.serial": 5},
        {"media.class": "Stream/Output/Audio", "application.name": "Spotify", "application.process.binary": "spotify", "object.serial": 6},
    ]]
    monkeypatch.setattr(capture, "pipewire_ok", lambda: True)
    monkeypatch.setattr(capture.subprocess, "run", lambda *a, **k: type("R", (), {"stdout": json.dumps(dump)})())
    assert [a.name for a in capture.apps()] == ["app:firefox", "app:spotify"]


# ------------------------------------------------------------------ Netzwerke erkennen (Handy-Abgleich)
def _fake_adapters(monkeypatch):
    import types

    import ifaddr
    calls = []

    def get_adapters():
        calls.append(1)
        ip = types.SimpleNamespace(ip="192.168.1.20", network_prefix=24)
        return [types.SimpleNamespace(name="eth0", nice_name="eth0", ips=[ip])]
    monkeypatch.setattr(ifaddr, "get_adapters", get_adapters)
    return calls


def test_networks_not_read_without_consent(monkeypatch):
    from tunebridge import phone
    monkeypatch.setattr(phone, "ensure_server", lambda force=False: None)
    calls = _fake_adapters(monkeypatch)
    phone._nets_cache.update(t=0.0, v=[])
    assert phone._load()["net_consent"] is False                 # Standard: keine Zustimmung
    assert phone.networks(fresh=True) == [] and phone.addresses() == []
    assert calls == []                                            # Netzwerkkarten gar nicht ausgelesen
    with pytest.raises(phone.PhoneError) as e:
        phone.start_pairing()
    assert e.value.status == 403
    assert not phone._allowed("192.168.1.50")                     # Handy-Anfragen abgewiesen
    st = phone.set_net_consent(True)
    assert st["net_consent"] is True and st["addresses"] == ["192.168.1.20:8766"] and calls
    st = phone.set_net_consent(False)                             # Widerruf wirkt sofort
    assert st["net_consent"] is False and st["networks"] == [] and st["pairing"] is None


def test_net_consent_api(client, monkeypatch):
    from tunebridge import phone
    monkeypatch.setattr(phone, "ensure_server", lambda force=False: None)
    _fake_adapters(monkeypatch)
    c = client[0] if isinstance(client, tuple) else client
    assert c.post("/api/phone/pair").status_code == 403
    assert c.post("/api/phone/net-consent", json={"ok": True}).json()["net_consent"] is True
    assert c.post("/api/phone/pair").status_code == 200
    assert c.post("/api/phone/net-consent", json={"ok": False}).json()["networks"] == []

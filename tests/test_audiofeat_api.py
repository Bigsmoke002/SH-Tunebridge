"""/api/audiofeat: Tempo/Tonart/Energie für ähnliche Songs – nur die vier Werte, {} ohne Hörprobe."""
from fastapi.testclient import TestClient

from tunebridge import audiofeat
from tunebridge.web.app import app


def test_audiofeat_by_artist_title(monkeypatch):
    seen = []

    def fake(t, deezer_bpm=None, refresh=False):
        seen.append((t.artist, t.title, t.isrc, t.ids))
        return {"bpm": 128.0, "bpm_conf": .9, "camelot": "8A", "key": "Am", "key_conf": .7, "energy": .62}
    monkeypatch.setattr(audiofeat, "features", fake)
    c = TestClient(app)
    r = c.get("/api/audiofeat", params={"artist": "Kavinsky", "title": "Nightcall", "isrc": "frxyz", "dz": "123"}).json()
    assert r == {"bpm": 128.0, "camelot": "8A", "key": "Am", "energy": .62}
    assert seen == [("Kavinsky", "Nightcall", "FRXYZ", {"deezer": "123"})]


def test_audiofeat_without_preview_and_missing_song(monkeypatch):
    monkeypatch.setattr(audiofeat, "features", lambda t, deezer_bpm=None, refresh=False: None)
    c = TestClient(app)
    assert c.get("/api/audiofeat", params={"artist": "X", "title": "Y"}).json() == {}
    assert c.get("/api/audiofeat").status_code == 400
    assert c.get("/api/audiofeat", params={"artist": "X", "title": "Y", "dz": "abc"}).status_code == 200

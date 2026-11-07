"""Playlists in andere Playlists übernehmen (Nutzer-Meldung: „Playlist lässt sich nicht in eine andere importieren“)."""
from urllib.parse import quote

from fastapi.testclient import TestClient

from tunebridge import services, store
from tunebridge.models import Track
from tunebridge.web.app import app

c = TestClient(app)
q = lambda n: quote(n, safe="")  # noqa: E731


def _titles(name):
    return [e["track"]["title"] for e in store.playlist_entries(name)][::-1]   # Liste kommt neueste zuerst


def test_merge_local_into_existing_skips_dupes_keeps_order():
    for t in ("A", "B"):
        store.add_to_playlist("Ziel", Track(t, ["K"]))
    for t in ("B", "C", "D"):
        store.add_to_playlist("Quelle / Mix", Track(t, ["K"]))
    r = c.post(f"/api/playlists/{q('Ziel')}/merge", json={"src": "local", "src_id": "Quelle / Mix"})
    assert r.status_code == 200
    assert r.json() == {"name": "Ziel", "added": 2, "dupes": 1, "total": 3}
    assert _titles("Ziel") == ["A", "B", "C", "D"]
    assert _titles("Quelle / Mix") == ["B", "C", "D"]          # Quelle bleibt unverändert


def test_merge_into_new_playlist_and_errors():
    store.add_to_playlist("Quelle", Track("A", ["K"]))
    assert c.post(f"/api/playlists/{q('Neu')}/merge", json={"src": "local", "src_id": "Quelle"}).json()["added"] == 1
    assert _titles("Neu") == ["A"]
    assert c.post(f"/api/playlists/{q('Quelle')}/merge", json={"src": "local", "src_id": "Quelle"}).status_code == 400
    assert c.post(f"/api/playlists/{q('Neu')}/merge", json={"src": "local", "src_id": "Gibt es nicht"}).status_code == 404


def test_merge_from_service(monkeypatch):
    monkeypatch.setattr(services, "load", lambda sid, pid: ("X", [Track("S1", ["K"]), Track("S2", ["K"])]))
    r = c.post(f"/api/playlists/{q('Ziel')}/merge", json={"src": "tidal", "src_id": "123"})
    assert r.status_code == 200 and r.json()["added"] == 2
    assert _titles("Ziel") == ["S1", "S2"]

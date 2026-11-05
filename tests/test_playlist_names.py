"""Playlists mit „/“ im Namen (z. B. „Ambient / Chill“) – vorher 404 „Not Found“ beim Öffnen."""
from urllib.parse import quote

from fastapi.testclient import TestClient

from tunebridge import store
from tunebridge.models import Track
from tunebridge.web.app import app


def test_slash_in_playlist_name():
    c = TestClient(app)
    name = "Ambient / Chill – Lo-Fi"
    store.add_to_playlist(name, Track("S", ["K"], genre="Ambient"))
    r = c.get(f"/api/playlists/{quote(name, safe='')}")
    assert r.status_code == 200 and r.json()["name"] == name and len(r.json()["entries"]) == 1
    assert c.post(f"/api/playlists/{quote(name, safe='')}/rename", json={"new": "Rock / Metal"}).status_code == 200
    assert len(store.playlist_entries("Rock / Metal")) == 1
    assert c.delete(f"/api/playlists/{quote('Rock / Metal', safe='')}").status_code == 200
    assert store.playlist_entries("Rock / Metal") == []

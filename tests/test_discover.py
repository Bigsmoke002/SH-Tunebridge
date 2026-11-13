"""Entdecken: Deezer-Antworten -> einheitliche Einträge; Schnittstellen am PC (ohne Netz)."""
import pytest
from fastapi.testclient import TestClient

from tunebridge import discover

TRACK = {"id": 11, "title": "Come Alive (VIP)", "title_short": "Come Alive", "duration": 250, "rank": 5, "preview": "https://p",
         "artist": {"id": 3, "name": "Netsky"}, "album": {"id": 9, "title": "2", "cover_medium": "https://c/9"},
         "contributors": [{"id": 3, "name": "Netsky"}, {"id": 4, "name": "Jenna G"}], "isrc": "GBXXX1200001"}


@pytest.fixture
def fake(monkeypatch):
    discover._RAM.clear()
    calls = []

    def get(url, **params):
        calls.append((url, params))
        if url.endswith("/search/track"):
            return {"data": [TRACK, {"id": None}]}
        if url.endswith("/search/artist"):
            return {"data": [{"id": 3, "name": "Netsky", "picture_medium": "https://a", "nb_fan": 10}]}
        if url.endswith("/search/album"):
            return {"data": [{"id": 9, "title": "2", "artist": {"id": 3, "name": "Netsky"}, "record_type": "album",
                              "release_date": "2012-06-01"}]}
        if url.endswith("/artist/3"):
            return {"id": 3, "name": "Netsky", "nb_fan": 10, "nb_album": 2}
        if url.endswith("/artist/3/top"):
            return {"data": [TRACK, TRACK]}
        if url.endswith("/artist/3/albums"):
            return {"data": [{"id": 9, "title": "2", "record_type": "album", "release_date": "2012-06-01"},
                             {"id": 10, "title": "Single", "record_type": "single", "release_date": "2020-01-01"}]}
        if url.endswith("/artist/3/related"):
            return {"data": [{"id": 5, "name": "Camo & Krooked"}]}
        if url.endswith("/album/9"):
            return {"id": 9, "title": "2", "record_type": "album", "release_date": "2012-06-01", "cover_medium": "https://c/9",
                    "artist": {"id": 3, "name": "Netsky"}, "genres": {"data": [{"name": "Dance"}]},
                    "tracks": {"data": [{"id": 12, "title": "Love Has Gone", "duration": 200, "preview": "",
                                         "artist": {"id": 3, "name": "Netsky"}}]}}
        if "/chart/" in url:
            return {"data": [TRACK]} if url.endswith("/tracks") else {"data": []}
        if url.endswith("/genre"):
            return {"data": [{"id": 0, "name": "Alle"}, {"id": 457, "name": "Hörbücher"}, {"id": 113, "name": "Dance"}]}
        return {"error": {"code": 800}}
    monkeypatch.setattr(discover, "_get", get)
    return calls


def test_track_item_keeps_all_artists_and_version(fake):
    it = discover.search("netsky", "track")["items"]
    assert len(it) == 1
    t = it[0]
    assert t["title"] == "Come Alive (VIP)" and t["artists"] == ["Netsky", "Jenna G"]
    assert t["preview_url"] == "deezer:11" and t["ids"] == {"deezer": "11"} and t["cover"] == "https://c/9"


def test_search_validates_and_caches(fake):
    assert discover.search("   ", "track")["items"] == []
    with pytest.raises(ValueError):
        discover.search("x", "podcast")
    discover.search("Netsky ", "track")
    discover.search("netsky", "track")
    assert len([c for c in fake if c[0].endswith("/search/track")]) == 1      # zweite Suche aus dem Speicher
    assert discover.search("x" * 300, "track")["q"] == "x" * 100


def test_artist_album_charts_genres(fake):
    a = discover.artist_page("3")
    assert a["artist"]["name"] == "Netsky" and len(a["top"]) == 1 and a["top"][0]["with"] == ["Jenna G"]
    assert [x["title"] for x in a["albums"]] == ["2"] and [x["title"] for x in a["singles"]] == ["Single"]
    assert a["related"][0]["name"] == "Camo & Krooked"
    al = discover.album_page(9)
    assert al["album"]["genres"] == ["Dance"] and al["tracks"][0]["cover"] == "https://c/9" and al["tracks"][0]["preview_url"] is None
    assert discover.charts(0)["tracks"][0]["title"] == "Come Alive (VIP)"
    assert [g["name"] for g in discover.genres()] == ["Alle", "Dance"]
    with pytest.raises(ValueError):
        discover.artist_page("1; drop")
    with pytest.raises(LookupError):
        discover.album_page(1)


def test_api_endpoints(fake):
    from tunebridge.web.app import app
    c = TestClient(app, base_url="http://127.0.0.1:8765")
    r = c.get("/api/discover/search", params={"q": "netsky"}).json()
    assert r["tracks"][0]["links"] and r["artists"][0]["id"] == 3
    assert c.get("/api/discover/artist/3").json()["top"][0]["links"]
    assert c.get("/api/discover/artist/abc").status_code == 400
    assert c.get("/api/discover/album/1").status_code == 404
    assert c.get("/api/discover/charts").json()["tracks"]
    assert "links" not in discover.charts(0)["tracks"][0]                   # Zwischenspeicher unverändert
    r = c.post("/api/versions/add", json={"playlist": "Entdeckt", "track": {**r["tracks"][0], "artists": [f"A{i}" for i in range(12)]}})
    assert r.json()["added"]
    from tunebridge import store
    saved = [p for p in store.local_playlists() if p.name == "Entdeckt"][0].tracks[0]
    assert len(saved.artists) == 12                                     # alle Interpreten bleiben erhalten (vorher 5)


def test_save_many_to_playlist(fake):
    from tunebridge import store
    from tunebridge.web.app import app
    c = TestClient(app, base_url="http://127.0.0.1:8765")
    al = c.get("/api/discover/album/9").json()
    tr = c.get("/api/discover/search", params={"q": "netsky", "kind": "track"}).json()["items"]
    r = c.post("/api/discover/save", json={"playlist": "Album 2", "tracks": al["tracks"] + tr + tr}).json()
    assert r == {"added": 2, "skipped": 1, "playlist": "Album 2"}
    saved = [p for p in store.local_playlists() if p.name == "Album 2"][0].tracks
    assert saved[1].isrc == "GBXXX1200001" and saved[1].artists == ["Netsky", "Jenna G"]
    assert c.post("/api/discover/save", json={"playlist": "x", "tracks": []}).status_code == 400
    assert c.post("/api/discover/save", json={"playlist": "x", "tracks": [{"title": "", "artists": []}]}).status_code == 400

"""Globale Suche: Songs in Playlists und Verlauf, Groß/klein auch bei Umlauten, Sonderzeichen ohne SQL-Wirkung."""
from fastapi.testclient import TestClient

from tunebridge import store
from tunebridge.models import Track
from tunebridge.web.app import app


def test_search_songs_history_and_umlauts():
    store.add_to_playlist("Abend", Track(title="Über den Wolken", artists=["Reinhard Mey"], isrc="DEA111111111"))
    store.add_to_playlist("Morgen", Track(title="Über den Wolken", artists=["Reinhard Mey"], isrc="DEA111111111"))
    store.add_to_playlist("Abend", Track(title="100% Pure Love", artists=["Crystal Waters"]))
    store.add_recognition("test", "shazam", 1, Track(title="Nightcall", artists=["Kavinsky"]), {})
    c = TestClient(app)
    r = c.get("/api/search", params={"q": "über mey"}).json()
    assert [s["title"] for s in r["songs"]] == ["Über den Wolken"] and sorted(r["songs"][0]["playlists"]) == ["Abend", "Morgen"]
    assert c.get("/api/search", params={"q": "ÜBER"}).json()["songs"]
    assert [s["title"] for s in c.get("/api/search", params={"q": "100%"}).json()["songs"]] == ["100% Pure Love"]
    assert c.get("/api/search", params={"q": "%"}).json() == {"songs": [], "history": []}      # zu kurz
    assert c.get("/api/search", params={"q": "_%_"}).json()["songs"] == []
    assert [h["title"] for h in c.get("/api/search", params={"q": "kavinsky night"}).json()["history"]] == ["Nightcall"]


def test_playlists_have_times():
    store.add_to_playlist("Alt", Track(title="A", artists=["X"]))
    store.add_to_playlist("Neu", Track(title="B", artists=["Y"]))
    pls = {p["name"]: p for p in TestClient(app).get("/api/playlists").json()}
    assert pls["Neu"]["updated"] >= pls["Alt"]["updated"] > 0 and pls["Alt"]["created"] > 0

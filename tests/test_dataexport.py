"""Offizielle Datenexporte (Spotify-Kontodaten, Google Takeout, Apple-Mediathek) einlesen – ohne Netz."""
import io
import json
import plistlib
import time
import zipfile

import pytest

from tunebridge import dataexport, services
from tunebridge.models import Track


def _zip(files: dict) -> bytes:
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in files.items():
            z.writestr(name, data if isinstance(data, (bytes, str)) else json.dumps(data))
    return b.getvalue()


SPOTIFY = _zip({
    "Spotify Account Data/Playlist1.json": {"playlists": [
        {"name": "Hardtekk Bretter", "lastModifiedDate": "2026-10-01", "items": [
            {"track": {"trackName": "AGAINST", "artistName": "Kloud", "albumName": "AG",
                       "trackUri": "spotify:track:4uLU6hMCjMI75M1A2tKUQC"}, "episode": None, "localTrack": None},
            {"track": None, "episode": {"episodeName": "Podcast"}, "localTrack": None}]},
        {"name": "Leer", "items": []}]},
    "Spotify Account Data/YourLibrary.json": {"tracks": [
        {"artist": "Netsky", "album": "2", "track": "Rio", "uri": "spotify:track:1111111111111111111111"}]},
    "Spotify Account Data/StreamingHistory_music_0.json": [{"artistName": "X", "trackName": "Y", "msPlayed": 1}],
    "Spotify Account Data/SearchQueries.json": [{"searchQuery": "geheim"}],
})


def test_spotify_account_data():
    r = dataexport.parse("my_spotify_data.zip", SPOTIFY)
    assert r["service"] == "spotify"
    assert [p["name"] for p in r["playlists"]] == ["Hardtekk Bretter"]            # leere Liste übersprungen
    t = r["playlists"][0]["tracks"]
    assert len(t) == 1 and (t[0].artists, t[0].title, t[0].ids) == (["Kloud"], "AGAINST", {"spotify": "4uLU6hMCjMI75M1A2tKUQC"})
    assert [x.title for x in r["liked"]] == ["Rio"]
    # Hörverlauf/Suchen werden nicht gelesen
    assert "geheim" not in json.dumps([vars(x) for p in r["playlists"] for x in p["tracks"]])


def test_takeout_youtube(monkeypatch):
    from tunebridge import linkimport
    lib = "Video ID,Song Title,Album Title,Artist Name 1,Artist Name 2\nabcdefghijk,Close Eyes,Close Eyes,DVRST,\n"
    pl = "Video-ID,Zeitstempel der Erstellung des Playlist-Videos\nzzzzzzzzzzz,2025-01-01\nyyyyyyyyyyy,2025-01-02\n"
    data = _zip({"Takeout/YouTube und YouTube Music/Musikbibliothek-Songs.csv": lib,
                 "Takeout/YouTube und YouTube Music/playlists/Phonk Nacht-videos.csv": pl,
                 "Takeout/YouTube und YouTube Music/playlists/playlists.csv": "Playlist-ID,Titel\nPL1,Phonk Nacht\n"})
    r = dataexport.parse("takeout.zip", data)
    assert r["service"] == "youtube" and r["liked"][0].artists == ["DVRST"]
    assert r["pending"] == [{"name": "Phonk Nacht", "video_ids": ["zzzzzzzzzzz", "yyyyyyyyyyy"]}]
    calls = []

    def fake(kind, vid):
        calls.append(vid)
        if vid == "yyyyyyyyyyy":
            raise linkimport.LinkError("privat")
        return "", [Track(title="Murder In My Mind", artists=["Kordhell"], ids={"youtube": vid})]
    monkeypatch.setattr(linkimport, "_youtube", fake)
    jid = dataexport.start("youtube", "takeout.zip", data)
    for _ in range(100):
        if dataexport.job(jid)["state"] in ("done", "error"):
            break
        time.sleep(0.02)
    j = dataexport.job(jid)
    assert j["state"] == "done", j
    assert j["result"]["playlists"] == 1 and j["result"]["liked"] == 1
    name, tracks = dataexport.load("youtube", "p0")
    assert name == "Phonk Nacht" and [t.title for t in tracks] == ["Murder In My Mind"]   # private übersprungen


def test_apple_library_all_playlists():
    lib = plistlib.dumps({"Tracks": {"1": {"Name": "Sahara", "Artist": "Hensonn", "Loved": True},
                                     "2": {"Name": "Why Not", "Artist": "Ghostface Playa"}},
                          "Playlists": [{"Name": "Mediathek", "Master": True, "Playlist Items": [{"Track ID": 1}]},
                                        {"Name": "Musik", "Distinguished Kind": 4, "Playlist Items": [{"Track ID": 1}]},
                                        {"Name": "Phonk", "Playlist Items": [{"Track ID": 2}, {"Track ID": 1}]},
                                        {"Name": "Drift", "Playlist Items": [{"Track ID": 2}]}]})
    r = dataexport.parse("Mediathek.xml", lib)
    assert r["service"] == "apple" and [p["name"] for p in r["playlists"]] == ["Phonk", "Drift"]
    assert [t.title for t in r["liked"]] == ["Sahara"]


def test_single_csv_still_works():
    r = dataexport.parse("liste.csv", b'"Track Name","Artist Name(s)"\n"SICKO MODE","Travis Scott"\n')
    assert r["playlists"][0]["name"] == "liste" and r["playlists"][0]["tracks"][0].title == "SICKO MODE"


def test_wrong_service_and_garbage():
    jid = dataexport.start("youtube", "spotify.zip", SPOTIFY)
    for _ in range(100):
        if dataexport.job(jid)["state"] in ("done", "error"):
            break
        time.sleep(0.02)
    assert "Spotify" in dataexport.job(jid)["error"]
    with pytest.raises(dataexport.ExportError):
        dataexport.parse("x.zip", b"PK\x03\x04kaputt")
    with pytest.raises(dataexport.ExportError):
        dataexport.parse("leer.zip", _zip({"a/readme.txt": "hallo"}))


def test_zip_bomb_guard(monkeypatch):
    monkeypatch.setattr(dataexport, "MAX_TOTAL", 1000)
    big = _zip({f"Spotify Account Data/Playlist{i}.json": {"playlists": [], "pad": "x" * 600} for i in range(3)})
    with pytest.raises(dataexport.ExportError, match="zu groß"):
        dataexport.parse("s.zip", big)


def test_services_use_import_until_connected():
    r = dataexport.parse("s.zip", SPOTIFY)
    dataexport.save("spotify", r, "s.zip")
    ov = {s["id"]: s for s in services.overview(lambda sid: (False, None))}
    assert ov["spotify"]["ready"] and ov["spotify"]["mode"] == "import" and ov["spotify"]["import"]["playlists"] == 1
    assert ov["apple"]["needs"] == "import" and not ov["apple"]["ready"]
    lists = services.playlists("spotify")
    assert lists[0]["id"] == "__liked__" and lists[1]["name"] == "Hardtekk Bretter"
    assert services.load("spotify", "p0")[1][0].title == "AGAINST"
    dataexport.remove("spotify")
    assert dataexport.info("spotify") is None


def test_import_api():
    from fastapi.testclient import TestClient

    from tunebridge.web.app import app
    c = TestClient(app)
    r = c.post("/api/services/spotify/import?name=my_spotify_data.zip", content=SPOTIFY,
               headers={"Content-Type": "application/octet-stream"})
    jid = r.json()["job"]
    for _ in range(100):
        j = c.get(f"/api/services/import/{jid}").json()
        if j["state"] in ("done", "error"):
            break
        time.sleep(0.02)
    assert j["state"] == "done"
    assert c.get("/api/services/spotify/playlists").json()[1]["name"] == "Hardtekk Bretter"
    assert c.post("/api/services/tidal/import", content=b"x").status_code == 400
    assert c.delete("/api/services/spotify/import").json()["ok"]

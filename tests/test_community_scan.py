"""Gemeinschaft (Bibliothek beitragen, Modus) und „Alles einlesen“."""
import time

import pytest

from tunebridge import community, consent, outbox, scanall, services, store
from tunebridge.models import Track


def _song(artist, title, genre, isrc=None):
    t = {"title": title, "artists": [artist], "isrc": isrc, "genre": genre}
    store.song_put([isrc or f"{artist.lower()}|{title.lower()}"], t, {"confidence": 0.9, "genre_source": "tags"})


def _mb(artist, title, tags):
    store.cache_set("musicbrainz", f"{artist.lower()}|{title.lower()}", {"recording": tags, "release_group": {}, "artist": {}})


def _allow(**kw):
    consent.save({"privacy": True, "server": {"domain": True, **kw}})


# ------------------------------------------------------------------ Bibliothek beitragen
def test_lib_entries_only_free_sources_and_agreement():
    _song("Kanine", "Surrender", "Drum & Bass", "GB0001")
    _mb("kanine", "surrender", {"drum and bass": 5})
    _song("Ohne", "MB", "Techno")                         # nie bei MusicBrainz nachgeschlagen -> nicht senden
    _song("Streit", "Fall", "Trance")
    _mb("streit", "fall", {"dubstep": 5})                 # freie Quelle sagt etwas anderes -> nicht senden
    e = community.lib_entries()
    assert [x["song"]["title"] for x in e] == ["Surrender"]
    d = e[0]["details"]
    assert d["herkunft"] == "bibliothek" and d["genre"] == "Drum & Bass" and d["quelle"] == "musicbrainz"
    assert set(e[0]) >= {"uid", "zeit", "art", "song", "details"} and "playlist" not in str(e[0]).lower()


def test_own_vote_wins_and_sent_not_repeated(monkeypatch):
    from tunebridge import genredb
    _song("A", "Eins", "Drum & Bass")
    _mb("a", "eins", {"drum and bass": 5})
    _song("B", "Zwei", "Drum & Bass")
    _mb("b", "zwei", {"drum and bass": 5})
    genredb.vote(["A"], "Eins", None, "Techno", None, "korrektur")
    assert [x["song"]["title"] for x in community.lib_entries()] == ["Zwei"]
    sent = []
    monkeypatch.setattr("tunebridge.upload.send", lambda pkg: sent.append(pkg) or {"angenommen": len(pkg["eintraege"])})
    _allow(bibliothek=True)
    assert community.sync()["bibliothek"] == 1
    assert community.lib_entries() == [] and community.lib_sent_count() == 1
    assert all("_key" not in x for x in sent[0]["eintraege"])         # interne Felder gehen nicht raus


def test_lib_limits(monkeypatch):
    for i in range(5):
        _song("K", f"S{i}", "Drum & Bass")
        _mb("k", f"s{i}", {"drum and bass": 5})
    assert len(community.lib_entries(3)) == 3                    # pro Abgleich begrenzt …
    assert len(community.lib_entries(None)) == 5                 # … insgesamt nicht
    sent = []
    monkeypatch.setattr("tunebridge.upload.send", lambda pkg: sent.append(pkg) or {"angenommen": len(pkg["eintraege"])})
    monkeypatch.setattr(community, "LIB_PER_SYNC", 2)
    _allow(bibliothek=True)
    for _ in range(3):
        community.sync()
    assert community.lib_sent_count() == 5 and community.lib_entries(None) == []


def test_sync_needs_consent():
    with pytest.raises(PermissionError):
        community.sync()


def test_manual_mode_skips_background(monkeypatch):
    calls = []
    monkeypatch.setattr(community, "send_part", lambda done, force_db=False: calls.append(force_db))
    community.set_mode("manuell")
    outbox.flush(auto=True)
    assert calls == []
    outbox.flush()                     # „Jetzt senden“ unter Datenschutz nimmt alles mit
    community.set_mode("auto")
    outbox.flush(auto=True)
    assert len(calls) == 2


def test_api(monkeypatch):
    from fastapi.testclient import TestClient
    from tunebridge.web.app import app
    c = TestClient(app)
    assert c.get("/api/community").json()["mode"] == "auto"
    assert c.post("/api/community/mode", json={"mode": "manuell"}).json() == {"mode": "manuell"}
    assert c.post("/api/community/mode", json={"mode": "x"}).status_code == 400
    assert c.post("/api/community/sync").status_code == 403


# ------------------------------------------------------------------ Alles einlesen
def test_parse():
    assert scanall.parse("spotify,friend-x,tidal|liked,followed,bogus") == (["spotify", "tidal"], {"liked", "followed"})
    assert scanall.parse("youtube|") == (["youtube"], {"liked", "own"})


def test_collect_dedupe_limits_and_errors(monkeypatch):
    monkeypatch.setattr(scanall, "PAUSE_S", 0)
    lists = {"spotify": [{"id": "__liked__", "name": "Lieblingssongs"}, {"id": "p1", "name": "Meins", "own": True},
                         {"id": "p2", "name": "Fremd", "own": False}, {"id": "bad", "name": "Kaputt", "own": True}],
             "tidal": [{"id": "t1", "name": "Tidal-Liste", "own": True}]}
    songs = {"__liked__": [Track("A", ["X"], isrc="isrc1"), Track("B", ["Y"])],
             "p1": [Track("A (Remaster)", ["X"], isrc="ISRC1"), Track("C", ["Z"])],
             "p2": [Track("D", ["W"])], "t1": [Track("b", ["y"], ids={"tidal": "9"})]}

    def load(sid, pid):
        if pid == "bad":
            raise services.ServiceError("Playlist ist privat")
        return "", [Track(t.title, list(t.artists), isrc=t.isrc, ids=dict(t.ids)) for t in songs[pid]]
    monkeypatch.setattr(services, "playlists", lambda sid: lists[sid])
    monkeypatch.setattr(services, "load", load)
    job = {"cancel": False}
    name, tracks = scanall.collect("spotify,tidal|liked,own", job)
    assert sorted(t.title for t in tracks) == ["A", "B", "C"]          # D (gefolgt) nicht, Doppelte zusammengeführt
    b = next(t for t in tracks if t.title == "B")
    assert b.ids.get("tidal") == "9"                                  # IDs aus beiden Diensten
    sc = job["scan"]
    assert sc["n"] == 4 and sc["lists"] == 3 and sc["doppelt"] == 2 and len(sc["fehler"]) == 1
    assert "Spotify" in name and "TIDAL" in name
    monkeypatch.setattr(scanall, "MAX_TRACKS", 2)
    job = {"cancel": False}
    _, tracks = scanall.collect("spotify|liked,own,followed", job)
    assert len(tracks) == 2 and job["scan"]["gekappt"]


def test_sort_job_with_all(monkeypatch):
    monkeypatch.setattr(scanall, "collect", lambda spec, job: ("Alles aus Spotify", [Track("A", ["X"])]))
    monkeypatch.setattr("tunebridge.linkimport._analyse_one",
                        lambda t: {"title": t.title, "artist": t.artists[0], "artists": t.artists, "ids": {}, "genre": "Pop"})
    monkeypatch.setattr("tunebridge.audiofeat.features", lambda *a, **k: None)
    jid = services.start("__all__", "spotify|liked")
    for _ in range(50):
        if services.job(jid)["state"] in ("done", "error"):
            break
        time.sleep(0.05)
    j = services.job(jid)
    assert j["state"] == "done" and j["name"] == "Alles aus Spotify" and j["items"][0]["genre"] == "Pop"

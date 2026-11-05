"""Statistik & Jahresrückblick."""
import time
from datetime import datetime

from tunebridge import stats, store
from tunebridge.models import Track


def _at(y, m):
    return datetime(y, m, 15, 12).timestamp()


def test_overview_year_sources_new_artists(monkeypatch):
    now = [0.0]
    # Nur die Uhr verstellen – NIE monkeypatch.undo(): das würde auch die Test-Isolierung (conftest) aufheben
    with monkeypatch.context() as m:
        m.setattr(time, "time", lambda: now[0])
        for when, pl, t in [(_at(2025, 3), "A", Track("Alt", ["Künstler Eins"], genre="Techno", subgenre="Peak Time")),
                            (_at(2026, 2), "A", Track("Neu1", ["Künstler Eins"], genre="Techno", subgenre="Schranz")),
                            (_at(2026, 2), "A", Track("Neu2", ["Zwei & Drei"], genre="House")),
                            (_at(2026, 5), "B", Track("Neu2", ["Zwei & Drei"], genre="House"))]:   # gleicher Song, 2. Playlist
            now[0] = when
            store.add_to_playlist(pl, t)
    store.cache_set("audiofeat", store.track_key(Track("Neu1", ["Künstler Eins"])), {"bpm": 147})
    d = stats.overview(2026, "playlists")
    assert d["years"] == [2026, 2025]
    assert d["zahlen"]["eintraege"] == 3 and d["zahlen"]["songs"] == 2
    assert d["zahlen"]["neue_kuenstler"] == 1                     # „Künstler Eins“ gab es schon 2025
    assert d["kuenstler"][0] == {"name": "Zwei", "n": 2}
    assert d["monate"][1]["n"] == 2 and d["monate"][1]["neu"] == 1 and d["monate"][4]["n"] == 1
    assert d["tempo"] == [{"von": 140, "n": 1}]
    a = stats.overview(None, "alle")
    assert a["zahlen"]["songs"] == 3 and a["monate"] is None and a["zahlen"]["eintraege"] == 3
    assert stats.overview(2026, "erkannt")["zahlen"]["eintraege"] == 0


def test_api(monkeypatch):
    from fastapi.testclient import TestClient
    from tunebridge.web.app import app
    store.add_to_playlist("X", Track("S", ["K"], genre="Pop"))
    d = TestClient(app).get("/api/stats", params={"source": "alle", "year": ""}).json()
    assert d["zahlen"]["songs"] == 1 and d["genres"] == [{"genre": "Pop", "n": 1}]

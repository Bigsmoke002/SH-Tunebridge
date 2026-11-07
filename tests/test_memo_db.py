"""Gemerkte Auswertungen müssen nach jeder Änderung an der Datenbank neu gerechnet werden."""

import sqlite3

from tunebridge import stats, store
from tunebridge.models import Track


def _t(i, genre="House"):
    return Track(title=f"Song {i}", artists=[f"Artist {i}"], genre=genre, cover=f"https://img/{i}.jpg")


def test_playlist_overview_nach_aenderung_neu():
    store.add_to_playlist("A", _t(1))
    first = store.playlist_overview()
    assert first[0]["count"] == 1
    first[0]["count"] = 99                         # Kopie verändern darf den Speicher nicht verfälschen
    assert store.playlist_overview()[0]["count"] == 1
    store.add_to_playlist("A", _t(2, "Techno"))
    o = store.playlist_overview()[0]
    assert o["count"] == 2 and o["covers"] == ["https://img/1.jpg", "https://img/2.jpg"]
    store.remove_from_playlist("A", store.track_key(_t(1)))
    assert store.playlist_overview()[0]["count"] == 1


def test_playlist_overview_wie_vorher():
    from tunebridge.web.app import _dist
    for i, g in enumerate(["House", "Techno", "House", None, "Techno", "House"]):
        store.add_to_playlist("B", _t(i, g))
    store.add_to_playlist("Leer", _t(0))
    store.remove_from_playlist("Leer", store.track_key(_t(0)))
    new = {p["name"]: p for p in store.playlist_overview()}
    for p in store.local_playlists():
        old_top = [(d["genre"], d["subgenre"], d["count"]) for d in _dist(p.tracks)[:3]]
        assert new[p.name]["count"] == len(p.tracks)
        assert new[p.name]["top"] == old_top
        assert new[p.name]["covers"] == [t.cover for t in p.tracks if t.cover][-4:]


def test_statistik_nach_neuer_erkennung():
    assert stats.overview()["zahlen"]["eintraege"] == 0
    store.add_recognition("desktop", "test", 1, _t(1), {})
    assert stats.overview()["zahlen"]["eintraege"] == 1


def test_fremder_schreiber_wird_bemerkt():
    store.add_to_playlist("A", _t(1))
    assert store.playlist_overview()[0]["count"] == 1
    c = sqlite3.connect(store.DB)                  # z. B. Begleiter oder Kommandozeile – anderer Prozess
    c.execute("DELETE FROM entries")
    c.commit()
    c.close()
    assert store.playlist_overview()[0]["count"] == 0

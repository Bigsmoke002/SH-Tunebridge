"""Sortier-Vorschau: Korrekturen merken, KI nur für Unsortierte, Grund bei fehlendem Genre."""
import time

import pytest

from tunebridge import genredb, linkimport, services
from tunebridge.models import Track


def _job(items):
    jid = "t" + str(time.time_ns())
    services._jobs[jid] = {"id": jid, "state": "done", "items": items, "cancel": False, "started": time.time()}
    return jid


def test_set_genre_learns_and_updates_item():
    jid = _job([{"title": "Song", "artist": "DJ", "artists": ["DJ"], "genre": None, "why": "x"}])
    it = services.set_genre(jid, 0, "Techno", "Peak Time", True)
    assert it["genre"] == "Techno" and it["subgenre"] == "Peak Time" and it["why"] is None and it["own"]
    own = genredb.own(["DJ"], "Song")
    assert own["genre"] == "Techno" and own["source"] == "korrektur"


def test_set_genre_without_learning_and_invalid():
    jid = _job([{"title": "B", "artist": "C", "artists": ["C"], "genre": "Pop"}])
    services.set_genre(jid, 0, "Techno", "Gibt es nicht", False)
    assert genredb.own(["C"], "B") is None and services._jobs[jid]["items"][0]["subgenre"] is None
    with pytest.raises(services.ServiceError):
        services.set_genre(jid, 0, "Kein Genre", None, True)
    with pytest.raises(services.ServiceError):
        services.set_genre(jid, 5, "Techno", None, True)


def test_ai_unsorted_only_sends_unsorted(monkeypatch):
    from tunebridge import ai
    sent = []
    monkeypatch.setattr(ai, "ready", lambda *a: (True, ""))
    monkeypatch.setattr(ai, "review_genres", lambda items: sent.extend(items) or [{"i": 1, "genre": "Techno", "subgenre": None, "grund": "kenn ich"}])
    items = [{"title": "a", "genre": "Pop"}, {"title": "b", "genre": None}, {"title": "c", "genre": None},
             {"title": "v", "genre": None, "nomusic": True}]
    jid = _job(items)
    monkeypatch.setattr(services.threading, "Thread", lambda target, args, daemon: type("T", (), {"start": lambda s: target(*args)})())
    assert services.ai_unsorted(jid) == 2
    assert [x["title"] for x in sent] == ["b", "c"]
    j = services._jobs[jid]
    assert j["state"] == "done" and j["ai_new"] == [2] and items[2]["genre"] == "Techno" and items[2]["ki"]


def test_why_no_genre_reasons():
    assert linkimport.why_no_genre(Track("t", ["a"], genre="Pop"), {}) is None
    assert "Pause" in linkimport.why_no_genre(Track("t", ["a"]), {"incomplete": True})
    assert "kawaii, 2019" in linkimport.why_no_genre(Track("t", ["a"], tags={"kawaii": 50, "2019": 10}), {})
    assert "nicht gefunden" in linkimport.why_no_genre(Track("t", ["a"]), {})
    assert "nirgends mit Genre" in linkimport.why_no_genre(Track("t", ["a"]), {"links": {"deezer": "https://deezer.com/track/1"}})

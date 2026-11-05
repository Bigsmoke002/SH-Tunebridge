"""Große Playlists sortieren: Limit-Pausen werden abgewartet, unvollständige Ergebnisse nicht gespeichert."""
import time

import pytest

from tunebridge import ratelimit


@pytest.fixture
def lim(monkeypatch):
    l = ratelimit._Limit("Test", 2, 1.0, pause=0.6)
    monkeypatch.setitem(ratelimit.LIMITS, "test", l)
    return l


def test_normal_mode_skips_during_pause_and_marks_skipped(lim):
    ratelimit.reset_skipped()
    ratelimit.blocked("test", 0.6)
    with pytest.raises(ratelimit.LimitReached):
        ratelimit.wait_sync("test", max_wait=0.1)
    assert ratelimit.skipped()


def test_patient_mode_waits_out_pause(lim):
    ratelimit.reset_skipped()
    ratelimit.blocked("test", 0.6)
    t0 = time.time()
    with ratelimit.patient(max_wait=5):
        assert ratelimit.is_patient()
        ratelimit.wait_sync("test", max_wait=0.1)
    assert time.time() - t0 >= 0.5
    assert not ratelimit.skipped() and not ratelimit.is_patient()


def test_patient_mode_gives_up_on_very_long_pause(lim):
    ratelimit.reset_skipped()
    ratelimit.blocked("test", 600)
    with ratelimit.patient(max_wait=1), pytest.raises(ratelimit.LimitReached):
        ratelimit.wait_sync("test")
    assert ratelimit.skipped()


def test_incomplete_result_is_not_cached(monkeypatch):
    from tunebridge import consent, enrich, songcache
    from tunebridge.models import Track
    from tunebridge.recognize.engines import Recognition
    saved = []
    monkeypatch.setattr(consent, "local", lambda k: True)
    monkeypatch.setattr(songcache, "lookup", lambda rec: None)
    monkeypatch.setattr(songcache, "save", lambda *a: saved.append(a))
    monkeypatch.setattr(enrich, "_known", lambda *a: None)

    def online(rec, skip):
        if skip:
            ratelimit._tl.skipped = True
        return Track(title=rec.title, artists=rec.artists), {}
    rec = Recognition(engine="link", title="Song", artists=["Artist"])
    monkeypatch.setattr(enrich, "_enrich_online", lambda r: online(r, True))
    _, extra = enrich.enrich(rec)
    assert extra.get("incomplete") and not saved
    monkeypatch.setattr(enrich, "_enrich_online", lambda r: online(r, False))
    enrich.enrich(rec)
    assert len(saved) == 1


def test_cached_hit_without_genre_is_refreshed_when_sorting(monkeypatch):
    from tunebridge import consent, enrich, songcache
    from tunebridge.models import Track
    from tunebridge.recognize.engines import Recognition
    monkeypatch.setattr(consent, "local", lambda k: True)
    monkeypatch.setattr(songcache, "lookup", lambda rec: (Track(title="Song", artists=["A"]), {}))
    monkeypatch.setattr(songcache, "save", lambda *a: None)
    monkeypatch.setattr(enrich, "_known", lambda *a: None)
    calls = []
    monkeypatch.setattr(enrich, "_enrich_online", lambda r: calls.append(1) or (Track(title="Song", artists=["A"], genre="Techno"), {}))
    rec = Recognition(engine="link", title="Song", artists=["A"])
    enrich.enrich(rec)
    assert not calls                                    # normal: Speicher reicht
    with ratelimit.patient():
        t, _ = enrich.enrich(rec)
    assert calls and t.genre == "Techno"                # beim Sortieren: ohne Genre -> neu nachschlagen

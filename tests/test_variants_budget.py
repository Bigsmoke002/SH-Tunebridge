"""Tempo-Suche darf das Shazam-Budget nicht aufbrauchen – der nächste Scan muss sofort gehen."""

import asyncio
import wave

import numpy as np

from tunebridge import ratelimit
from tunebridge.recognize import variants


def test_tries_allowed_keeps_reserve():
    assert variants.tries_allowed(10) == 3
    assert variants.tries_allowed(9) == 3
    assert variants.tries_allowed(7) == 2
    assert variants.tries_allowed(5) == 0
    assert variants.tries_allowed(0) == 0


def test_unknown_song_uses_at_most_three_extra_requests(tmp_path, monkeypatch):
    p = tmp_path / "a.wav"
    with wave.open(str(p), "wb") as w:
        w.setnchannels(1), w.setsampwidth(2), w.setframerate(8000)
        w.writeframes((np.random.default_rng(1).normal(0, 3000, 8000 * 6)).astype("<i2").tobytes())
    calls = []

    async def fake_shazam(path):
        await ratelimit.wait_async("shazam", max_wait=8)
        calls.append(path)
        return None   # Song unbekannt

    monkeypatch.setattr(variants, "shazam", fake_shazam)
    monkeypatch.setattr(variants, "PAUSE", 0)
    ratelimit.LIMITS["shazam"].hits.clear()
    ratelimit.LIMITS["shazam"].gap = 0
    try:
        ratelimit.LIMITS["shazam"].hits.append(__import__("time").time())   # der normale Scan
        tries = variants.tries_allowed(ratelimit.free("shazam"))
        assert asyncio.run(variants.find(p, max_tries=tries)) is None
        assert len(calls) == 3
        assert ratelimit.free("shazam") >= variants.RESERVE   # nächster Scan geht sofort
    finally:
        ratelimit.LIMITS["shazam"].hits.clear()
        ratelimit.LIMITS["shazam"].gap = 2.0


def test_nothing_found_no_automatic_tempo_search(monkeypatch, tmp_path):
    """Gar kein Treffer -> keine weiteren Shazam-Anfragen von selbst, nur ein Angebot (Knopf)."""
    from fastapi.testclient import TestClient

    from tunebridge.recognize import engines
    from tunebridge.web import app as web
    p = tmp_path / "a.wav"
    with wave.open(str(p), "wb") as w:
        w.setnchannels(1), w.setsampwidth(2), w.setframerate(8000)
        w.writeframes((np.random.default_rng(2).normal(0, 6000, 8000 * 6)).astype("<i2").tobytes())
    import shutil
    monkeypatch.setattr(web.capture, "record", lambda src, sec: shutil.copy(p, tmp_path / "rec.wav"))
    monkeypatch.setattr(web, "recognize", lambda wav, eng: _async(engines.Result(None, 0, [], {})))
    found = []
    monkeypatch.setattr(variants, "find", lambda *a, **k: found.append(k) or _async(None))
    cl = TestClient(web.app)
    r = cl.post("/api/listen", json={"seconds": 5}).json()
    assert r["found"] is False and r["tempo_offer"] is True and found == []
    r = cl.post("/api/listen", json={"seconds": 5, "tempo": True}).json()
    assert len(found) == 1 and found[0]["max_tries"] >= 1


async def _coro(v):
    return v


def _async(v):
    return _coro(v)

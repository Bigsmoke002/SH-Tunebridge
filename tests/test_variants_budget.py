"""Tempo-Suche darf das Shazam-Budget nicht aufbrauchen – der nächste Scan muss sofort gehen."""

import asyncio
import wave

import numpy as np

from tunebridge import ratelimit
from tunebridge.recognize import variants


def test_tries_allowed_keeps_reserve():
    assert variants.tries_allowed(12) == 3
    assert variants.tries_allowed(11) == 3
    assert variants.tries_allowed(8) == 2
    assert variants.tries_allowed(6) == 0
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
        ratelimit.LIMITS["shazam"].gap = 1.0

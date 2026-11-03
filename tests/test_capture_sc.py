"""Windows/macOS-Aufnahme mit einer nachgebauten `soundcard`-Bibliothek (läuft auch unter Linux)."""

import asyncio
import sys
import types
import wave

import numpy as np
import pytest

from tunebridge import osutil
from tunebridge.recognize import capture_sc


class _Rec:
    def __init__(self, ch):
        self.ch = ch

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def record(self, numframes):
        t = np.arange(numframes) / 44100
        x = 0.5 * np.sin(2 * np.pi * 440 * t)
        return np.stack([x] * self.ch, axis=1)


class _Dev:
    def __init__(self, id, name):
        self.id, self.name = id, name

    def recorder(self, samplerate, channels, blocksize=None):
        return _Rec(channels)


@pytest.fixture
def fake_sc(monkeypatch):
    spk = _Dev("spk1", "Lautsprecher")
    mics = [_Dev("mic1", "Headset-Mikrofon"), _Dev("bh", "BlackHole 2ch")]
    mod = types.SimpleNamespace(
        default_speaker=lambda: spk, all_speakers=lambda: [spk],
        default_microphone=lambda: mics[0],
        all_microphones_loop=None)
    mod.all_microphones = lambda include_loopback=False: ([spk] if include_loopback else []) + mics
    monkeypatch.setitem(sys.modules, "soundcard", mod)
    return mod


def test_sources_windows(fake_sc, monkeypatch):
    monkeypatch.setattr(osutil, "WINDOWS", True)
    monkeypatch.setattr(osutil, "MACOS", False)
    src = capture_sc.sources()
    assert src[0].name == "loop:spk1" and src[0].kind == "desktop" and src[0].default
    assert capture_sc.default_source("desktop") == "loop:spk1"
    assert capture_sc.default_source("mic") == "mic:mic1"


def test_macos_blackhole_is_desktop(fake_sc, monkeypatch):
    monkeypatch.setattr(osutil, "WINDOWS", False)
    monkeypatch.setattr(osutil, "MACOS", True)
    assert capture_sc.default_source("desktop") == "mic:bh"


def test_record_writes_wav(fake_sc, monkeypatch):
    monkeypatch.setattr(osutil, "WINDOWS", True)
    p = capture_sc.record("desktop", 0.5)
    with wave.open(str(p)) as w:
        assert w.getnchannels() == 2 and w.getframerate() == 44100 and w.getnframes() == 22050
    p.unlink()


def test_meter_stream(fake_sc, monkeypatch):
    monkeypatch.setattr(osutil, "WINDOWS", True)

    async def go():
        r = await capture_sc.open_stream("desktop", 22050, 882)
        data = await r.stdout.readexactly(882 * 2 * 3)
        await r.wait()
        return np.frombuffer(data, "<i2")

    s = asyncio.run(go())
    assert s.size == 882 * 3 and np.abs(s).max() > 10000


def test_app_sources_rejected():
    with pytest.raises(RuntimeError):
        capture_sc.record("app:spotify", 1)


def test_macos_integer_ids(fake_sc, monkeypatch):
    """macOS (CoreAudio) liefert Zahlen als Geräte-ID."""
    monkeypatch.setattr(osutil, "WINDOWS", False)
    monkeypatch.setattr(osutil, "MACOS", True)
    mics = [_Dev(41, "MacBook-Mikrofon"), _Dev(73, "BlackHole 2ch")]
    fake_sc.all_microphones = lambda include_loopback=False: mics
    fake_sc.default_microphone = lambda: mics[0]
    assert capture_sc.default_source("mic") == "mic:41"
    assert capture_sc.default_source("desktop") == "mic:73"
    assert capture_sc._device("mic:73") is mics[1]

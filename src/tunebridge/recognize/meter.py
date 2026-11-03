"""Live-Pegel & Spektrum einer Audioquelle – damit man sieht, ob überhaupt Ton ankommt.

Liest per `parec` rohes Mono-PCM (16 bit, 22,05 kHz) und berechnet ~25× pro Sekunde:
  rms/peak in dBFS und 32 logarithmisch verteilte Frequenzbänder (0..1).
Mehrere Leser auf derselben Quelle sind unter PipeWire/PulseAudio kein Problem.
"""

from __future__ import annotations

import asyncio
import wave
from pathlib import Path

import numpy as np

from .. import osutil
from .capture import APP_PREFIX, app_targets, apps, default_source, sources

RATE = 22050
FPS = 25
CHUNK = RATE // FPS             # Samples pro Frame
FFT_N = 2048
BANDS = 32
FLOOR_DB = -90.0
SILENT_DB = -60.0               # darunter gilt: kein brauchbares Signal

# Log-Bandgrenzen 40 Hz .. 11 kHz -> FFT-Bins
_edges = np.geomspace(40, RATE / 2 - 1, BANDS + 1)
_bins = np.clip((_edges / (RATE / 2) * (FFT_N // 2)).astype(int), 1, FFT_N // 2)
_window = np.hanning(FFT_N)


def resolve(source: str) -> str:
    return default_source(source) if source in ("desktop", "mic") else source


def _db(x: float) -> float:
    return float(max(FLOOR_DB, 20 * np.log10(max(x, 1e-9))))


def analyze(samples: np.ndarray) -> dict:
    """samples: float32 -1..1"""
    rms = float(np.sqrt(np.mean(samples ** 2))) if samples.size else 0.0
    peak = float(np.max(np.abs(samples))) if samples.size else 0.0
    buf = np.zeros(FFT_N, dtype=np.float32)
    n = min(FFT_N, samples.size)
    buf[-n:] = samples[-n:]
    spec = np.abs(np.fft.rfft(buf * _window)) / (FFT_N / 4)
    bands = []
    for lo, hi in zip(_bins[:-1], _bins[1:]):
        v = float(spec[lo:max(hi, lo + 1)].max())
        db = 20 * np.log10(max(v, 1e-9))
        bands.append(round(float(min(1.0, max(0.0, (db + 75) / 70))), 3))  # -75..-5 dB -> 0..1
    return {"rms": round(_db(rms), 1), "peak": round(_db(peak), 1), "bands": bands}


async def _open(device: str) -> asyncio.subprocess.Process:
    if not osutil.LINUX:
        from .capture_sc import open_stream
        return await open_stream(device, RATE, CHUNK)
    if device.startswith(APP_PREFIX):
        targets = await asyncio.to_thread(app_targets, device)
        if not targets:
            raise LookupError("Anwendung spielt gerade nichts ab")
        return await asyncio.create_subprocess_exec(
            "pw-record", "--target", targets[0], "--raw", "--format", "s16", "--rate", str(RATE), "--channels", "1",
            "--latency", "20ms", "-", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
    return await asyncio.create_subprocess_exec(
        "parec", "-d", device, "--format=s16le", f"--rate={RATE}", "--channels=1", "--raw",
        "--latency-msec=20", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)


async def levels(source: str):
    """Async-Generator: liefert Pegel-Frames, bis der Aufrufer abbricht."""
    proc = await _open(resolve(source))
    hist = np.zeros(FFT_N, dtype=np.float32)
    try:
        while True:
            data = await proc.stdout.readexactly(CHUNK * 2)
            s = np.frombuffer(data, dtype="<i2").astype(np.float32) / 32768.0
            hist = np.concatenate([hist[s.size:], s])
            frame = analyze(hist[-CHUNK:])
            frame["bands"] = analyze(hist)["bands"]
            yield frame
    finally:
        if proc.returncode is None:
            proc.kill()
        await proc.wait()


async def probe(device: str, seconds: float = 0.8) -> float:
    """Kurz in eine Quelle hineinhören -> RMS in dBFS."""
    proc = await _open(device)
    try:
        data = await asyncio.wait_for(proc.stdout.readexactly(int(RATE * seconds) * 2), timeout=seconds + 2)
    except (asyncio.TimeoutError, asyncio.IncompleteReadError):
        data = b""
    finally:
        if proc.returncode is None:
            proc.kill()
        await proc.wait()
    s = np.frombuffer(data, dtype="<i2").astype(np.float32) / 32768.0
    # Erste 150 ms verwerfen (Anlauf-Stille)
    s = s[int(RATE * 0.15):]
    return _db(float(np.sqrt(np.mean(s ** 2)))) if s.size else FLOOR_DB


async def scan(kind: str | None = None) -> list[dict]:
    """Alle Quellen (optional nur 'desktop'/'mic') gleichzeitig kurz prüfen."""
    srcs = [s for s in sources() if not kind or s.kind == kind]
    if kind in (None, "desktop"):
        srcs += apps()
    dbs = await asyncio.gather(*(probe(s.name) for s in srcs))
    out = [{"name": s.name, "description": s.description, "kind": s.kind, "default": s.default,
            "db": round(d, 1), "signal": d > SILENT_DB} for s, d in zip(srcs, dbs)]
    return sorted(out, key=lambda x: -x["db"])


def wav_level(path: Path) -> float:
    """Pegel einer Aufnahme (dBFS) – um 'nichts erkannt' von 'nichts gehört' zu unterscheiden."""
    with wave.open(str(path)) as w:
        raw = w.readframes(w.getnframes())
    s = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    return _db(float(np.sqrt(np.mean(s ** 2)))) if s.size else FLOOR_DB

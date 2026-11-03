"""Tonaufnahme unter Windows und macOS (Bibliothek `soundcard`).

* Windows: Desktop-Ton über WASAPI-Loopback des Ausgabegeräts – funktioniert ohne Zusatzprogramme.
* macOS: Apple erlaubt Desktop-Ton nur über ein virtuelles Gerät (z. B. das kostenlose „BlackHole“).
  Ist eines installiert, erscheint es als Desktop-Quelle; sonst gibt es nur das Mikrofon.
* Einzelne Anwendungen aufnehmen geht hier nicht (nur unter Linux/PipeWire).
Datenschutz wie unter Linux: Aufnahmen landen nur kurz in einer temporären Datei.
"""

from __future__ import annotations

import asyncio
import re
import threading
import warnings
import wave
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .. import osutil

APP_PREFIX = "app:"
_VIRTUAL = re.compile(r"blackhole|loopback|soundflower|vb-?audio|stereo ?mix|stereomix", re.I)


@dataclass
class Source:
    name: str
    description: str
    kind: str
    default: bool = False


def _sc():
    import soundcard
    # Beim Start einer Aufnahme meldet Windows oft eine kurze Lücke – harmlos, nur Lärm im Log
    warnings.filterwarnings("ignore", message="data discontinuity", module="soundcard")
    return soundcard


def pipewire_ok() -> bool:
    return False


def apps() -> list[Source]:
    return []


def app_targets(source: str) -> list[str]:
    return []


def _safe(fn, default=None):
    try:
        return fn()
    except Exception:  # kein Audiogerät / Audiodienst aus – dann eben keine Quelle statt Absturz
        return default


def sources() -> list[Source]:
    try:
        sc = _sc()
    except Exception:
        return []
    out: list[Source] = []
    if osutil.WINDOWS:
        dflt = _safe(sc.default_speaker)
        for sp in _safe(sc.all_speakers, []):
            out.append(Source(f"loop:{sp.id}", sp.name, "desktop", dflt is not None and sp.id == dflt.id))
    dmic = _safe(sc.default_microphone)
    for m in _safe(lambda: sc.all_microphones(include_loopback=False), []):
        kind = "desktop" if _VIRTUAL.search(m.name) else "mic"
        out.append(Source(f"mic:{m.id}", m.name, kind, dmic is not None and m.id == dmic.id and kind == "mic"))
    out.sort(key=lambda s: (s.kind != "desktop", not s.default, s.description))
    return out


def default_source(kind: str) -> str:
    srcs = [s for s in sources() if s.kind == kind]
    if not srcs:
        if kind == "desktop" and osutil.MACOS:
            raise RuntimeError("Für Desktop-Ton unter macOS bitte ein virtuelles Audiogerät wie „BlackHole“ "
                               "installieren und als Ausgabe wählen – oder das Mikrofon nutzen")
        raise RuntimeError("Kein passendes Audiogerät gefunden")
    return next((s.name for s in srcs if s.default), srcs[0].name)


def _device(name: str):
    sc = _sc()
    if name in ("desktop", "mic"):
        name = default_source(name)
    kind, _, dev = name.partition(":")
    # IDs vergleichen wir als Text: Windows liefert Zeichenketten, macOS Zahlen
    devices = sc.all_microphones(include_loopback=(kind == "loop"))
    hit = next((d for d in devices if str(d.id) == dev), None)
    if hit is None:
        raise RuntimeError("Audiogerät nicht mehr vorhanden – bitte Quelle neu wählen")
    return hit


def record(source: str = "desktop", seconds: float = 10) -> Path:
    if source.startswith(APP_PREFIX):
        raise RuntimeError("Einzelne Anwendungen aufnehmen geht nur unter Linux")
    mic = _device(source)
    rate = 44100
    with mic.recorder(samplerate=rate, channels=2) as r:
        data = r.record(numframes=int(rate * seconds))
    if data.ndim == 1:
        data = np.stack([data, data], axis=1)
    pcm = (np.clip(data[:, :2], -1, 1) * 32767).astype("<i2")
    out = osutil.tmpfile(prefix="tunebridge-", suffix=".wav")
    with wave.open(str(out), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm.tobytes())
    return out


class _Reader:
    """Benimmt sich für meter.py wie ein Unterprozess mit stdout (s16le mono)."""

    def __init__(self, device: str, rate: int, block: int):
        self.returncode = None
        self._stop = threading.Event()
        self._q: asyncio.Queue[bytes] = asyncio.Queue(maxsize=200)
        self._buf = b""
        self._loop = asyncio.get_running_loop()
        self.stdout = self
        threading.Thread(target=self._run, args=(device, rate, block), daemon=True).start()

    def _run(self, device: str, rate: int, block: int) -> None:
        try:
            mic = _device(device)
            with mic.recorder(samplerate=rate, channels=1, blocksize=block) as r:
                while not self._stop.is_set():
                    d = r.record(numframes=block)
                    mono = d.mean(axis=1) if d.ndim > 1 else d
                    pcm = (np.clip(mono, -1, 1) * 32767).astype("<i2").tobytes()
                    self._loop.call_soon_threadsafe(self._put, pcm)
        except Exception:
            self._loop.call_soon_threadsafe(self._put, b"")
        self.returncode = 0

    def _put(self, pcm: bytes) -> None:
        if not self._q.full():
            self._q.put_nowait(pcm)

    async def readexactly(self, n: int) -> bytes:
        while len(self._buf) < n:
            chunk = await self._q.get()
            if not chunk:
                raise asyncio.IncompleteReadError(self._buf, n)
            self._buf += chunk
        out, self._buf = self._buf[:n], self._buf[n:]
        return out

    def kill(self) -> None:
        self._stop.set()

    async def wait(self) -> int:
        self._stop.set()
        return 0


async def open_stream(device: str, rate: int, block: int) -> _Reader:
    if device.startswith(APP_PREFIX):
        raise LookupError("Einzelne Anwendungen gehen nur unter Linux")
    return _Reader(device, rate, block)

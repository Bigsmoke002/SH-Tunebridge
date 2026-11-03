"""Audio aufnehmen: Mikrofon, Desktop-Sound (PipeWire/PulseAudio-Monitor) oder – optional –
nur eine einzelne Anwendung (Browser, Spotify, Player …).

Nutzt `parecord` (libpulse, auf praktisch jedem Linux-Desktop vorhanden, funktioniert auch
mit PipeWire). Anwendungen einzeln gehen nur unter PipeWire (`pw-dump` + `pw-record`).
Keine Python-Audio-Bibliotheken nötig.

Datenschutz: Sprach-/Videochat-Programme (Discord, Teams, Zoom …) werden als Quelle gar nicht
erst angeboten.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import wave
import time
from dataclasses import dataclass
from pathlib import Path
from .. import osutil


@dataclass
class Source:
    name: str
    description: str
    kind: str  # "desktop" | "mic" | "app"
    default: bool = False


def _pactl(*args: str) -> str:
    return subprocess.run(["pactl", *args], capture_output=True, text=True, check=True).stdout


def sources() -> list[Source]:
    default_sink = _pactl("get-default-sink").strip()
    default_src = _pactl("get-default-source").strip()
    out: list[Source] = []
    name = desc = None
    for line in _pactl("list", "sources").splitlines():
        line = line.strip()
        if line.startswith("Name:"):
            name = line.split(":", 1)[1].strip()
        elif line.startswith("Description:") and name:
            desc = line.split(":", 1)[1].strip()
            kind = "desktop" if name.endswith(".monitor") else "mic"
            is_def = name == f"{default_sink}.monitor" or name == default_src
            out.append(Source(name, desc, kind, is_def))
            name = None
    out.sort(key=lambda s: (s.kind != "desktop", not s.default, s.description))
    return out


# ---------------------------------------------------------------- einzelne Anwendungen (PipeWire)
APP_PREFIX = "app:"
# Sprach-/Videochat & Mikrofon-Durchschleifen: nie als Quelle anbieten (Gespräche, § 201 StGB)
_VOICE = re.compile(r"discord|webrtc|voiceengine|teams|zoom|skype|signal|telegram|mumble|teamspeak|ts3|element|"
                    r"slack|whatsapp|jitsi|webex|nvbroadcast|noisetorch|easyeffects|\bmic\b|microphone|"
                    r"tunebridge|qtwebengine", re.I)


def pipewire_ok() -> bool:
    return bool(shutil.which("pw-dump") and shutil.which("pw-record"))


def _streams() -> list[dict]:
    """Laufende Wiedergabe-Streams von Anwendungen: [{key, name, title, serial}]"""
    if not pipewire_ok():
        return []
    try:
        objs = json.loads(subprocess.run(["pw-dump"], capture_output=True, text=True, timeout=5).stdout or "[]")
    except (subprocess.SubprocessError, ValueError):
        return []
    out = []
    for o in objs:
        p = ((o.get("info") or {}).get("props") or {})
        if o.get("type") != "PipeWire:Interface:Node" or p.get("media.class") != "Stream/Output/Audio":
            continue
        name = p.get("application.name") or p.get("application.process.binary") or p.get("node.name") or ""
        binary = p.get("application.process.binary") or ""
        ident = " ".join(str(x) for x in (name, binary, p.get("node.name"), p.get("media.name")))
        if not name or p.get("media.role") in ("Communication", "Phone") or _VOICE.search(ident):
            continue
        key = (binary or name).lower()
        out.append({"key": key, "name": name, "title": p.get("media.name") or "", "serial": str(p.get("object.serial"))})
    return out


def apps() -> list[Source]:
    """Eine Quelle je Anwendung (mehrere Tabs/Streams werden beim Aufnehmen zusammengemischt)."""
    seen: dict[str, Source] = {}
    for st in _streams():
        seen.setdefault(st["key"], Source(APP_PREFIX + st["key"], st["name"], "app"))
    return sorted(seen.values(), key=lambda s: s.description.lower())


def app_targets(source: str) -> list[str]:
    key = source[len(APP_PREFIX):]
    return [st["serial"] for st in _streams() if st["key"] == key]


def _record_app(source: str, seconds: float) -> Path:
    targets = app_targets(source)
    if not targets:
        raise RuntimeError(f"„{source[len(APP_PREFIX):]}“ spielt gerade nichts ab – Wiedergabe starten oder andere Quelle wählen")
    tmp = [osutil.tmpfile(prefix="tunebridge-a-", suffix=".raw") for _ in targets]
    procs = [subprocess.Popen(["pw-record", "--target", t, "--raw", "--format", "s16", "--rate", "44100",
                               "--channels", "2", str(f)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
             for t, f in zip(targets, tmp)]
    time.sleep(seconds + 0.5)
    for pr in procs:
        pr.terminate()
    for pr in procs:
        try:
            pr.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pr.kill()
    import numpy as np

    try:
        parts = [np.frombuffer(f.read_bytes(), "<i2").astype(np.int32) for f in tmp]
    finally:
        for f in tmp:
            f.unlink(missing_ok=True)
    n = max((len(x) for x in parts), default=0) // 2 * 2
    if n < 44100 * 2:
        raise RuntimeError("Aufnahme der Anwendung leer/zu kurz")
    mix = np.zeros(n, np.int32)
    for x in parts:
        mix[:len(x[:n])] += x[:n]
    out = osutil.tmpfile(prefix="tunebridge-", suffix=".wav")
    with wave.open(str(out), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(np.clip(mix, -32768, 32767).astype("<i2").tobytes())
    return out


def default_source(kind: str) -> str:
    if kind == "desktop":
        return _pactl("get-default-sink").strip() + ".monitor"
    return _pactl("get-default-source").strip()


def record(source: str = "desktop", seconds: float = 10) -> Path:
    """Nimmt `seconds` Sekunden auf und gibt den Pfad zur WAV-Datei zurück.
    `source`: "desktop", "mic", ein konkreter Quellenname aus `sources()` oder „app:<programm>“."""
    if source.startswith(APP_PREFIX):
        return _record_app(source, seconds)
    if not shutil.which("parecord"):
        raise RuntimeError("parecord fehlt (Paket libpulse bzw. pulseaudio-utils)")
    device = default_source(source) if source in ("desktop", "mic") else source
    out = osutil.tmpfile(prefix="tunebridge-", suffix=".wav")
    proc = subprocess.Popen(
        ["parecord", "-d", device, "--file-format=wav", "--rate=44100", "--channels=2",
         "--format=s16le", str(out)],
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
    )
    time.sleep(seconds + 1.5)  # parecord braucht ~1-2 s zum Anlaufen
    proc.terminate()
    _, err = proc.communicate(timeout=5)
    if out.stat().st_size < 10_000:
        raise RuntimeError(f"Aufnahme leer/zu kurz ({device}): {err.decode().strip()}")
    return out


# Windows/macOS: gleiche Schnittstelle, andere Technik (WASAPI-Loopback bzw. CoreAudio)
if not osutil.LINUX:
    from .capture_sc import (Source, app_targets, apps, default_source, pipewire_ok,  # noqa: E402,F401,F811
                             record, sources)

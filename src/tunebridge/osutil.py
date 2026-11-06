"""Betriebssystem-Unterschiede an einer Stelle: Linux, Windows, macOS.

Linux bleibt wie bisher (PipeWire/PulseAudio, MPRIS, XDG-Ordner). Für Windows und macOS gibt es hier
die passenden Gegenstücke – ohne dass der Rest der App davon wissen muss.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

LINUX = sys.platform.startswith("linux")
WINDOWS = sys.platform == "win32"
# Unterprozesse unter Windows nie mit sichtbarem Konsolenfenster starten (wirkte wie „Schadsoftware“)
NO_WINDOW: dict = {"creationflags": 0x08000000} if WINDOWS else {}   # CREATE_NO_WINDOW
MACOS = sys.platform == "darwin"
NAME = "Linux" if LINUX else "Windows" if WINDOWS else "macOS" if MACOS else sys.platform


def config_dir() -> Path:
    if WINDOWS:
        return Path(os.environ.get("APPDATA", Path.home() / "AppData/Roaming")) / "SH-Tunebridge"
    if MACOS:
        return Path.home() / "Library/Application Support/SH-Tunebridge"
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "tunebridge"


def data_dir() -> Path:
    if os.environ.get("TUNEBRIDGE_DATA"):
        return Path(os.environ["TUNEBRIDGE_DATA"])
    if WINDOWS:
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "SH-Tunebridge"
    if MACOS:
        return Path.home() / "Library/Application Support/SH-Tunebridge/Daten"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "tunebridge"


def downloads_dir() -> Path:
    if os.environ.get("TUNEBRIDGE_DOWNLOADS"):          # Tests / eigener Export-Ordner
        return Path(os.environ["TUNEBRIDGE_DOWNLOADS"])
    if LINUX:
        try:
            out = subprocess.run(["xdg-user-dir", "DOWNLOAD"], capture_output=True, text=True, timeout=3).stdout.strip()
            if out and out != str(Path.home()):
                return Path(out)
        except (OSError, subprocess.SubprocessError):
            pass
    for name in ("Downloads", "Download"):
        if (Path.home() / name).is_dir():
            return Path.home() / name
    return Path.home()


def open_path(path: str | Path) -> None:
    """Ordner/Datei im Dateimanager bzw. Standardprogramm öffnen."""
    p = str(path)
    try:
        if WINDOWS:
            os.startfile(p)  # noqa: S606  (nur lokale Pfade aus der App)
        elif MACOS:
            subprocess.Popen(["open", p], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.Popen(["xdg-open", p], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError as e:   # z. B. kein Dateimanager / Explorer startet nicht – verständlich melden statt Serverfehler
        raise OpenError(f"Ordner ließ sich nicht öffnen – du findest ihn hier: {p}") from e


class OpenError(RuntimeError):
    """Dateimanager/Browser konnte nicht gestartet werden."""


def ram_gb() -> dict:
    """{total, available} in GB."""
    if LINUX:
        info = {}
        for line in Path("/proc/meminfo").read_text().splitlines():
            k, v = line.split(":", 1)
            info[k] = int(v.split()[0]) / 1024 / 1024
        return {"total": round(info.get("MemTotal", 0), 1), "available": round(info.get("MemAvailable", 0), 1)}
    if WINDOWS:
        import ctypes

        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        st = MEMORYSTATUSEX()
        st.dwLength = ctypes.sizeof(st)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st))
        return {"total": round(st.ullTotalPhys / 1024 ** 3, 1), "available": round(st.ullAvailPhys / 1024 ** 3, 1)}
    try:
        total = int(subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True).stdout)
        vm = subprocess.run(["vm_stat"], capture_output=True, text=True).stdout
        page = 16384 if "16384" in vm.splitlines()[0] else 4096
        free = sum(int(line.split(":")[1].strip().rstrip(".")) for line in vm.splitlines()
                   if line.startswith(("Pages free", "Pages inactive", "Pages speculative")))
        return {"total": round(total / 1024 ** 3, 1), "available": round(free * page / 1024 ** 3, 1)}
    except (OSError, ValueError, IndexError):
        return {"total": 0, "available": 0}


def physical_cores() -> int:
    if LINUX:
        try:
            text = Path("/proc/cpuinfo").read_text()
            cores = {line.split(":")[1].strip() for line in text.splitlines() if line.startswith("core id")}
            sockets = {line.split(":")[1].strip() for line in text.splitlines()
                       if line.startswith("physical id")} or {"0"}
            if cores:
                return max(1, len(cores) * len(sockets))
        except OSError:
            pass
    if MACOS:
        try:
            return int(subprocess.run(["sysctl", "-n", "hw.physicalcpu"], capture_output=True, text=True).stdout)
        except (OSError, ValueError):
            pass
    return max(1, (os.cpu_count() or 2) // 2)


def die_with_parent() -> None:
    """Kindprozess (LLM-Server) beendet sich mit der App – nur Linux kann das direkt.
    Windows/macOS: die App beendet den Server beim Schließen selbst (llm.stop via atexit)."""
    if LINUX:
        import ctypes
        import signal
        try:
            ctypes.CDLL("libc.so.6").prctl(1, signal.SIGTERM)  # PR_SET_PDEATHSIG
        except OSError:
            pass


def popen_flags() -> dict:
    """Unter Windows kein schwarzes Konsolenfenster für Hilfsprogramme."""
    if WINDOWS:
        return {"creationflags": 0x08000000}  # CREATE_NO_WINDOW
    return {}


def tmpfile(prefix: str, suffix: str) -> Path:
    """Leere temporäre Datei; Handle sofort schließen (Windows sperrt sonst Löschen/Überschreiben)."""
    fd, name = tempfile.mkstemp(prefix=prefix, suffix=suffix)
    os.close(fd)
    return Path(name)

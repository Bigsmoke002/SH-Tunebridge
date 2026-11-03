"""Lokales LLM, von SH-Tunebridge selbst verwaltet.

* Drei Modelle (leicht / mittel / Qualität, Gemma 3 – im Test mit Abstand das beste Musikwissen) – Download im Hintergrund, fortsetzbar, SHA256-geprüft.
* Laufzeit: llama.cpp-Server (offizielle Release-Builds, SHA256-geprüft):
    cpu -> reiner CPU-Build (RAM)
    gpu -> Vulkan-Build (NVIDIA/AMD/Intel, kein CUDA nötig)
* Der Server startet erst, wenn er gebraucht wird, und beendet sich nach einer Weile ohne Nutzung
  (gibt RAM/VRAM wieder frei). Er stirbt immer mit der App.
* Es werden keine GPU-Einstellungen verändert – nur ein Programm ausgeführt.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tarfile
import threading
import time
from pathlib import Path

import httpx

from . import config, store

PORT = 8766
LLAMA_BUILD = "b12032"
_REL = f"https://github.com/ggml-org/llama.cpp/releases/download/{LLAMA_BUILD}/llama-{LLAMA_BUILD}-bin-"
_RUNTIMES_BY_OS = {
    "linux": {
        "cpu": {"label": "CPU", "size": 22886629, "url": _REL + "ubuntu-x64.tar.gz",
                "sha256": "9f10432ca3f66ef003a7a540aaffb9da0acadaefd05404521b9ab7a2436af304"},
        "gpu": {"label": "Vulkan", "size": 35669614, "url": _REL + "ubuntu-vulkan-x64.tar.gz",
                "sha256": "f75e7107f9450034c5467492c41e9ed91816e2d815fc4b802c6bd58de7d5b126"},
    },
    "win32": {
        "cpu": {"label": "CPU", "size": 24582754, "url": _REL + "win-cpu-x64.zip",
                "sha256": "5296f5d18bb7d422c7c26f4bb9bc796d9d4f41e1312a8c296cff475bdc60d0d4"},
        "gpu": {"label": "Vulkan", "size": 37523450, "url": _REL + "win-vulkan-x64.zip",
                "sha256": "19a8bbf269fa683ae7bc04f886c9c2a93e0655c2606f37d2b60069bf9e8bcc32"},
    },
    # macOS: der Build nutzt automatisch Metal (Apple-GPU) – ein Paket für beides
    "darwin-arm64": {
        "cpu": {"label": "CPU", "size": 16513842, "url": _REL + "macos-arm64.tar.gz",
                "sha256": "00468fe833eb000b78a748122f5921b6c7b07dc82331a8d0c68196c69cb26382"},
        "gpu": {"label": "Metal", "size": 16513842, "url": _REL + "macos-arm64.tar.gz",
                "sha256": "00468fe833eb000b78a748122f5921b6c7b07dc82331a8d0c68196c69cb26382"},
    },
    "darwin-x86_64": {
        "cpu": {"label": "CPU", "size": 12258802, "url": _REL + "macos-x64.tar.gz",
                "sha256": "291d99f3b6f45f67f73afe5381540f29928840a1a14d9c19d6595bd649a035fc"},
    },
}


def _os_key() -> str:
    import platform
    import sys
    if sys.platform == "darwin":
        return "darwin-arm64" if platform.machine() == "arm64" else "darwin-x86_64"
    return "win32" if sys.platform == "win32" else "linux"


RUNTIMES = _RUNTIMES_BY_OS[_os_key()]
_SERVER_EXE = "llama-server.exe" if _os_key() == "win32" else "llama-server"
# Auswahl per Test: 30 Songs mit eindeutigem Subgenre (DnB, Dubstep, House, Trance, Hardstyle), nur Künstler+Titel.
#   Qwen3 4B 10/30 · Gemma 3 4B 16/30 · Qwen3 8B 14/30 · Gemma 3 12B 23/30 · Mistral Small 24B 21/30 · Gemma 3 27B 27/30
MODELS = {
    "light": {"tier": "Leicht", "name": "Gemma 3 4B", "file": "gemma-3-4b-it-Q4_K_M.gguf", "repo": "unsloth/gemma-3-4b-it-GGUF",
              "size": 2489894016, "sha256": "04a43a22e8d2003deda5acc262f68ec1005fa76c735a9962a8c77042a74a7d19",
              "need_gb": 4, "score": 16, "cpu_s": 2.7,
              "desc": "Schnell und sparsam, läuft auf fast jedem Rechner. Kennt vor allem bekannte Künstler."},
    "medium": {"tier": "Mittel", "name": "Gemma 3 12B", "file": "gemma-3-12b-it-Q4_K_M.gguf", "repo": "unsloth/gemma-3-12b-it-GGUF",
               "size": 7300778336, "sha256": "15b8fd9d8672cd4240c178c217ca781409291f34e353d2e913b29c7602ceb3ff",
               "need_gb": 9, "score": 23, "cpu_s": 8.8,
               "desc": "Guter Mittelweg aus Tempo und Musikwissen – empfohlen."},
    "quality": {"tier": "Qualität", "name": "Gemma 3 27B", "file": "gemma-3-27b-it-Q4_K_M.gguf", "repo": "unsloth/gemma-3-27b-it-GGUF",
                "size": 16546688736, "sha256": "f1b699659942c777bd3ec0bcb527d6ebf34ae14ca76e3af103d58d0c9cbdadee",
                "need_gb": 19, "score": 27, "cpu_s": 19.5,
                "desc": "Bestes Musikwissen, kennt auch Nischen-Künstler. Am besten mit großer Grafikkarte."},
}
for _k, _m in MODELS.items():
    _m["url"] = f"https://huggingface.co/{_m['repo']}/resolve/main/{_m['file']}"


def base_dir() -> Path:
    d = Path(config.opt("TUNEBRIDGE_MODELS_DIR") or config.DATA / "llm")
    d.mkdir(parents=True, exist_ok=True)
    return d


def model_path(mid: str) -> Path:
    return base_dir() / "models" / MODELS[mid]["file"]


def runtime_dir(variant: str) -> Path:
    return base_dir() / "runtime" / f"{LLAMA_BUILD}-{variant}"


def server_bin(variant: str) -> Path | None:
    d = runtime_dir(variant)
    if not d.exists():
        return None
    hits = [p for p in d.rglob(_SERVER_EXE) if p.is_file()]
    return hits[0] if hits else None


# ================================================================== Downloads
_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()


def jobs() -> dict[str, dict]:
    with _jobs_lock:
        return {k: {kk: vv for kk, vv in v.items() if kk != "cancel"} for k, v in _jobs.items()}


def _download(job_id: str, url: str, dest: Path, size: int, sha256: str, after=None) -> None:
    part = dest.with_suffix(dest.suffix + ".part")
    dest.parent.mkdir(parents=True, exist_ok=True)
    job = _jobs[job_id]
    try:
        free = shutil.disk_usage(dest.parent).free
        have = part.stat().st_size if part.exists() else 0
        if free < (size - have) + 500_000_000:
            raise RuntimeError(f"Zu wenig Speicherplatz ({free / 1e9:.1f} GB frei, {size / 1e9:.1f} GB nötig)")
        h = hashlib.sha256()
        if have:  # Fortsetzen: vorhandenen Teil in die Prüfsumme einrechnen
            job["state"] = "resuming"
            with part.open("rb") as f:
                for chunk in iter(lambda: f.read(8 << 20), b""):
                    if job["cancel"]:
                        raise InterruptedError
                    h.update(chunk)
        job.update(state="downloading", done=have, total=size)
        headers = {"User-Agent": "SH-Tunebridge", **({"Range": f"bytes={have}-"} if have else {})}
        t_last, b_last = time.time(), have
        with httpx.stream("GET", url, headers=headers, follow_redirects=True, timeout=60) as r:
            if have and r.status_code != 206:  # Server kann nicht fortsetzen -> neu
                have, h = 0, hashlib.sha256()
                job["done"] = 0
            elif r.status_code not in (200, 206):
                raise RuntimeError(f"Download fehlgeschlagen (HTTP {r.status_code})")
            with part.open("ab" if have else "wb") as f:
                for chunk in r.iter_bytes(1 << 20):
                    if job["cancel"]:
                        raise InterruptedError
                    f.write(chunk)
                    h.update(chunk)
                    job["done"] += len(chunk)
                    now = time.time()
                    if now - t_last >= 1:
                        job["speed"] = (job["done"] - b_last) / (now - t_last)
                        t_last, b_last = now, job["done"]
        job["state"] = "verifying"
        if part.stat().st_size != size or h.hexdigest() != sha256:
            part.unlink(missing_ok=True)
            raise RuntimeError("Prüfsumme stimmt nicht – Datei verworfen, bitte erneut laden")
        part.rename(dest)
        if after:
            after(dest)
        job.update(state="done", speed=0)
    except InterruptedError:
        job.update(state="cancelled", speed=0)
    except Exception as e:
        from . import debuglog as dbg
        dbg.error("llm", f"Download {job_id} fehlgeschlagen", e)
        job.update(state="error", error=str(e), speed=0)


def _start_job(job_id: str, url: str, dest: Path, size: int, sha256: str, after=None) -> None:
    with _jobs_lock:
        cur = _jobs.get(job_id)
        if cur and cur["state"] in ("downloading", "verifying", "resuming", "queued"):
            return
        _jobs[job_id] = {"state": "queued", "done": 0, "total": size, "speed": 0, "cancel": False, "error": None}
    threading.Thread(target=_download, args=(job_id, url, dest, size, sha256, after), daemon=True).start()


def download_model(mid: str) -> None:
    m = MODELS[mid]
    if model_path(mid).exists():
        return
    if not settings()["terms_accepted"]:
        raise PermissionError("Bitte zuerst die Gemma-Nutzungsbedingungen bestätigen")
    _start_job(f"model:{mid}", m["url"], model_path(mid), m["size"], m["sha256"])
    download_runtime(settings()["device"])  # Laufzeit gleich mitladen (klein)


def _extract_runtime(variant: str):
    def run(archive: Path) -> None:
        target = runtime_dir(variant)
        tmp = target.with_name(target.name + ".tmp")
        shutil.rmtree(tmp, ignore_errors=True)
        tmp.mkdir(parents=True)
        if archive.suffix == ".zip":
            import zipfile
            with zipfile.ZipFile(archive) as z:
                for m in z.infolist():   # sicher: keine Pfade außerhalb des Zielordners
                    dest = (tmp / m.filename).resolve()
                    if not str(dest).startswith(str(tmp.resolve())):
                        raise RuntimeError("Unsicherer Pfad im Archiv")
                z.extractall(tmp)
        else:
            with tarfile.open(archive) as t:
                t.extractall(tmp, filter="data")  # sicher: keine Pfade außerhalb, keine Gerätedateien
        shutil.rmtree(target, ignore_errors=True)
        tmp.rename(target)
        archive.unlink(missing_ok=True)
        for p in target.rglob(_SERVER_EXE):
            p.chmod(0o755)
    return run


def download_runtime(variant: str) -> None:
    if server_bin(variant):
        return
    r = RUNTIMES[variant]
    ext = ".zip" if r["url"].endswith(".zip") else ".tar.gz"
    archive = base_dir() / "runtime" / f"llama-{LLAMA_BUILD}-{variant}{ext}"
    _start_job(f"runtime:{variant}", r["url"], archive, r["size"], r["sha256"], after=_extract_runtime(variant))


def cancel(job_id: str) -> None:
    with _jobs_lock:
        if job_id in _jobs:
            _jobs[job_id]["cancel"] = True


def delete_model(mid: str) -> None:
    if _runner.model == mid:
        stop()
    cancel(f"model:{mid}")
    model_path(mid).unlink(missing_ok=True)
    model_path(mid).with_suffix(".gguf.part").unlink(missing_ok=True)
    with _jobs_lock:
        _jobs.pop(f"model:{mid}", None)


# ================================================================== Einstellungen (pro Rechner)
_PREF = f"llm:{store.HOST}"
DEFAULTS = {"enabled": False, "model": "medium", "device": "cpu", "gpu": "", "idle_minutes": 10,
            "terms_accepted": False}  # Gemma-Nutzungsbedingungen bestätigt?
TERMS_URL = "https://ai.google.dev/gemma/terms"
POLICY_URL = "https://ai.google.dev/gemma/prohibited_use_policy"


def settings() -> dict:
    raw = store.meta_get(_PREF)
    return {**DEFAULTS, **(json.loads(raw) if raw else {})}


def save_settings(patch: dict) -> dict:
    cur = settings()
    cur.update({k: v for k, v in patch.items() if k in DEFAULTS})
    store.meta_set(_PREF, json.dumps(cur))
    if cur["enabled"] or "device" in patch:
        download_runtime(cur["device"])
    if _runner.proc and (_runner.model != cur["model"] or _runner.device != cur["device"] or _runner.gpu != cur["gpu"]
                         or not cur["enabled"]):
        stop()  # beim nächsten Bedarf mit neuer Einstellung starten
    return cur


# ================================================================== System-Infos
def ram_gb() -> dict:
    from .osutil import ram_gb as _r
    return _r()


def physical_cores() -> int:
    from .osutil import physical_cores as _c
    return _c()


_gpu_cache: dict = {}


def gpus() -> list[dict]:
    """Grafikkarten über den Vulkan-Build auflisten (nur lesen, nichts wird verstellt)."""
    b = server_bin("gpu")
    if not b:
        return []
    if _gpu_cache.get("bin") == str(b) and time.time() - _gpu_cache.get("t", 0) < 30:
        return _gpu_cache["list"]
    try:
        opts = {k: v for k, v in _child_opts(b.parent).items() if k != "preexec_fn"}
        r = subprocess.run([str(b), "--list-devices"], capture_output=True, text=True, timeout=20, **opts)
        out = r.stdout + r.stderr
    except (subprocess.SubprocessError, OSError):
        return []
    lst = []
    for m in re.finditer(r"^\s*(Vulkan\d+):\s*(.+?)\s*\((\d+)\s*MiB,\s*(\d+)\s*MiB free\)", out, re.M):
        lst.append({"id": m.group(1), "name": m.group(2), "vram_gb": round(int(m.group(3)) / 1024, 1),
                    "free_gb": round(int(m.group(4)) / 1024, 1)})
    _gpu_cache.update(bin=str(b), t=time.time(), list=lst)
    return lst


# ================================================================== Server
class _Runner:
    def __init__(self):
        self.proc: subprocess.Popen | None = None
        self.model = self.device = self.gpu = None
        self.state = "stopped"      # stopped | starting | running | error
        self.error = None
        self.last_used = 0.0
        self.lock = threading.Lock()
        self.log: Path | None = None


_runner = _Runner()


def _child_opts(lib_dir: Path) -> dict:
    """Server stirbt mit der App (Linux) bzw. wird beim Beenden gestoppt (atexit); Bibliothekspfad setzen."""
    from . import osutil
    env = {**os.environ}
    if osutil.LINUX:
        env["LD_LIBRARY_PATH"] = str(lib_dir)
        return {"preexec_fn": osutil.die_with_parent, "env": env}
    if osutil.MACOS:
        env["DYLD_LIBRARY_PATH"] = str(lib_dir)
        return {"env": env}
    env["PATH"] = str(lib_dir) + os.pathsep + env.get("PATH", "")     # Windows: DLLs neben der .exe
    return {"env": env, **osutil.popen_flags()}


def status() -> dict:
    r = _runner
    if r.proc and r.proc.poll() is not None and r.state != "stopped":
        tail = r.log.read_text(errors="replace")[-4000:].lower() if r.log and r.log.exists() else ""
        if "out of memory" in tail or "failed to allocate" in tail:
            msg = "Grafikspeicher/RAM reicht nicht – kleineres Modell wählen oder andere Programme schließen"
        else:
            msg = f"Server beendet (Code {r.proc.returncode}) – Details in {r.log}"
        r.state, r.error = "error", msg
        r.proc = None
    return {"state": r.state, "model": r.model, "device": r.device, "gpu": r.gpu, "error": r.error,
            "idle_for": round(time.time() - r.last_used) if r.last_used else None}


def stop() -> None:
    r = _runner
    with r.lock:
        if r.proc and r.proc.poll() is None:
            r.proc.terminate()
            try:
                r.proc.wait(10)
            except subprocess.TimeoutExpired:
                r.proc.kill()
        r.proc, r.state, r.model = None, "stopped", None


def _start(s: dict) -> None:
    r = _runner
    variant = "gpu" if s["device"] == "gpu" else "cpu"
    b = server_bin(variant)
    if not b:
        raise RuntimeError("Laufzeit (llama.cpp) ist noch nicht heruntergeladen")
    mp = model_path(s["model"])
    if not mp.exists():
        raise RuntimeError(f"Modell {MODELS[s['model']]['name']} ist noch nicht heruntergeladen")
    cmd = [str(b), "-m", str(mp), "--host", "127.0.0.1", "--port", str(PORT), "-c", "4096", "-np", "1",
           "--jinja", "--no-webui"]
    if variant == "gpu":
        cmd += ["-ngl", "999"] + (["--device", s["gpu"]] if s.get("gpu") else [])
    else:
        cmd += ["-ngl", "0", "-t", str(physical_cores())]
    r.log = base_dir() / "server.log"
    r.proc = subprocess.Popen(cmd, stdout=r.log.open("wb"), stderr=subprocess.STDOUT, **_child_opts(b.parent))
    import atexit
    atexit.register(stop)
    r.model, r.device, r.gpu, r.state, r.error = s["model"], s["device"], s.get("gpu"), "starting", None


def ensure_running(wait: float = 180) -> str | None:
    """URL des laufenden Servers; startet ihn bei Bedarf. None, wenn (noch) nicht bereit."""
    s = settings()
    if not s["enabled"] or not s["terms_accepted"]:
        return None
    r = _runner
    with r.lock:
        if r.proc and r.proc.poll() is None and (r.model, r.device, r.gpu) != (s["model"], s["device"], s.get("gpu")):
            r.proc.terminate()
            r.proc.wait(10)
            r.proc = None
        if not (r.proc and r.proc.poll() is None):
            try:
                _start(s)
            except Exception as e:
                from . import debuglog as dbg
                dbg.error("llm", "llama-server startet nicht", e, modell=s.get("model"), gerät=s.get("device"))
                r.state, r.error = "error", str(e)
                return None
    url = f"http://127.0.0.1:{PORT}"
    t0 = time.time()
    while time.time() - t0 < wait:
        if r.proc is None or r.proc.poll() is not None:
            status()
            return None
        try:
            if httpx.get(url + "/health", timeout=2).status_code == 200:
                r.state, r.last_used = "running", time.time()
                return url + "/v1"
        except httpx.HTTPError:
            pass
        time.sleep(0.5)
    return None


def warm() -> None:
    """Im Hintergrund schon mal starten (z.B. wenn „Erkennen“ geöffnet wird)."""
    s = settings()
    if s["enabled"] and model_path(s["model"]).exists() and server_bin(s["device"]):
        threading.Thread(target=ensure_running, daemon=True).start()


def _idle_watch():
    while True:
        time.sleep(30)
        r, s = _runner, settings()
        if r.state == "running" and r.last_used and time.time() - r.last_used > s["idle_minutes"] * 60:
            stop()


threading.Thread(target=_idle_watch, daemon=True).start()


def chat(prompt: str, wait: float = 180, max_tokens: int = 200) -> str | None:
    url = ensure_running(wait)
    if not url:
        return None
    r = httpx.post(url + "/chat/completions", timeout=120, json={
        "model": "local", "temperature": 0, "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
        "chat_template_kwargs": {"enable_thinking": False},
    })
    _runner.last_used = time.time()
    text = r.json()["choices"][0]["message"]["content"]
    return re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()


# ================================================================== Übersicht für die UI
def overview() -> dict:
    s = settings()
    js = jobs()
    models = []
    for mid, m in MODELS.items():
        models.append({"id": mid, **{k: m[k] for k in ("tier", "name", "size", "need_gb", "desc", "score", "cpu_s")},
                       "downloaded": model_path(mid).exists(), "job": js.get(f"model:{mid}")})
    return {
        "settings": s, "models": models, "terms_url": TERMS_URL, "policy_url": POLICY_URL, "server": status(),
        "runtime": {v: {"installed": bool(server_bin(v)), "job": js.get(f"runtime:{v}"), "build": LLAMA_BUILD}
                    for v in RUNTIMES},
        "ram": ram_gb(), "gpus": gpus(), "cores": physical_cores(),
        "disk_free_gb": round(shutil.disk_usage(base_dir()).free / 1e9, 1), "dir": str(base_dir()),
    }

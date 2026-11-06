"""Auto-Updater: neue Versionen aus GitHub holen – nur signierte Releases.

Sicherheitsmodell
  * Es werden nur Git-Tags `vX.Y.Z` betrachtet – nicht jeder Push auf main.
  * Ein Tag wird nur installiert, wenn er mit einem Schlüssel aus `release_signers`
    signiert ist. Diese Datei stammt aus der *bereits installierten* Version –
    wer nur das GitHub-Repo kontrolliert, kann also keine fremde Version unterschieben.
  * Die Version im Tag muss zur Version in pyproject.toml passen.
  * Vor der Installation wird automatisch ein Backup der Datenbank angelegt.
  * Installiert wird nur auf Klick – nie still im Hintergrund.
  * Es wird nur die Datei für *dieses* System und *diesen* Prozessor genommen (Name im signierten Manifest,
    z. B. `-windows-x64.zip`, `-macos-arm64.dmg`, `-x86_64.AppImage`). Passt keine, wird nichts angeboten.
  * Windows/macOS: neue Version wird neben die alte entpackt und nach dem Beenden ausgetauscht
    (kleines Hilfsskript wartet, bis die App zu ist). Ist der Ordner nicht beschreibbar, landet sie geprüft in „Downloads“.
"""

from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
import tempfile
import threading
import time
from importlib import metadata, resources
from pathlib import Path

from . import config, store

# Wird beim Einrichten des GitHub-Repos gesetzt; per UPDATE_REPO in der config überschreibbar.
DEFAULT_REPO = "https://github.com/Bigsmoke002/SH-Tunebridge.git"
CHECK_EVERY = 3600          # neue Versionen spätestens nach 1 h bemerken
RETRY_ERROR = 15 * 60       # offline/GitHub gestört: bald erneut versuchen
_TAG = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")
_prepared: dict = {}
_lock = threading.Lock()


def repo() -> str:
    return config.opt("UPDATE_REPO") or DEFAULT_REPO


def current() -> str:
    # Entwickler-/editable-Installation: die Paket-Metadaten stammen vom ersten Installieren und veralten –
    # maßgeblich ist dann pyproject.toml im Quellordner (sonst meldet die App ewig ein „Update“).
    py = Path(__file__).resolve().parents[2] / "pyproject.toml"
    if py.exists():
        m = re.search(r'^version\s*=\s*"([^"]+)"', py.read_text(encoding="utf-8"), re.M)
        if m:
            return m.group(1)
    try:
        return metadata.version("tunebridge")
    except metadata.PackageNotFoundError:
        return "0.0.0"


class Incompatible(RuntimeError):
    """Release vorhanden, aber nicht für diesen Prozessor gebaut."""


class NotReady(RuntimeError):
    """Release angelegt, aber die Dateien für dieses System werden noch hochgeladen – kein Fehler, später erneut."""


def machine() -> str:
    m = platform.machine().lower()
    return {"amd64": "x86_64", "x64": "x86_64", "aarch64": "arm64"}.get(m, m)


def arch_ok(fname: str) -> bool:
    """Passt die Release-Datei (laut Namen) zu diesem Prozessor? Windows auf ARM kann x64-Programme emulieren."""
    from . import osutil
    f, m = fname.lower(), machine()
    if "arm64" in f or "aarch64" in f:
        return m == "arm64"
    if "x64" in f or "x86_64" in f or "amd64" in f:
        return m == "x86_64" or (osutil.WINDOWS and m == "arm64")
    return True            # ohne Angabe: als passend behandeln (ältere Releases)


def _v(s: str) -> tuple[int, ...]:
    m = re.match(r"v?(\d+)\.(\d+)\.(\d+)", s)
    return tuple(int(x) for x in m.groups()) if m else (0, 0, 0)


# ------------------------------------------------------------------ AppImage
# Im AppImage gibt es kein git/uv. Stattdessen: GitHub-Release mit
#   SH-Tunebridge-<v>-x86_64.AppImage, SH-Tunebridge-<v>.manifest, SH-Tunebridge-<v>.manifest.sig
# Das Manifest (Version, Dateiname, Größe, SHA256, Notizen) ist mit dem Release-Schlüssel signiert
# (ssh-keygen -Y sign, Namespace RELEASE_NS). Erst Signatur prüfen, dann AppImage laden und Hash vergleichen.
RELEASE_NS = "sh-tunebridge-release"


def is_appimage() -> bool:
    p = os.environ.get("APPIMAGE")
    return bool(p) and Path(p).is_file()


def is_frozen() -> bool:
    """Fertiges Programm für Windows/macOS (PyInstaller). Dort wird die neue Version nur
    signaturgeprüft in „Downloads“ gelegt – installieren tust du sie selbst (kein stiller Austausch)."""
    import sys
    return bool(getattr(sys, "frozen", False)) and not is_appimage()


def _release_base(tag: str) -> str:
    from . import osutil
    suffix = "-windows" if osutil.WINDOWS else "-macos" if osutil.MACOS else ""
    return f"SH-Tunebridge-{tag[1:]}{suffix}"


def _slug() -> str | None:
    m = re.search(r"github\.com[:/]([^/]+/[^/]+?)(?:\.git)?/?$", repo()) or \
        re.search(r"^git@[^:]+:([^/]+/[^/]+?)(?:\.git)?$", repo())
    return m.group(1) if m else None


def _http():
    import httpx
    return httpx.Client(timeout=30, follow_redirects=True, headers={"User-Agent": "SH-Tunebridge-Updater",
                                                                     "Accept": "application/vnd.github+json"})


def _releases() -> list[dict]:
    slug = _slug()
    if not slug:
        raise RuntimeError("Update-Quelle ist kein GitHub-Repo")
    with _http() as c:
        r = c.get(f"https://api.github.com/repos/{slug}/releases", params={"per_page": 15})
        if r.status_code == 404:
            raise RuntimeError("Keine Releases gefunden (Repo privat?)")
        r.raise_for_status()
        rels = [x for x in r.json() if not x.get("draft") and not x.get("prerelease") and _TAG.match(x["tag_name"])]
    return sorted(rels, key=lambda x: _v(x["tag_name"]), reverse=True)


def _verify_manifest(manifest: bytes, sig: bytes) -> dict:
    from . import sshsig
    try:  # gleiche Regeln wie `ssh-keygen -Y verify`, aber ohne externes Programm (Windows/macOS/Linux gleich)
        sshsig.verify(manifest, sig, _signers_file().read_text(encoding="utf-8"), "sh-tunebridge", RELEASE_NS)
    except sshsig.SigError as e:
        raise RuntimeError("Signatur ungültig oder fehlt – Update wird NICHT installiert.") from e
    text = manifest.decode()
    head, _, notes = text.partition("\n\n")
    fields = dict(line.split("=", 1) for line in head.splitlines()[1:] if "=" in line)
    if not head.startswith("SH-Tunebridge-Release 1") or not {"version", "file", "size", "sha256"} <= fields.keys():
        raise RuntimeError("Manifest unvollständig – Update abgebrochen.")
    fields["notes"] = notes.strip()
    return fields


def _prepare_appimage(rel: dict) -> dict:
    tag = rel["tag_name"]
    assets = {a["name"]: a["browser_download_url"] for a in rel.get("assets", [])}
    base = _release_base(tag)
    if f"{base}.manifest" not in assets or f"{base}.manifest.sig" not in assets:
        raise NotReady(f"{tag}: Dateien für dieses System noch nicht hochgeladen")
    with _http() as c:
        man = c.get(assets[f"{base}.manifest"]).content
        sig = c.get(assets[f"{base}.manifest.sig"]).content
    f = _verify_manifest(man, sig)
    if f"v{f['version']}" != tag:
        raise RuntimeError("Version im Manifest passt nicht zum Release – Update abgebrochen.")
    if "/" in f["file"] or "\\" in f["file"]:
        raise RuntimeError("Ungültiger Dateiname im Manifest")
    if f["file"] not in assets:
        raise NotReady(f"{tag}: Programmdatei noch nicht hochgeladen")
    if not arch_ok(f["file"]):
        raise Incompatible(f"{tag} gibt es nicht für deinen Prozessor ({machine()}) – nur als {f['file']}.")
    info = {"tag": tag, "file": f["file"], "url": assets[f["file"]], "size": int(f["size"]), "sha256": f["sha256"],
            "notes": f["notes"]}
    with _lock:
        _prepared.clear()
        _prepared.update(appimage=info, tag=tag)
    return {"tag": tag, "verified": True, "signature": "Manifest mit Release-Schlüssel signiert", "notes": f["notes"]}


def _download_verified(info: dict, tmp: Path, h) -> None:
    with _http() as c, c.stream("GET", info["url"]) as r, tmp.open("wb") as out:
        r.raise_for_status()
        for chunk in r.iter_bytes(1 << 20):
            out.write(chunk)
            h.update(chunk)
    if tmp.stat().st_size != info["size"] or h.hexdigest() != info["sha256"]:
        raise RuntimeError("Prüfsumme stimmt nicht – Update verworfen.")


def _install_download() -> dict:
    """Windows/macOS: geprüfte neue Version nach „Downloads“ legen und den Ordner öffnen."""
    import hashlib

    from . import backup, osutil
    with _lock:
        info = _prepared.get("appimage")
    if not info:
        raise RuntimeError("Update ist nicht vorbereitet")
    dest_dir = osutil.downloads_dir()
    target = dest_dir / info["file"]
    tmp = dest_dir / f".{info['file']}.download"
    if shutil.disk_usage(dest_dir).free < info["size"] + 100_000_000:
        raise RuntimeError("Zu wenig Speicherplatz für das Update")
    safety = backup.create(kind="vor-update")
    try:
        _download_verified(info, tmp, hashlib.sha256())
        os.replace(tmp, target)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    try:
        osutil.open_path(dest_dir)
    except (OSError, osutil.OpenError):
        pass
    store.cache_set("update", "latest", {"tag": info["tag"], "checked": time.time(), "error": None})
    return {"installed": info["tag"], "safety_backup": safety.name, "downloaded": str(target), "manual": True}


def _install_appimage() -> dict:
    with _lock:
        info = _prepared.get("appimage")
    if not info:
        raise RuntimeError("Update ist nicht vorbereitet")
    import hashlib
    cur = Path(os.environ["APPIMAGE"]).resolve()
    target = cur.with_name(info["file"])
    tmp = cur.with_name(f".{info['file']}.download")
    if not os.access(cur.parent, os.W_OK):
        raise RuntimeError(f"Ordner {cur.parent} ist nicht beschreibbar – AppImage bitte z. B. nach ~/Programme legen.")
    if shutil.disk_usage(cur.parent).free < info["size"] + 100_000_000:
        raise RuntimeError("Zu wenig Speicherplatz für das Update")
    from . import backup
    safety = backup.create(kind="vor-update")
    try:
        _download_verified(info, tmp, hashlib.sha256())
        tmp.chmod(0o755)
        os.replace(tmp, target)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    if target != cur:
        target = _keep_old_path(cur, target)
    with _lock:
        _prepared["new_path"] = str(target)
    integrate_desktop(target)
    store.cache_set("update", "latest", {"tag": info["tag"], "checked": time.time(), "error": None})
    return {"installed": info["tag"], "safety_backup": safety.name}


def _keep_old_path(cur: Path, target: Path) -> Path:
    """Die alte Datei durch einen Verweis auf die neue ersetzen. Starter, Panel-Pins und Autostart-Einträge, die
    noch den alten Dateinamen kennen, starten so weiter – statt „Programm … ist nicht auffindbar“.
    Gibt den Pfad zurück, unter dem die neue Version jetzt liegt."""
    link = cur.with_name(f".{cur.name}.link")
    try:
        link.unlink(missing_ok=True)
        link.symlink_to(target.name)          # relativ: funktioniert auch, wenn der Ordner verschoben wird
        os.replace(link, cur)                 # alte Version läuft weiter (Datei bleibt geöffnet), bis neu gestartet
        return target
    except OSError:                           # Dateisystem ohne Verweise (z. B. exFAT): neue Version unter altem Namen
        link.unlink(missing_ok=True)
        os.replace(target, cur)
        return cur


_OLD_NAME = re.compile(r"(/[^\s\"'=,;]*/SH-Tunebridge-\d+\.\d+\.\d+-[A-Za-z0-9_]+\.AppImage)")


def heal_old_paths(path: Path | None = None) -> list[str]:
    """Bis v0.6.0 löschte das Update die alte AppImage-Datei – Starter, Panel-Pins und Autostart mit dem alten
    Namen zeigten danach ins Leere („Programm … ist nicht auffindbar“). Fehlt eine solche Datei im Ordner der
    laufenden Version, wird sie als Verweis auf die aktuelle Version neu angelegt. Nur dort, nur SH-Tunebridge-Namen."""
    cur = Path(path or os.environ.get("APPIMAGE", "")).resolve()
    if not cur.is_file():
        return []
    home, cfg = Path.home(), Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    files = [*(home / ".local/share/applications").glob("*.desktop"), *(cfg / "autostart").glob("*.desktop"),
             *(home / "Desktop").glob("*.desktop"), *(home / "Schreibtisch").glob("*.desktop"),
             cfg / "plasma-org.kde.plasma.desktop-appletsrc"]
    made = []
    for f in files:
        try:
            if not f.is_file() or f.stat().st_size > 2_000_000:
                continue
            text = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for m in set(_OLD_NAME.findall(text)):
            old = Path(m)
            if old.parent != cur.parent or old.name == cur.name or old.exists() or old.is_symlink():
                continue
            try:
                old.symlink_to(cur.name)
                made.append(str(old))
            except OSError:
                pass
    return made


def integrate_desktop(path: Path | None = None) -> None:
    """AppImage ins Startmenü eintragen (bzw. Pfad aktualisieren)."""
    path = Path(path or os.environ.get("APPIMAGE", ""))
    if not path.is_file():
        return
    apps = Path.home() / ".local/share/applications"
    icons = Path.home() / ".local/share/icons/hicolor/scalable/apps"
    apps.mkdir(parents=True, exist_ok=True)
    icons.mkdir(parents=True, exist_ok=True)
    icon_src = Path(str(resources.files("tunebridge") / "web/static/icon.svg"))
    if icon_src.exists():
        shutil.copyfile(icon_src, icons / "sh-tunebridge.svg")
    entry = apps / "sh-tunebridge.desktop"
    text = ("[Desktop Entry]\nType=Application\nName=SH-Tunebridge\n"
            "Comment=Songs erkennen, nach Genre sortieren, Playlists übertragen\n"
            f'Exec="{path}" %U\nIcon=sh-tunebridge\nCategories=AudioVideo;Audio;\n'
            "StartupWMClass=tunebridge\nTerminal=false\nX-SH-Tunebridge-AppImage=true\n")
    if not entry.exists() or entry.read_text(encoding="utf-8") != text:
        entry.write_text(text, encoding="utf-8")


def is_dev_install() -> bool:
    """Läuft direkt aus einem Git-Checkout (Entwicklerrechner)? Dann per git pull aktualisieren."""
    if is_frozen():
        return False
    root = Path(__file__).resolve().parents[2]
    return (root / ".git").exists()


def _git(*args: str, cwd: Path | None = None, timeout: int = 60) -> subprocess.CompletedProcess:
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=timeout, env=env)


def remote_tags() -> list[str]:
    """Alle Versions-Tags im Repo, neueste zuerst."""
    if not repo():
        return []
    r = _git("ls-remote", "--tags", "--refs", repo(), timeout=30)
    if r.returncode != 0:
        err = r.stderr.strip()
        if re.search(r"could not read Username|Authentication failed|Repository not found|Permission denied", err, re.I):
            raise RuntimeError("Kein Zugriff auf das Update-Repo (privat?) – Repo öffentlich machen "
                               "oder diesem Rechner einen Lese-Schlüssel geben (siehe README).")
        raise RuntimeError(err.splitlines()[-1] if err else "GitHub nicht erreichbar")
    tags = [line.split("refs/tags/")[1] for line in r.stdout.splitlines() if "refs/tags/" in line]
    return sorted((t for t in tags if _TAG.match(t)), key=_v, reverse=True)


def _latest_valid_appimage() -> tuple[str | None, list[str]]:
    skipped = []
    for rel in _releases():
        if _v(rel["tag_name"]) <= _v(current()):
            break
        try:
            _prepare_appimage(rel)
            return rel["tag_name"], skipped
        except Incompatible:
            raise
        except NotReady:
            continue
        except Exception as e:
            from . import debuglog as dbg
            dbg.error("update", f"Release {rel['tag_name']} übersprungen (ungültig/unsigniert?)", e)
            skipped.append(rel["tag_name"])
    return None, skipped


def latest_valid_tag() -> tuple[str | None, list[str]]:
    """Neueste Version, die wirklich signiert ist. Ungültige Tags werden übersprungen
    (sonst könnte ein gefälschter Tag echte Updates verdecken)."""
    skipped = []
    for t in remote_tags():
        if _v(t) <= _v(current()):
            break
        try:
            prepare(t)
            return t, skipped
        except Exception as e:
            from . import debuglog as dbg
            dbg.error("update", f"Tag {t} übersprungen (ungültig/unsigniert?)", e)
            skipped.append(t)
    return None, skipped


def check(force: bool = False) -> dict:
    kind = ("appimage" if is_appimage() else ("frozen" if frozen_writable() else "download") if is_frozen()
            else "dev" if is_dev_install() else "uv")
    info = {"current": current(), "repo": repo(), "dev": is_dev_install(), "configured": bool(repo()),
            "kind": kind, "system": f"{platform.system()} {machine()}"}
    if not repo():
        return {**info, "available": False, "latest": None, "error": None}
    cached = store.cache_get("update", "latest", max_age=None if force else CHECK_EVERY)
    if cached and cached.get("error") and time.time() - cached.get("checked", 0) > RETRY_ERROR:
        cached = None
    if cached and cached.get("for") not in (None, current()):
        cached = None      # nach einem Update: Ergebnis der alten Version zählt nicht mehr
    if cached and not force:
        tag, checked, err, skipped = cached["tag"], cached["checked"], cached.get("error"), cached.get("skipped", [])
    else:
        try:
            (tag, skipped), err = (_latest_valid_appimage() if is_appimage() or is_frozen() else latest_valid_tag()), None
        except Incompatible as e:      # Release da, aber nicht für diesen Prozessor
            tag, skipped, err = None, [], str(e)
        except Exception as e:  # offline o.ä.
            from . import debuglog as dbg
            dbg.error("update", "Update-Prüfung fehlgeschlagen", e)
            tag, skipped, err = None, [], str(e)
        checked = time.time()
        store.cache_set("update", "latest", {"tag": tag, "checked": checked, "error": err, "skipped": skipped,
                                             "for": current()})
    available = bool(tag) and _v(tag) > _v(current())
    return {**info, "latest": tag, "available": available, "checked": checked, "error": err,
            "skipped": skipped}


def _signers_file() -> Path:
    return Path(str(resources.files("tunebridge") / "release_signers"))


def prepare(tag: str) -> dict:
    """Tag holen, Signatur + Version prüfen, Änderungen auslesen. Installiert noch nichts."""
    if not _TAG.match(tag):
        raise ValueError("Ungültige Version")
    if is_appimage() or is_frozen():
        rel = next((r for r in _releases() if r["tag_name"] == tag), None)
        if not rel:
            raise RuntimeError("Release nicht gefunden")
        return _prepare_appimage(rel)
    tmp = Path(tempfile.mkdtemp(prefix="sh-tunebridge-update-"))
    try:
        for args in (("init", "-q"), ("remote", "add", "origin", repo()),
                     ("fetch", "-q", "--depth", "1", "origin", f"refs/tags/{tag}:refs/tags/{tag}"),
                     ("checkout", "-q", tag)):
            r = _git(*args, cwd=tmp, timeout=120)
            if r.returncode != 0:
                raise RuntimeError(f"git {args[0]}: {r.stderr.strip()}")
        v = _git("-c", f"gpg.ssh.allowedSignersFile={_signers_file()}", "verify-tag", tag, cwd=tmp)
        if v.returncode != 0:
            raise RuntimeError("Signatur ungültig oder fehlt – Update wird NICHT installiert.")
        sig = (v.stderr.strip().splitlines() or [""])[0]
        pyver = re.search(r'^version\s*=\s*"([^"]+)"', (tmp / "pyproject.toml").read_text(encoding="utf-8"), re.M)
        if not pyver or f"v{pyver.group(1)}" != tag:
            raise RuntimeError("Version im Paket passt nicht zum Tag – Update abgebrochen.")
        notes = _git("tag", "-l", "--format=%(contents)", tag, cwd=tmp).stdout
        notes = re.sub(r"-----BEGIN SSH SIGNATURE-----.*?-----END SSH SIGNATURE-----", "", notes, flags=re.S).strip()
    except Exception:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    with _lock:
        old = _prepared.pop("dir", None)
        if old:
            shutil.rmtree(old, ignore_errors=True)
        _prepared.update(dir=tmp, tag=tag)
    return {"tag": tag, "verified": True, "signature": sig, "notes": notes}


def frozen_root() -> Path:
    """Was beim Update ersetzt wird: Windows = Programmordner, macOS = das .app-Paket."""
    import sys

    from . import osutil
    exe = Path(sys.executable).resolve()
    if osutil.MACOS:
        for p in exe.parents:
            if p.suffix == ".app":
                return p
    return exe.parent


def frozen_writable() -> bool:
    try:
        root = frozen_root()
        return os.access(root, os.W_OK) and os.access(root.parent, os.W_OK)
    except Exception:  # noqa: BLE001
        return False


def _install_frozen() -> dict:
    """Windows/macOS: geprüftes Paket holen und *neben* die laufende Version entpacken.
    Ausgetauscht wird erst beim Neustart (restart), wenn die App beendet ist."""
    import hashlib
    import zipfile

    from . import backup, osutil
    with _lock:
        info = _prepared.get("appimage")
    if not info:
        raise RuntimeError("Update ist nicht vorbereitet")
    root = frozen_root()
    if shutil.disk_usage(root.parent).free < info["size"] * 3 + 200_000_000:
        raise RuntimeError("Zu wenig Speicherplatz für das Update")
    safety = backup.create(kind="vor-update")
    work = Path(tempfile.mkdtemp(prefix="sh-tunebridge-update-"))
    new = root.with_name(f".{root.name}.neu")
    shutil.rmtree(new, ignore_errors=True)
    try:
        pkg = work / info["file"]
        _download_verified(info, pkg, hashlib.sha256())
        if osutil.WINDOWS:
            with zipfile.ZipFile(pkg) as z:
                for n in z.namelist():                      # Schutz vor „../“ im Archiv
                    if n.startswith(("/", "\\")) or ".." in Path(n).parts:
                        raise RuntimeError("Update-Archiv ungültig")
                z.extractall(work / "x")
            exe = next((work / "x").rglob("SH-Tunebridge.exe"), None)
            if not exe:
                raise RuntimeError("Update-Archiv enthält kein Programm")
            shutil.move(str(exe.parent), str(new))
            for f in root.glob("unins*"):               # per Setup installiert: Deinstaller mitnehmen
                if f.is_file():
                    shutil.copy2(f, new / f.name)
        elif osutil.MACOS:
            mnt = work / "mnt"
            mnt.mkdir()
            r = subprocess.run(["hdiutil", "attach", "-nobrowse", "-readonly", "-noautoopen", "-mountpoint", str(mnt),
                                str(pkg)], capture_output=True, text=True, timeout=180)
            if r.returncode != 0:
                raise RuntimeError("Disk-Image ließ sich nicht öffnen: " + r.stderr.strip()[-200:])
            try:
                app = mnt if (mnt / "Contents").is_dir() else next(mnt.glob("*.app"), None)
                if not app:
                    raise RuntimeError("Disk-Image enthält keine App")
                subprocess.run(["ditto", str(app), str(new)], check=True, timeout=600)
            finally:
                subprocess.run(["hdiutil", "detach", "-quiet", str(mnt)], timeout=60)
        else:
            raise RuntimeError("Nicht unterstütztes System")
    except BaseException:
        shutil.rmtree(new, ignore_errors=True)
        shutil.rmtree(work, ignore_errors=True)
        raise
    with _lock:
        _prepared["swap"] = {"new": str(new), "target": str(root), "work": str(work)}
    store.cache_set("update", "latest", {"tag": info["tag"], "checked": time.time(), "error": None})
    return {"installed": info["tag"], "safety_backup": safety.name}


def _swap_and_restart() -> None:
    """Hilfsskript starten: wartet, bis diese App beendet ist, tauscht alt gegen neu und startet neu.
    Klappt der Tausch nicht, wird die alte Version wiederhergestellt."""
    from . import osutil
    with _lock:
        sw = _prepared.get("swap")
    if not sw:
        raise RuntimeError("Update ist nicht installiert")
    pid, t, n, w = os.getpid(), sw["target"], sw["new"], sw["work"]
    try:                      # Tray/Schwebe-Icon läuft aus demselben Ordner -> vor dem Tausch beenden
        from .web import app as web
        web.companion_stop()
    except Exception:  # noqa: BLE001
        pass
    if osutil.WINDOWS:
        q = lambda x: "'" + x.replace("'", "''") + "'"  # noqa: E731 – PowerShell-String
        script = Path(w) / "tausch.ps1"
        script.write_text(f"""$ErrorActionPreference = 'Stop'
while (Get-Process -Id {pid} -ErrorAction SilentlyContinue) {{ Start-Sleep -Milliseconds 300 }}
Start-Sleep -Milliseconds 500
$t = {q(t)}; $n = {q(n)}; $b = $t + '.alt'
if (Test-Path $b) {{ Remove-Item -Recurse -Force $b }}
try {{ Move-Item $t $b; Move-Item $n $t }}
catch {{ if ((Test-Path $b) -and -not (Test-Path $t)) {{ Move-Item $b $t }} }}
Start-Process (Join-Path $t 'SH-Tunebridge.exe')
Start-Sleep -Seconds 3
Remove-Item -Recurse -Force $b -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force {q(w)} -ErrorAction SilentlyContinue
""", encoding="utf-8-sig")
        flags = 0x00000008 | 0x00000200 | 0x08000000      # DETACHED_PROCESS | NEW_PROCESS_GROUP | NO_WINDOW
        subprocess.Popen(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden",
                          "-File", str(script)], creationflags=flags, close_fds=True)
    else:
        import shlex
        T, N, W = shlex.quote(t), shlex.quote(n), shlex.quote(w)
        cmd = (f"while kill -0 {pid} 2>/dev/null; do sleep 0.3; done; sleep 0.5; "
               f"rm -rf {T}.alt; if mv {T} {T}.alt && mv {N} {T}; then rm -rf {T}.alt; "
               f"else [ -d {T}.alt ] && [ ! -d {T} ] && mv {T}.alt {T}; fi; open {T}; rm -rf {W}")
        subprocess.Popen(["/bin/sh", "-c", cmd], start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    threading.Timer(0.6, lambda: os._exit(0)).start()


def install() -> dict:
    if is_appimage():
        return _install_appimage()
    if is_frozen():
        return _install_frozen() if frozen_writable() else _install_download()
    with _lock:
        d, tag = _prepared.get("dir"), _prepared.get("tag")
    if not d or not Path(d).exists():
        raise RuntimeError("Update ist nicht vorbereitet")
    if is_dev_install():
        raise RuntimeError("Entwicklerinstallation – bitte per `git pull` aktualisieren.")
    uv = shutil.which("uv") or str(Path.home() / ".local/bin/uv")
    from . import backup
    safety = backup.create(kind="vor-update")
    r = subprocess.run([uv, "tool", "install", "--force", f"{d}[desktop]"], capture_output=True, text=True, timeout=900)
    if r.returncode != 0:
        raise RuntimeError("Installation fehlgeschlagen: " + (r.stderr.strip().splitlines() or ["?"])[-1])
    shutil.rmtree(d, ignore_errors=True)
    with _lock:
        _prepared.clear()
    store.cache_set("update", "latest", {"tag": tag, "checked": time.time(), "error": None})
    return {"installed": tag, "safety_backup": safety.name}


def restart(mode: str = "app") -> None:
    """Neue Version starten und diese beenden."""
    if is_frozen():
        if _prepared.get("swap"):
            return _swap_and_restart()
        raise RuntimeError("Bitte die neue Version aus „Downloads“ installieren und starten.")
    import shlex
    import sys
    # gleiche Argumente wie beim Start (z. B. „ui --port 8800“), sonst nur der Modus
    args = shlex.join(sys.argv[1:]) if sys.argv[1:2] == [mode] else mode
    if is_appimage():
        exe = _prepared.get("new_path") or os.environ["APPIMAGE"]
        cmd = f'sleep 1.5; exec "{exe}"' + ("" if mode == "app" else f" {args}")
    else:
        exe = shutil.which("tunebridge") or str(Path.home() / ".local/bin/tunebridge")
        cmd = f'sleep 1.5; exec "{exe}" {args}'
    env = {k: v for k, v in os.environ.items() if k not in ("APPIMAGE", "APPDIR", "ARGV0", "OWD")}
    subprocess.Popen(["sh", "-c", cmd], start_new_session=True, env=env,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    threading.Timer(0.6, lambda: os._exit(0)).start()

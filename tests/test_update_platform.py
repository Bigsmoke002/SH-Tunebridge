"""Updater: richtige Datei je Prozessor, Windows-Paket wird sicher neben die alte Version entpackt."""

import zipfile
from types import SimpleNamespace

import pytest

from tunebridge import osutil, update


@pytest.mark.parametrize("mach,win,fname,ok", [
    ("x86_64", False, "SH-Tunebridge-0.4.1-x86_64.AppImage", True),
    ("aarch64", False, "SH-Tunebridge-0.4.1-x86_64.AppImage", False),
    ("arm64", False, "SH-Tunebridge-0.4.1-macos-arm64.dmg", True),
    ("x86_64", False, "SH-Tunebridge-0.4.1-macos-arm64.dmg", False),      # Intel-Mac
    ("AMD64", True, "SH-Tunebridge-0.4.1-windows-x64.zip", True),
    ("ARM64", True, "SH-Tunebridge-0.4.1-windows-x64.zip", True),         # Windows on ARM emuliert x64
    ("x86_64", False, "SH-Tunebridge-0.3.0.AppImage", True),              # alte Namen ohne Angabe
])
def test_arch_ok(monkeypatch, mach, win, fname, ok):
    monkeypatch.setattr(update.platform, "machine", lambda: mach)
    monkeypatch.setattr(osutil, "WINDOWS", win)
    assert update.arch_ok(fname) is ok


def _fake_env(monkeypatch, tmp_path, files):
    root = tmp_path / "Programme" / "SH-Tunebridge"
    root.mkdir(parents=True)
    (root / "SH-Tunebridge.exe").write_text("alt")
    pkg_src = tmp_path / "paket.zip"
    with zipfile.ZipFile(pkg_src, "w") as z:
        for name, data in files.items():
            z.writestr(name, data)
    monkeypatch.setattr(osutil, "WINDOWS", True)
    monkeypatch.setattr(osutil, "MACOS", False)
    monkeypatch.setattr(update, "frozen_root", lambda: root)
    monkeypatch.setattr(update, "_download_verified", lambda info, dest, h: dest.write_bytes(pkg_src.read_bytes()))
    monkeypatch.setattr(update.store, "cache_set", lambda *a, **k: None)
    import tunebridge.backup as backup
    monkeypatch.setattr(backup, "create", lambda kind: SimpleNamespace(name="sicherung.zip"))
    update._prepared.clear()
    update._prepared["appimage"] = {"tag": "v9.9.9", "file": "SH-Tunebridge-9.9.9-windows-x64.zip", "size": 10}
    return root


def test_windows_update_unpacks_next_to_install(monkeypatch, tmp_path):
    root = _fake_env(monkeypatch, tmp_path, {"SH-Tunebridge/SH-Tunebridge.exe": "neu",
                                             "SH-Tunebridge/_internal/x.dll": "d"})
    out = update._install_frozen()
    new = root.with_name(".SH-Tunebridge.neu")
    assert out["installed"] == "v9.9.9"
    assert (new / "SH-Tunebridge.exe").read_text() == "neu" and (new / "_internal" / "x.dll").exists()
    assert (root / "SH-Tunebridge.exe").read_text() == "alt"          # alte Version bleibt bis zum Neustart
    assert update._prepared["swap"]["target"] == str(root)
    update._prepared.clear()


def test_windows_update_rejects_path_traversal(monkeypatch, tmp_path):
    root = _fake_env(monkeypatch, tmp_path, {"../../boese.exe": "x", "SH-Tunebridge/SH-Tunebridge.exe": "neu"})
    with pytest.raises(RuntimeError, match="ungültig"):
        update._install_frozen()
    assert not root.with_name(".SH-Tunebridge.neu").exists()
    update._prepared.clear()


def test_windows_update_keeps_setup_uninstaller(monkeypatch, tmp_path):
    """Per Setup installiert: Deinstaller (unins000.exe/.dat) muss nach dem Austausch noch da sein."""
    root = _fake_env(monkeypatch, tmp_path, {"SH-Tunebridge/SH-Tunebridge.exe": "neu"})
    (root / "unins000.exe").write_text("deinst")
    (root / "unins000.dat").write_text("liste")
    update._install_frozen()
    new = root.with_name(".SH-Tunebridge.neu")
    assert (new / "unins000.exe").read_text() == "deinst" and (new / "unins000.dat").exists()
    update._prepared.clear()


def test_one_version_everywhere():
    """/api/status, Updater und Paket melden dieselbe Version – auch in einer editable-Installation mit veralteten
    Metadaten (Fehler: Status 0.10.2, Update-Prüfung 0.13.0)."""
    import re
    from pathlib import Path

    from fastapi.testclient import TestClient

    import tunebridge
    from tunebridge import update
    from tunebridge.web.app import app

    want = re.search(r'^version\s*=\s*"([^"]+)"', (Path(__file__).parents[1] / "pyproject.toml").read_text(), re.M).group(1)
    assert tunebridge.__version__ == update.current() == want
    c = TestClient(app, base_url="http://127.0.0.1:8765")
    assert c.get("/api/status").json()["version"] == want


def test_windows_swap_script_not_inside_program_folder(monkeypatch, tmp_path):
    """Per Doppelklick gestartet steht die App im Programmordner. Das Tausch-Skript darf das nicht erben – sonst
    lässt Windows den Ordner nicht verschieben und die alte Version meldet ewig dasselbe Update (0.10.2 → 0.13.0)."""
    root = tmp_path / "Programme" / "SH-Tunebridge"
    root.mkdir(parents=True)
    work = tmp_path / "work"
    work.mkdir()
    calls = []
    monkeypatch.setattr(osutil, "WINDOWS", True)
    monkeypatch.setattr(update.subprocess, "Popen", lambda args, **kw: calls.append((args, kw)))
    monkeypatch.setattr(update.threading, "Timer", lambda *a, **k: SimpleNamespace(start=lambda: None))
    import tunebridge.web.app as web
    monkeypatch.setattr(web, "companion_stop", lambda: None)
    update.swap_failed_path().write_text("alt")
    update._prepared["swap"] = {"target": str(root), "new": str(root.with_name(".SH-Tunebridge.neu")), "work": str(work)}
    monkeypatch.chdir(root)
    update._swap_and_restart()
    (args, kw), = calls
    assert kw["cwd"] == update.tempfile.gettempdir() and str(root) not in kw["cwd"]
    script = (work / "tausch.ps1").read_text(encoding="utf-8-sig")
    assert script.index("Set-Location") < script.index("Move-Item")
    assert "for ($i = 1; $i -le 20" in script                     # mehrere Versuche (Virenscanner)
    assert str(update.swap_failed_path()) in script                # Fehlschlag wird gemerkt
    assert "-WorkingDirectory" in script                           # Neustart auch nicht im Programmordner
    assert not update.swap_failed_path().exists()                  # alter Merkzettel vor neuem Versuch weg
    update._prepared.clear()


def test_swap_failed_shown_until_current(monkeypatch):
    monkeypatch.setattr(update, "repo", lambda: "https://github.com/x/y")
    monkeypatch.setattr(update, "is_appimage", lambda: False)
    monkeypatch.setattr(update, "is_frozen", lambda: True)
    monkeypatch.setattr(update, "frozen_writable", lambda: True)
    monkeypatch.setattr(update, "current", lambda: "0.10.2")
    monkeypatch.setattr(update, "_latest_valid_appimage", lambda: ("v0.13.0", []))
    update.swap_failed_path().write_text("Das Element wird gerade verwendet", encoding="utf-8")
    u = update.check(force=True)
    assert u["available"] and "verwendet" in u["swap_failed"]
    monkeypatch.setattr(update, "current", lambda: "0.13.0")       # z. B. per Setup nachinstalliert
    u = update.check(force=True)
    assert not u["available"] and u["swap_failed"] is None and not update.swap_failed_path().exists()

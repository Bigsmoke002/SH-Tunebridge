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

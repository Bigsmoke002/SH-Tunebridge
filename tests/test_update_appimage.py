"""AppImage-Updates: nur ein mit dem Release-Schlüssel signiertes Manifest wird akzeptiert."""

import os
import subprocess

import pytest

from tunebridge import update


@pytest.fixture
def keys(tmp_path, monkeypatch):
    key = tmp_path / "k"
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", "test", "-f", str(key)], check=True)
    other = tmp_path / "o"
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", "fremd", "-f", str(other)], check=True)
    signers = tmp_path / "signers"
    signers.write_text(f'* namespaces="git,{update.RELEASE_NS}" {key.with_suffix(".pub").read_text()}')
    monkeypatch.setattr(update, "_signers_file", lambda: signers)
    return key, other


def _sign(key, data: bytes, ns=update.RELEASE_NS) -> bytes:
    f = key.parent / "m"
    f.write_bytes(data)
    subprocess.run(["ssh-keygen", "-q", "-Y", "sign", "-f", str(key), "-n", ns, str(f)], check=True,
                   capture_output=True)
    return (key.parent / "m.sig").read_bytes()


MAN = (b"SH-Tunebridge-Release 1\nversion=0.3.0\nfile=SH-Tunebridge-0.3.0-x86_64.AppImage\n"
       b"size=123\nsha256=abc\n\nSH-Tunebridge 0.3.0\n- Neu")


def test_valid_manifest(keys):
    key, _ = keys
    f = update._verify_manifest(MAN, _sign(key, MAN))
    assert f["version"] == "0.3.0" and f["sha256"] == "abc" and "Neu" in f["notes"]


def test_tampered_manifest_rejected(keys):
    key, _ = keys
    sig = _sign(key, MAN)
    with pytest.raises(RuntimeError, match="Signatur"):
        update._verify_manifest(MAN.replace(b"sha256=abc", b"sha256=evil"), sig)


def test_foreign_key_rejected(keys):
    _, other = keys
    with pytest.raises(RuntimeError, match="Signatur"):
        update._verify_manifest(MAN, _sign(other, MAN))


def test_wrong_namespace_rejected(keys):
    key, _ = keys
    with pytest.raises(RuntimeError, match="Signatur"):
        update._verify_manifest(MAN, _sign(key, MAN, ns="file"))


def test_slug_parsing(monkeypatch):
    for url in ("https://github.com/Bigsmoke002/SH-Tunebridge.git", "git@github-sh-tunebridge:Bigsmoke002/SH-Tunebridge.git"):
        monkeypatch.setattr(update, "repo", lambda u=url: u)
        assert update._slug() == "Bigsmoke002/SH-Tunebridge"


def test_old_appimage_path_keeps_working(tmp_path):
    """Nach dem Update startet der alte Dateiname (Starter, Panel, Autostart) die neue Version."""
    old = tmp_path / "SH-Tunebridge-0.5.0-x86_64.AppImage"
    new = tmp_path / "SH-Tunebridge-0.6.0-x86_64.AppImage"
    old.write_text("alt")
    new.write_text("neu")
    assert update._keep_old_path(old, new) == new
    assert old.is_symlink() and old.read_text() == "neu"
    newer = tmp_path / "SH-Tunebridge-0.7.0-x86_64.AppImage"
    newer.write_text("neuer")
    update._keep_old_path(new, newer)                  # nächstes Update: Kette bleibt gültig
    assert old.read_text() == "neuer" and new.read_text() == "neuer"
    assert not list(tmp_path.glob(".*"))               # keine Reste


def test_old_path_without_symlinks(tmp_path, monkeypatch):
    old, new = tmp_path / "a.AppImage", tmp_path / "b.AppImage"
    old.write_text("alt")
    new.write_text("neu")
    monkeypatch.setattr(update.Path, "symlink_to", lambda *a, **k: (_ for _ in ()).throw(OSError("exfat")))
    assert update._keep_old_path(old, new) == old
    assert old.read_text() == "neu" and not new.exists()


def test_release_still_uploading_is_not_skipped(monkeypatch):
    rels = [{"tag_name": "v9.0.0", "assets": []}, {"tag_name": "v8.0.0", "assets": []}]
    monkeypatch.setattr(update, "_releases", lambda: rels)
    monkeypatch.setattr(update, "current", lambda: "0.1.0")
    tag, skipped = update._latest_valid_appimage()
    assert tag is None and skipped == []                # nicht als „unsigniert“ markiert


def test_check_cache_is_per_version(monkeypatch):
    saved = {}
    monkeypatch.setattr(update, "repo", lambda: "https://github.com/x/y.git")
    monkeypatch.setattr(update, "is_appimage", lambda: True)
    monkeypatch.setattr(update.store, "cache_get", lambda *a, **k: saved.get("v"))
    monkeypatch.setattr(update.store, "cache_set", lambda ns, k, v: saved.update(v=v))
    calls = []
    monkeypatch.setattr(update, "_latest_valid_appimage", lambda: calls.append(1) or ("v0.6.0", []))
    monkeypatch.setattr(update, "current", lambda: "0.5.0")
    assert update.check()["available"] and len(calls) == 1
    update.check()
    assert len(calls) == 1                              # innerhalb einer Stunde aus dem Zwischenspeicher
    monkeypatch.setattr(update, "current", lambda: "0.6.0")
    assert not update.check()["available"] and len(calls) == 2   # neue Version -> neu prüfen
    saved["v"] = {**saved["v"], "error": "offline", "checked": 0}
    update.check()
    assert len(calls) == 3                              # Fehler wird bald erneut versucht


def test_appimage_install_end_to_end(tmp_path, monkeypatch):
    """Update im laufenden AppImage: neue Datei geprüft geladen, alter Pfad startet die neue Version,
    Startmenü zeigt auf die neue Datei, Neustart nimmt die neue Datei."""
    from types import SimpleNamespace

    from tunebridge import backup
    home = tmp_path / "home"
    bindir = home / ".local/bin"
    bindir.mkdir(parents=True)
    old = bindir / "SH-Tunebridge-0.5.0-x86_64.AppImage"
    old.write_bytes(b"alt")
    old.chmod(0o755)
    monkeypatch.setenv("APPIMAGE", str(old))
    monkeypatch.setattr(update.Path, "home", classmethod(lambda cls: home))
    monkeypatch.setattr(backup, "create", lambda **k: SimpleNamespace(name="sicherung"))
    monkeypatch.setattr(update.store, "cache_set", lambda *a, **k: None)
    monkeypatch.setattr(update, "_download_verified", lambda info, tmp, h: tmp.write_bytes(b"neu"))
    update._prepared.clear()
    update._prepared["appimage"] = {"tag": "v0.6.0", "file": "SH-Tunebridge-0.6.0-x86_64.AppImage", "size": 3,
                                    "sha256": "x", "url": "u", "notes": ""}
    r = update.install()
    assert r["installed"] == "v0.6.0"
    new = bindir / "SH-Tunebridge-0.6.0-x86_64.AppImage"
    assert new.read_bytes() == b"neu" and os.access(new, os.X_OK)
    assert old.read_bytes() == b"neu"                      # alter Starter startet die neue Version
    assert update._prepared["new_path"] == str(new)
    entry = (home / ".local/share/applications/sh-tunebridge.desktop").read_text()
    assert f'Exec="{new}"' in entry

"""AppImage-Updates: nur ein mit dem Release-Schlüssel signiertes Manifest wird akzeptiert."""

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

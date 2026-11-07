"""Zeichenweg des App-Fensters: GPU nur dort, wo er erprobt ist, mit Absturzschutz."""

import os

import pytest

from tunebridge import desktop


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("TUNEBRIDGE_DATA", str(tmp_path))
    for k in ("TUNEBRIDGE_GPU", "QT_QPA_PLATFORM", "QSG_RHI_BACKEND", "QTWEBENGINE_CHROMIUM_FLAGS", "TUNEBRIDGE_RENDER"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-1")
    monkeypatch.setattr(desktop, "_nvidia", lambda: True)
    monkeypatch.setattr(desktop, "_vulkan", lambda: True)
    return tmp_path


def test_nvidia_wayland_nimmt_vulkan(env):
    assert desktop._gpu_mode() == "vulkan"
    desktop._qt_env()
    assert os.environ["QSG_RHI_BACKEND"] == "vulkan"
    assert "--disable-gpu" not in os.environ["QTWEBENGINE_CHROMIUM_FLAGS"]
    assert (env / desktop.GPU_TRY).read_text().startswith("1 ")


def test_ohne_nvidia_oder_vulkan_software(env, monkeypatch):
    monkeypatch.setattr(desktop, "_nvidia", lambda: False)
    assert desktop._gpu_mode() == "software"
    monkeypatch.setattr(desktop, "_nvidia", lambda: True)
    monkeypatch.setattr(desktop, "_vulkan", lambda: False)
    assert desktop._gpu_mode() == "software"
    desktop._qt_env()
    assert "--disable-gpu" in os.environ["QTWEBENGINE_CHROMIUM_FLAGS"]
    assert not (env / desktop.GPU_TRY).exists()


def test_x11_bleibt_software(env, monkeypatch):
    monkeypatch.delenv("WAYLAND_DISPLAY")
    assert desktop._gpu_mode() == "software"
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-1")
    monkeypatch.setenv("QT_QPA_PLATFORM", "xcb")
    assert desktop._gpu_mode() == "software"


def test_zwei_abstuerze_dann_software(env):
    desktop._qt_env()
    assert desktop._gpu_mode() == "vulkan"      # ein abgebrochener Start reicht nicht (z. B. sofort beendet)
    desktop._qt_env()
    assert desktop._gpu_mode() == "software"
    (env / desktop.GPU_TRY).unlink()
    assert desktop._gpu_mode() == "vulkan"


def test_erzwingen(env, monkeypatch):
    (env / desktop.GPU_TRY).write_text("5 vulkan")
    for val, want in (("0", "software"), ("1", "gpu"), ("vulkan", "vulkan")):
        monkeypatch.setenv("TUNEBRIDGE_GPU", val)
        assert desktop._gpu_mode() == want

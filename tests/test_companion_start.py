"""Begleiter (Tray/Schwebe-Icon): bekommt seine Einstellungen gleich beim Start mit und startet nur einmal."""
import json

import pytest


def test_companion_gets_cfg_and_starts_once(monkeypatch):
    pytest.importorskip("PySide6.QtWidgets")
    from tunebridge import store
    from tunebridge.web import app as web
    started = []

    class P:
        def __init__(self, cmd, env=None, **k):
            started.append(env)

        def poll(self):
            return None
    monkeypatch.setattr("subprocess.Popen", P)
    monkeypatch.setattr(web, "_companion", {"proc": None})
    web.companion_ensure(8799)
    assert started == []                                   # beides aus -> kein Prozess
    store.meta_set("companion", json.dumps({"tray": False, "bubble": True}))
    web.companion_ensure(8799)
    web.companion_ensure(8799)
    assert len(started) == 1
    assert json.loads(started[0]["TUNEBRIDGE_COMPANION_CFG"])["bubble"] is True

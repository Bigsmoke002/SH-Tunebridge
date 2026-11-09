"""Nach einem Neustart der App darf nur ein Begleiter (Tray/Schwebe-Icon) laufen."""
from tunebridge.web import app as web


def test_companion_api_reports_boot_id():
    from fastapi.testclient import TestClient
    c = TestClient(web.app, base_url="http://127.0.0.1:8765")
    boot = c.get("/api/companion").json()["boot"]
    assert boot == web.APP_BOOT and len(boot) == 16


def test_companion_gets_boot_id_at_start(monkeypatch):
    seen = {}

    class P:
        def __init__(self, cmd, env, **kw):
            seen.update(env)

        def poll(self):
            return None
    monkeypatch.setattr("subprocess.Popen", P)
    monkeypatch.setitem(web._companion, "proc", None)
    web._companion_start({"tray": True, "bubble": False}, 8765)
    assert seen["TUNEBRIDGE_BOOT"] == web.APP_BOOT
    monkeypatch.setitem(web._companion, "proc", None)

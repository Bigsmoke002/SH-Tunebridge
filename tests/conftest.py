"""Alle Tests laufen in einem Wegwerf-Ordner – nie gegen die echten Daten des Nutzers (Datenbank, Token,
Fehler-Warteschlange, Upload-Schlüssel, Debug-Protokoll)."""
import os
import tempfile

import pytest

# Zweite Sicherung, VOR dem ersten Import von tunebridge: Daten- und Konfig-Ordner zeigen von Anfang an auf
# Wegwerf-Ordner. Selbst wenn ein Test die Isolierung unten versehentlich aufhebt (z. B. monkeypatch.undo()),
# landet nichts in den echten Daten oder der echten config.env.
_SAFE = tempfile.mkdtemp(prefix="tunebridge-tests-")
os.environ["TUNEBRIDGE_DATA"] = os.path.join(_SAFE, "data")
os.environ["XDG_CONFIG_HOME"] = os.path.join(_SAFE, "config")
os.environ["TUNEBRIDGE_DOWNLOADS"] = os.path.join(_SAFE, "downloads")
os.makedirs(os.environ["TUNEBRIDGE_DOWNLOADS"], exist_ok=True)


@pytest.fixture(autouse=True)
def _isolated_data(tmp_path_factory, monkeypatch):
    from tunebridge import config, debuglog, outbox, preview, store, upload
    d = tmp_path_factory.mktemp("data")
    monkeypatch.setattr(config, "DATA", d)
    monkeypatch.setattr(store, "DB", d / "tunebridge.db")
    monkeypatch.setattr(outbox, "QUEUE", d / "fehler-warteschlange.json")
    monkeypatch.setattr(upload, "KEY_FILE", d / "upload-identity.pem")
    monkeypatch.setattr(debuglog, "LOG_DIR", d / "logs")
    monkeypatch.setattr(preview, "CACHE", d / "cache" / "previews")
    monkeypatch.setenv("TUNEBRIDGE_NO_AUTOSYNC", "1")
    store.ram_clear()
    yield
    store.ram_clear()

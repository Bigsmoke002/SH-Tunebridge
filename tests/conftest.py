"""Alle Tests laufen in einem Wegwerf-Ordner – nie gegen die echten Daten des Nutzers (Datenbank, Token,
Fehler-Warteschlange, Upload-Schlüssel, Debug-Protokoll)."""
import pytest


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

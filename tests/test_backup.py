import sys
import sqlite3
import zipfile

import pytest

from tunebridge import backup, config, store
from tunebridge.models import Track


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB", tmp_path / "data" / "tunebridge.db")
    monkeypatch.setattr(config, "DATA", tmp_path / "data")
    monkeypatch.setattr(config, "CONFIG_FILE", tmp_path / "config.env")
    monkeypatch.setattr(config, "CONFIG_DIR", tmp_path)
    monkeypatch.setenv("TUNEBRIDGE_BACKUP_DIR", str(tmp_path / "backups"))
    (tmp_path / "data").mkdir()
    store._migrated.clear()
    return tmp_path


def _song(n):
    return Track(f"Song {n}", ["Artist"], genre="Drum & Bass", subgenre="Liquid")


def test_roundtrip_replace(env, monkeypatch):
    rid = store.add_recognition("desktop", "shazam", 1, _song(1), {})
    store.add_to_playlist("Liquid", _song(1))
    config.CONFIG_FILE.write_text("LASTFM_API_KEY=abc123\nTUNEBRIDGE_DATA=/irgendwo\n")
    b = backup.create(include_keys=True)
    if sys.platform != "win32":  # Windows kennt keine Unix-Rechte
        assert b.stat().st_mode & 0o777 == 0o600
    assert {"manifest.json", "tunebridge.db", "config.env"} <= set(zipfile.ZipFile(b).namelist())

    # "neuer Rechner": alles weg
    store.delete_playlist("Liquid")
    with store._conn() as c:
        c.execute("DELETE FROM recognitions")
    config.CONFIG_FILE.write_text("")
    monkeypatch.delenv("LASTFM_API_KEY", raising=False)

    r = backup.restore(b, "replace", restore_keys=True)
    assert r["stats"]["recognitions"] == 1 and r["stats"]["entries"] == 1
    assert store.get_recognition(rid)[0].title == "Song 1"
    assert "LASTFM_API_KEY=abc123" in config.CONFIG_FILE.read_text()
    assert "TUNEBRIDGE_DATA" not in config.CONFIG_FILE.read_text()   # rechnerspezifisch
    assert any("vor-wiederherstellung" in x["name"] for x in backup.list_backups())


def test_merge_no_duplicates(env):
    store.add_recognition("desktop", "shazam", 1, _song(1), {})
    store.add_to_playlist("Liquid", _song(1))
    b = backup.create()
    store.add_recognition("mic", "shazam", 1, _song(2), {})
    store.add_to_playlist("Liquid", _song(2))
    r = backup.restore(b, "merge")
    assert r["stats"]["recognitions"] == 2 and r["stats"]["entries"] == 2   # nichts doppelt, nichts verloren


def test_old_schema_v1_is_migrated(env):
    old = env / "old.db"
    c = sqlite3.connect(old)
    c.executescript(store.MIGRATIONS[0])
    c.execute("INSERT INTO recognitions(ts,host,source,engine,agreement,track,extra) VALUES(1,'pc','d','s',1,?, '{}')",
              ('{"title":"Alt","artists":["X"]}',))
    c.commit(); c.close()
    store.DB.write_bytes(old.read_bytes())
    store._migrated.clear()
    assert store.stats()["schema"] == store.SCHEMA_VERSION
    assert store.history()[0]["track"]["title"] == "Alt"


def test_invalid_file(env):
    bad = env / "x.tbbackup"
    bad.write_text("kaputt")
    with pytest.raises(ValueError):
        backup.inspect(bad)


def test_auto_settings_interval_keep_and_folder(tmp_path, monkeypatch):
    """Auto-Sicherung: aus/täglich/wöchentlich, Anzahl behalten, eigener Ordner (geprüft)."""
    import time as _t

    from tunebridge import backup, config, store
    from tunebridge.models import Track
    monkeypatch.delenv("TUNEBRIDGE_BACKUP_DIR", raising=False)
    assert backup.auto_settings() == {"interval": "daily", "keep": 14}
    assert backup.auto_backup() is None                       # leere Datenbank -> nichts zu sichern
    store.add_to_playlist("P", Track("S", ["K"]))             # nur Playlists, kein Verlauf -> trotzdem sichern
    target = tmp_path / "zweite-platte" / "tb"
    (tmp_path / "zweite-platte").mkdir()
    backup.save_auto_settings(folder=str(target), keep=2)
    assert backup.backup_dir() == target and target.is_dir() and config.opt("TUNEBRIDGE_BACKUP_DIR") == str(target)
    made = []
    for _ in range(3):
        store.meta_set("last_auto_backup", "0")
        made.append(backup.auto_backup())
        _t.sleep(1.05)                                        # Dateiname hat Sekunden
    assert all(made) and len(list(target.glob("*-auto.tbbackup"))) == 2
    assert backup.auto_backup() is None                       # gerade erst gesichert
    backup.save_auto_settings(interval="weekly")
    assert backup.next_auto() - float(store.meta_get("last_auto_backup")) == 7 * 86400
    backup.save_auto_settings(interval="off")
    store.meta_set("last_auto_backup", "0")
    assert backup.auto_backup() is None and backup.next_auto() is None
    for bad in ("relativ/pfad", str(tmp_path / "gibt" / "es" / "nicht")):
        try:
            backup.save_auto_settings(folder=bad)
            raise AssertionError("hätte abgelehnt werden müssen")
        except ValueError:
            pass
    backup.save_auto_settings(folder="")
    assert not config.opt("TUNEBRIDGE_BACKUP_DIR")

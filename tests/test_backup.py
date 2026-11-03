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

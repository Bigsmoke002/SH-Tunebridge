"""Mix-Tracklists aus dem Verlauf."""
from datetime import datetime

from tunebridge import mixlog


def _r(i, minute, title, artist="DJ", isrc=None, sec=0):
    return {"id": i, "ts": datetime(2026, 11, 5, 21, 0).timestamp() + minute * 60 + sec, "title": title, "artists": [artist],
            "genre": "Techno", "subgenre": "Schranz", "isrc": isrc, "ids": {}, "cover": None, "preview_url": None}


ROWS = [_r(1, 0, "A"), _r(2, 1, "A"), _r(3, 4, "B", sec=30), _r(4, 9, "C"), _r(5, 75, "D"), _r(6, 120, "E"), _r(7, 122, "F")]


def test_sessions_split_and_dedupe():
    s = mixlog.sessions([dict(r) for r in ROWS])
    assert [x["count"] for x in s] == [2, 1, 3]                      # neueste zuerst
    first = s[-1]
    assert [x["title"] for x in first["songs"]] == ["A", "B", "C"]    # A doppelt erkannt -> einmal
    assert [x["offset"] for x in first["songs"]] == [0, 270, 540]
    assert first["label"].startswith("Do 5.11.2026, 21:00–21:09")


def test_tracklist_formats():
    s = mixlog.sessions([dict(r) for r in ROWS])[-1]
    assert mixlog.tracklist(s) == "00:00 DJ – A\n04:30 DJ – B\n09:00 DJ – C\n"
    assert mixlog.tracklist(s, "clock").splitlines()[1] == "21:04 DJ – B"
    assert mixlog.tracklist(s, "plain", genre=True).splitlines()[0] == "01. DJ – A [Schranz]"
    long = dict(s, songs=[dict(s["songs"][0], offset=3725)])
    assert mixlog.tracklist(long).startswith("1:02:05 ")


def test_api_and_save():
    from fastapi.testclient import TestClient
    from tunebridge import store
    from tunebridge.models import Track
    from tunebridge.web.app import app
    for t in ("X", "Y", "Y", "Z"):
        store.add_recognition("desktop", "shazam", 1, Track(t, ["K"]), {})
    cl = TestClient(app)
    lst = cl.get("/api/mixlog").json()
    assert len(lst) == 1 and lst[0]["count"] == 3 and lst[0]["first"][0] == "K – X"
    d = cl.get(f"/api/mixlog/{lst[0]['id']}", params={"fmt": "plain"}).json()
    assert d["text"] == "01. K – X\n02. K – Y\n03. K – Z\n"
    assert cl.post(f"/api/mixlog/{lst[0]['id']}/save", json={"name": "Mein Mix"}).json()["added"] == 3
    assert cl.get("/api/mixlog/1").status_code == 404

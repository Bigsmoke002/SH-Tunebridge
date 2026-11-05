"""Set-Planer: Reihenfolge nach Tempo, Tonart und Energie-Kurve; Exporte."""
import time

import pytest

from tunebridge import setplan, store
from tunebridge.models import Track


def _it(t, bpm, cam, e):
    return {"title": t, "artists": ["A"], "artist": "A", "bpm": bpm, "camelot": cam, "energy": e, "genre": "Techno",
            "ids": {"deezer": "1"} if t == "a" else {}, "duration_ms": 300000}


ITEMS = [_it("a", 128, "8A", 0.2), _it("b", 130, "9A", 0.45), _it("c", 132, "9A", 0.7), _it("d", 126, "3B", 0.65), _it("e", 64, "8A", 0.3)]


def test_tempo_jump_half_double():
    assert setplan.tempo_jump(140, 70) == 0 and round(setplan.tempo_jump(128, 132), 1) == 3.1
    assert setplan.tempo_jump(None, 120) is None


def test_curves():
    assert setplan.target("aufbau", 0) < setplan.target("aufbau", 1)
    assert setplan.target("runter", 0) > setplan.target("runter", 1)
    assert setplan.target("peak", 0.7) == pytest.approx(0.95) and setplan.target("peak", 1) < 0.6
    assert setplan.target("gleich", 0.5) is None


def test_order_is_permutation_and_rising():
    o = setplan.order(ITEMS, "aufbau")
    assert sorted(o) == list(range(len(ITEMS)))
    d = setplan.describe(ITEMS, o, "aufbau")
    en = [s["energy"] for s in d["steps"]]
    assert en[0] == min(en) and d["steps"][1]["key"] and d["minuten"] == 25
    assert setplan.order(ITEMS, "runter")[0] != o[0]


def test_render_formats_and_bad_order():
    j = {"playlist": "Mein Set", "items": ITEMS}
    m = setplan.render(j, [0, 1, 2, 3, 4], "m3u8")
    assert m.startswith("#EXTM3U") and "#EXTINF:300,A - a [128 BPM 8A]" in m and "https://www.deezer.com/track/1" in m
    c = setplan.render(j, [4, 3, 2, 1, 0], "csv")
    assert c.splitlines()[1].startswith("1;A;e;64;")
    assert setplan.render(j, [0, 1, 2, 3, 4], "txt").startswith("01. A – a (128 BPM, 8A)")
    with pytest.raises(ValueError):
        setplan.render(j, [0, 0, 1, 2, 3], "csv")


def test_job_save_and_export(monkeypatch, tmp_path):
    from tunebridge import audiofeat
    monkeypatch.setenv("TUNEBRIDGE_DOWNLOADS", str(tmp_path))
    for t in ("x", "y", "z"):
        store.add_to_playlist("Quelle", Track(t, ["K"], genre="House"))
    monkeypatch.setattr(audiofeat, "features", lambda t: {"bpm": 124, "camelot": "5A", "key": "C minor", "energy": 0.4})
    jid = setplan.start("Quelle")
    for _ in range(50):
        if setplan.job(jid)["state"] == "done":
            break
        time.sleep(0.05)
    j = setplan.job(jid)
    assert j["state"] == "done" and j["items"][0]["bpm"] == 124
    r = setplan.export(jid, [2, 1, 0], "txt")
    assert (tmp_path / r["name"]).read_text(encoding="utf-8").startswith("01. K – z")
    assert setplan.save(jid, [2, 1, 0], "Quelle Set")["count"] == 3
    assert [t.title for t in next(p for p in store.local_playlists() if p.name == "Quelle Set").tracks] == ["z", "y", "x"]
    with pytest.raises(ValueError):
        setplan.save(jid, [2, 1, 0], "Quelle Set")
    with pytest.raises(ValueError):
        setplan.start("Gibt es nicht")


def test_improve_never_worse_and_fast():
    import random
    rnd = random.Random(3)
    cams = [f"{n}{m}" for n in range(1, 13) for m in "AB"]
    items = [{"title": str(i), "artists": ["A"], "artist": "A", "bpm": rnd.choice([0, 1]) * 0 + rnd.uniform(118, 140),
              "camelot": rnd.choice(cams), "energy": rnd.uniform(0.15, 0.7), "genre": "Techno"} for i in range(120)]
    for curve in ("aufbau", "peak", "gleich"):
        n = len(items)
        greedy_like = list(range(n))
        t0 = time.time()
        o = setplan.order(items, curve)
        assert time.time() - t0 < 20
        assert sorted(o) == greedy_like
        assert setplan.total_cost(items, setplan._improve(items, o, curve), curve) <= setplan.total_cost(items, o, curve) + 1e-9

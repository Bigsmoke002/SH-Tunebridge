"""Unsichere Treffer: keine automatische Tempo-Suche, Rückfrage „Stimmt/Falsch“, Fingerabdruck erst nach „Stimmt“."""

import shutil
import wave

import numpy as np
from fastapi.testclient import TestClient

from tunebridge import store
from tunebridge.models import Track
from tunebridge.recognize import engines, localfp, variants
from tunebridge.web import app as web


async def _coro(v):
    return v


def _setup(monkeypatch, tmp_path, skew):
    p = tmp_path / "a.wav"
    with wave.open(str(p), "wb") as w:
        w.setnchannels(1), w.setsampwidth(2), w.setframerate(11025)
        w.writeframes((np.random.default_rng(3).normal(0, 6000, 11025 * 6)).astype("<i2").tobytes())
    monkeypatch.setattr(web.capture, "record", lambda src, sec: shutil.copy(p, tmp_path / "rec.wav"))
    hit = engines.Recognition(engine="shazam", title="Song", artists=["Band"], skew=skew)
    monkeypatch.setattr(web, "recognize", lambda wav, eng: _coro(engines.Result(hit, 1, [hit], {})))
    monkeypatch.setattr(web, "enrich", lambda rec, *a: (Track(title=rec.title, artists=rec.artists), {}))
    found, learned = [], []
    monkeypatch.setattr(variants, "find", lambda *a, **k: found.append(k) or _coro(None))
    monkeypatch.setattr(localfp, "remember", lambda *a: learned.append(a))
    return TestClient(web.app), found, learned


def test_unsicherer_treffer_ohne_automatische_tempo_suche(monkeypatch, tmp_path):
    cl, found, learned = _setup(monkeypatch, tmp_path, skew=0.08)
    r = cl.post("/api/listen", json={"seconds": 5}).json()
    assert r["found"] and r["extra"]["unsure"] is True and r["tempo_offer"] is True
    assert found == [] and learned == []           # keine Zusatz-Anfragen, nichts gemerkt
    v = cl.post(f"/api/recognition/{r['id']}/verdict", json={"ok": True}).json()
    assert v["learned"] is True and len(learned) == 1
    assert "unsure" not in v["extra"] and v["extra"]["confirmed"] is True


def test_falsch_loescht_eintrag(monkeypatch, tmp_path):
    cl, _, learned = _setup(monkeypatch, tmp_path, skew=0.08)
    r = cl.post("/api/listen", json={"seconds": 5}).json()
    v = cl.post(f"/api/recognition/{r['id']}/verdict", json={"ok": False}).json()
    assert v["deleted"] is True and store.get_recognition(r["id"]) is None and learned == []
    assert cl.post(f"/api/recognition/{r['id']}/verdict", json={"ok": True}).status_code == 404


def test_sicherer_treffer_wird_sofort_gemerkt(monkeypatch, tmp_path):
    cl, found, learned = _setup(monkeypatch, tmp_path, skew=0.0)
    r = cl.post("/api/listen", json={"seconds": 5}).json()
    assert r["found"] and not r["extra"].get("unsure") and not r["tempo_offer"]
    assert found == [] and len(learned) == 1

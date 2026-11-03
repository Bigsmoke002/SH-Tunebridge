"""Song-Speicher, lokaler Wiedererkenner, Liste „Nicht erkannt“, Speicher-Übersicht."""

import wave

import numpy as np
import pytest


@pytest.fixture
def db(tmp_path, monkeypatch):
    from tunebridge import config, store
    monkeypatch.setattr(config, "DATA", tmp_path)
    monkeypatch.setattr(store, "DB", tmp_path / "t.db")
    return store


def _wav(path, seed, seconds=10, start=0.0):
    """Reproduzierbares „Musikstück“: wechselnde Töne + Rauschen; start = Ausschnitt ab Sekunde."""
    rate = 44100
    rng = np.random.default_rng(seed)
    t = np.arange(int(rate * 30)) / rate
    x = np.zeros_like(t)
    step = 0.12                                  # kurze, abklingende Töne wie bei echter Musik
    for i in range(int(30 / step)):
        seg = (t >= i * step) & (t < i * step + 0.4)
        env = np.exp(-(t[seg] - i * step) * 12)
        for f in rng.uniform(150, 3000, size=2):
            x[seg] += env * np.sin(2 * np.pi * f * t[seg])
    x += rng.normal(0, 0.05, t.size)
    x = x[int(start * rate):int((start + seconds) * rate)]
    x = (x / np.abs(x).max() * 20000).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
        w.writeframes(x.tobytes())
    return path


def test_local_fingerprint_matches_known_part_only(db, tmp_path):
    from tunebridge.recognize import localfp
    localfp.remember("A|song", None, localfp.fingerprint(_wav(tmp_path / "a.wav", 1, start=0)), 0)
    localfp.remember("B|other", None, localfp.fingerprint(_wav(tmp_path / "b.wav", 2, start=0)), 0)
    hit = localfp.match(localfp.fingerprint(_wav(tmp_path / "a2.wav", 1, seconds=8, start=1.5)))
    assert hit and localfp.parse_ref(hit["ref"]) == ("A|song", 1.0)
    assert abs(hit["pos_frames"] / localfp.FPS - 1.5) < 0.2       # Position im Song stimmt
    assert localfp.match(localfp.fingerprint(_wav(tmp_path / "c.wav", 3))) is None   # unbekannter Song


def test_song_cache_skips_online_lookups(db, monkeypatch):
    from tunebridge import enrich as en
    from tunebridge.models import Track
    from tunebridge.recognize.engines import Recognition
    calls = []

    def online(rec):
        calls.append(rec.title)
        return Track(title=rec.title, artists=rec.artists, isrc="US1", genre="Breakcore",
                     tags={"breakcore": 100}), {"cover": "http://x/c.jpg", "preview_url": None, "genre_source": "tags"}
    monkeypatch.setattr(en, "_enrich_online", online)
    rec = Recognition(engine="shazam", title="Song", artists=["Artist"], isrc="US1")
    t1, x1 = en.enrich(rec)
    t2, x2 = en.enrich(Recognition(engine="shazam", title="Song", artists=["Artist"]))   # ohne ISRC -> Name
    assert calls == ["Song"] and t2.genre == "Breakcore" and x2.get("cached")
    assert db.saved_calls().get("lookups") == 1
    en.enrich(rec, fresh=True)
    assert len(calls) == 2


def test_misses_export_has_no_host_or_device(db, monkeypatch):
    from fastapi.testclient import TestClient
    from tunebridge.web import app as webapp
    db.miss_add("unerkannt", "alsa_output.pci-0000_0b_00.4.analog-stereo.monitor", -21.0,
                {"title": "Clarity (Ultra Slowed)", "artist": "Xalv"}, None, {"fehler": {}})
    c = TestClient(webapp.app)
    data = c.post("/api/misses/preview", json={}).json()
    raw = str(data)
    assert data["eintraege"][0]["quelle"] == "gerät" and "alsa_output" not in raw and db.HOST not in raw
    st = c.get("/api/storage").json()
    assert {r["id"] for r in st["rows"]} >= {"songs", "fingerprints", "misses"}
    assert "previews" not in {r["id"] for r in st["rows"]}   # Hörproben werden nicht mehr gespeichert
    assert c.post("/api/storage/clear", json={"what": ["misses"]}).json()["cleared"]["misses"] == 1


def _frames(kind, seconds, seed=0):
    """Pegel-Frames wie meter.levels sie liefert (25/s)."""
    from tunebridge.recognize import meter
    rng = np.random.default_rng(seed)
    base = rng.uniform(0.2, 0.9, 32)
    for i in range(int(seconds * meter.FPS)):
        if kind == "still":
            yield {"rms": -80.0, "bands": [0.0] * 32}
        else:
            yield {"rms": -18.0 + rng.normal(0, 1), "bands": list(np.clip(base + rng.normal(0, 0.05, 32), 0, 1))}


@pytest.mark.parametrize("plan,why", [
    ([("song", 8, 1), ("still", 2, 0)], "stille"),
    ([("song", 8, 1), ("song", 8, 2)], "klang"),
    ([("song", 30, 1)], "zeit"),
])
def test_hold_detects_song_change(monkeypatch, plan, why):
    import asyncio
    import time as _t
    from tunebridge.recognize import hold, players
    clock = [1000.0]
    monkeypatch.setattr(_t, "time", lambda: clock[0])
    monkeypatch.setattr(players, "signature", lambda: "")

    async def fake_levels(source):
        for kind, sec, seed in plan:
            for fr in _frames(kind, sec, seed):
                clock[0] += 1 / 25
                yield fr
    monkeypatch.setattr(hold.meter, "levels", fake_levels)

    async def run():
        async for ev in hold.watch("desktop", 20):
            if ev.get("done"):
                return ev["why"]
    assert asyncio.run(run()) == why


def test_hold_player_change(monkeypatch):
    import asyncio
    import time as _t
    from tunebridge.recognize import hold, players
    clock = [0.0]
    monkeypatch.setattr(_t, "time", lambda: clock[0])
    monkeypatch.setattr(players, "signature", lambda: "brave:A" if clock[0] < 4 else "brave:B")

    async def fake_levels(source):
        for fr in _frames("song", 20, 1):
            clock[0] += 1 / 25
            yield fr
    monkeypatch.setattr(hold.meter, "levels", fake_levels)

    async def run():
        async for ev in hold.watch("desktop", 20):
            if ev.get("done"):
                return ev["why"], clock[0]
    why, at = asyncio.run(run())
    assert why == "player" and at < 6


def test_upload_signature_format(db, monkeypatch, tmp_path):
    """Unterschrift so, wie der Server sie prüft: r‖s (64 Byte) über den kanonischen Text."""
    import base64
    import hashlib
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
    from tunebridge import upload
    monkeypatch.setattr(upload, "KEY_FILE", tmp_path / "id.pem")
    seen = {}

    class R:
        status_code = 200
        def json(self):
            return {"angenommen": 1, "schon_da": 0}

    def fake_post(url, content, headers, timeout):
        seen.update(url=url, body=content, h=headers)
        return R()
    monkeypatch.setattr(upload.httpx, "post", fake_post)
    upload.send({"format": 1, "eintraege": [{"uid": "a" * 32}]})
    h = seen["h"]
    pub = base64.b64decode(h["X-TB-Key"])
    sig = base64.b64decode(h["X-TB-Sig"])
    assert len(pub) == 65 and len(sig) == 64 and seen["url"].endswith("/v1/misses")
    msg = upload.canonical("POST", "/v1/misses", h["X-TB-Time"], h["X-TB-Nonce"], seen["body"])
    assert msg.decode().endswith(hashlib.sha256(seen["body"]).hexdigest())
    key = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), pub)
    key.verify(encode_dss_signature(int.from_bytes(sig[:32], "big"), int.from_bytes(sig[32:], "big")),
               msg, ec.ECDSA(hashes.SHA256()))
    assert upload.identity() == hashlib.sha256(pub).hexdigest()[:8]

"""Mix erstellen: Kandidaten aus Deezer (gefälscht), Stufen „Wie passend?“, eigene Filter, Speichern, kein Netz."""
import time

import httpx
import pytest

from tunebridge import artists, audiofeat, mixgen, store
from tunebridge.models import Track

# Start-Künstler 1 („Seed“), ähnliche Künstler 10–14. Tempo je Song steht im Titel-Schema der Fälschung unten.
BPM = {}


def _h(tid, title, aid, name, rank=1000, isrc=None):
    return {"id": tid, "title": title, "artist": {"id": aid, "name": name}, "rank": rank, "duration": 240,
            "album": {"title": "Alb", "cover_medium": "https://e-cdns-images.dzcdn.net/x.jpg"},
            "preview": f"https://cdnt-preview.dzcdn.net/{tid}.mp3", **({"isrc": isrc} if isrc else {})}


def _fake_get(url, **params):
    if "/search/artist" in url:
        return {"data": [{"id": 1, "name": "Seed", "nb_fan": 1234, "picture_medium": None}]}
    aid = int(url.split("/artist/")[1].split("/")[0])
    if url.endswith("/related"):
        return {"data": [{"id": 10 + i, "name": f"Rel{i}"} for i in range(5)]}
    if url.endswith("/radio"):
        return {"data": [_h(500, "Seed Radio", 1, "Seed")] + [_h(600 + i, f"Radio {i}", 50 + i % 3, f"Radio{i % 3}", rank=100 * i)
                                                              for i in range(9)]}
    if url.endswith("/top"):
        if aid == 1:
            return {"data": [_h(100 + i, f"Seed Hit {i}", 1, "Seed", rank=900000 - i) for i in range(3)]}
        return {"data": [_h(aid * 100 + k, f"Song {aid}-{k}", aid, f"Rel{aid - 10}", rank=aid * 1000 + k)
                         for k in range(params.get("limit", 4))]}
    raise AssertionError(url)


@pytest.fixture(autouse=True)
def fake_deezer(monkeypatch):
    artists._RAM.clear()
    monkeypatch.setattr(artists, "_get", _fake_get)
    calls = []

    def feats(t, deezer_bpm=None, refresh=False):
        calls.append(t.title)
        tid = int(t.ids["deezer"])
        bpm = BPM.get(tid, 174.0)
        return {"bpm": bpm, "camelot": "8A" if tid % 2 == 0 else "9A", "key": "Am", "energy": 0.7}
    monkeypatch.setattr(audiofeat, "features", feats)

    def no_net(self, request, *a, **kw):
        raise AssertionError(f"unerwartete Netzanfrage: {request.url}")
    monkeypatch.setattr(httpx.Client, "send", no_net)
    BPM.clear()
    yield calls
    artists._RAM.clear()


def run(opts=None, seeds=None):
    opts = mixgen.clean_opts(opts)
    j = {"id": "t", "seeds": seeds or [{"id": 1, "name": "Seed"}], "opts": opts, "state": "running", "phase": "collecting",
         "done": 0, "total": 1, "cancel": False, "started": time.time(), "note": ""}
    mixgen._run(j)
    assert j["state"] == "done", j.get("error")
    return j, [j["items"][i] for i in j["order"]]


def test_clean_opts_limits():
    o = mixgen.clean_opts({"level": "x", "count": 500, "bpm_min": 180, "bpm_max": 170, "camelot": "13A", "per_artist": 0})
    assert o["level"] == "passend" and o["count"] == mixgen.COUNT_MAX and o["per_artist"] == 1
    assert (o["bpm_min"], o["bpm_max"]) == (170, 180) and o["camelot"] is None
    assert mixgen.clean_opts({"camelot": "8a"})["camelot"] == "8A"
    assert mixgen.clean_opts({})["count"] == mixgen.COUNT_DEFAULT


def test_locker_needs_no_measuring_and_keeps_limits(fake_deezer):
    j, picked = run({"level": "locker", "count": 10, "per_artist": 2})
    assert fake_deezer == []                                     # „Locker“ misst nichts
    assert len(picked) == 10
    per = {}
    for it in picked:
        per[it["artist"]] = per.get(it["artist"], 0) + 1
    assert max(per.values()) <= 2
    assert picked[0]["artist"] == "Seed"                          # Start-Künstler zuerst (höchste Ähnlichkeit)
    assert all(it["reasons"] for it in picked) and j["found"] > 20


def test_without_seed_songs():
    _, picked = run({"level": "locker", "count": 40, "include_seeds": False})
    assert picked and all(it["artist"] != "Seed" for it in picked)


def test_mixbar_tempo_half_double_and_dj_order():
    BPM.update({1100: 87.0, 1101: 140.0, 1200: 176.0, 1201: 120.0})   # 87 = halbes 174 -> passt; 140/120 nicht
    j, picked = run({"level": "mixbar", "count": 15, "per_artist": 3})
    titles = {it["title"] for it in picked} | {j["items"][i]["title"] for i in j["reserve"]}
    assert j["ref"]["bpm"] == 174.0
    assert "Song 11-0" in titles and "Song 12-0" in titles
    assert "Song 11-1" not in titles and "Song 12-1" not in titles
    assert sorted(j["order"]) == sorted(set(j["order"]))         # DJ-Reihenfolge ist eine Auswahl ohne Doppelte


def test_own_bpm_range_is_strict(fake_deezer):
    BPM.update({100: 128.0, 1000: 126.0, 1001: 130.0})
    _, picked = run({"level": "locker", "bpm_min": 124, "bpm_max": 132, "count": 50})
    assert picked and all(124 <= it["bpm"] <= 132 for it in picked)
    assert fake_deezer                                            # eigener Filter -> es wird gemessen


def test_own_key_filter():
    _, picked = run({"level": "passend", "camelot": "8A", "count": 50, "per_artist": 10})
    assert picked and all(mixgen.camelot_distance("8A", it["camelot"]) <= 1 for it in picked)


def test_measure_is_capped(fake_deezer, monkeypatch):
    monkeypatch.setattr(mixgen, "MEASURE_MAX", 7)
    run({"level": "passend", "count": 50})
    assert len(fake_deezer) <= 7


def test_versions_and_library_filter():
    items = [mixgen._item(_h(1, "Tune (VIP)", 5, "A"), 0.9, "x"), mixgen._item(_h(2, "Tune", 5, "A"), 0.8, "x"),
             mixgen._item(_h(3, "Other", 6, "B"), 0.7, "x")]
    o = mixgen.clean_opts({"versions": False})
    assert [it["title"] for it in mixgen.prefilter(items, o)] == ["Tune", "Other"]
    store.add_to_playlist("Meins", Track("Other", ["B"]))
    assert [it["title"] for it in mixgen.prefilter(items, mixgen.clean_opts({}), mixgen.library_keys())] == ["Tune (VIP)", "Tune"]


def test_dedupe_by_isrc_keeps_best():
    a = mixgen._item(_h(1, "Song", 5, "A", isrc="X1"), 0.5, "radio")
    b = mixgen._item(_h(2, "Song (Radio Edit)", 5, "A", isrc="X1"), 0.9, "top")
    out = mixgen.dedupe([a, b])
    assert len(out) == 1 and out[0]["why"] == "top"


def test_save_and_errors():
    j, _ = run({"level": "locker", "count": 5})
    mixgen._jobs["t"] = j
    r = mixgen.save("t", j["order"], "Mein Mix")
    assert r["count"] == 5
    pl = next(p for p in store.local_playlists() if p.name == "Mein Mix")
    assert len(pl.tracks) == 5 and pl.tracks[0].ids.get("deezer")
    with pytest.raises(ValueError):
        mixgen.save("t", j["order"], "Mein Mix")                # Name vergeben
    with pytest.raises(ValueError):
        mixgen.save("t", [999], "Anders")                         # Index passt nicht
    with pytest.raises(ValueError):
        mixgen.save("t", [0, 0], "Anders")
    with pytest.raises(ValueError):
        mixgen.start([], {})


def test_api_flow_without_network():
    from fastapi.testclient import TestClient

    from tunebridge.web import app as webapp
    c = TestClient(webapp.app)
    assert c.get("/api/mix/levels").json()["count"] == mixgen.COUNT_DEFAULT
    assert c.get("/api/mix/artists?q=Se").json()[0]["name"] == "Seed"
    assert c.post("/api/mix/start", json={"seeds": [], "opts": {}}).status_code == 400
    jid = c.post("/api/mix/start", json={"seeds": [{"id": 1, "name": "Seed"}], "opts": {"level": "locker", "count": 8}}).json()["job"]
    for _ in range(100):
        j = c.get(f"/api/mix/{jid}").json()
        if j["state"] != "running":
            break
        time.sleep(0.05)
    assert j["state"] == "done" and len(j["order"]) == 8
    assert "fit" not in j["items"][0] and "rank" not in j["items"][0]      # nur Anzeige-Felder
    d = c.post(f"/api/mix/{jid}/describe", json={"order": j["order"]}).json()
    assert "harmonisch" in d
    assert c.post(f"/api/mix/{jid}/save", json={"order": j["order"], "name": "API-Mix"}).json()["count"] == 8
    assert c.get("/api/mix/unbekannt").status_code == 400


def test_network_is_really_blocked():
    """Gegenprobe: die Netzsperre dieser Tests greift wirklich (sonst wären die Tests oben wertlos)."""
    from tunebridge import enrich
    with pytest.raises(AssertionError, match="unerwartete Netzanfrage"):
        enrich._http.get("https://api.deezer.com/track/1")


def test_reference_tempo_is_robust():
    c = lambda *bs: [(b, 0.7) for b in bs]
    assert mixgen.ref_tempo(c(86.6, 86.7, 173.4, 86.5)) == 173.3           # DnB: halbe Messungen zählen doppelt
    assert mixgen.ref_tempo(c(85.0, 86.0, 84.0, 87.0)) == 85.5             # Hip-Hop bleibt bei 85
    assert mixgen.ref_tempo(c(128.0, 127.0, 64.0)) == 128.0                # 256 wäre zu schnell
    # Netsky-Fall: 2/3-Fehlmessungen (117) und Ausreißer dürfen das Ziel nicht kippen
    assert 172 <= mixgen.ref_tempo(c(117.4, 86.4, 86.7, 173.1, 129.7, 116.5, 173.5, 86.3)) <= 174
    assert mixgen.ref_tempo([]) is None
    assert mixgen.fold_to(86.7, 174) == 173.4 and mixgen.fold_to(128, None) == 128


def test_collab_is_not_labelled_as_own_song():
    j, _ = run({"level": "locker", "count": 50, "per_artist": 10})
    assert all(it["why"] == "von Seed" for it in j["items"] if it["artist"] == "Seed" and it["seed"])


# ------------------------------------------------------------------ Genre-Suche
LIQ = {"genre": "Drum & Bass", "sub": "Liquid"}


@pytest.fixture
def fake_mb(monkeypatch):
    from tunebridge.genres.sources import musicbrainz
    seen = []

    def mb_get(path, **params):
        seen.append(params["query"])
        if "liquid" in params["query"]:
            return {"artists": [
                {"name": "Liq A", "score": 100, "tags": [{"name": "drum and bass", "count": 4}, {"name": "liquid funk", "count": 2}]},
                {"name": "Liq B", "score": 95, "tags": [{"name": "liquid funk", "count": 1}]},
                {"name": "Prinz", "score": 99, "tags": [{"name": "funk", "count": 12}, {"name": "liquid funk", "count": 1}]},
                {"name": "Nur Treffer", "score": 98, "tags": [{"name": "rock", "count": 3}]}]}
        return {"artists": [{"name": "Liq B", "score": 90, "tags": [{"name": "drum and bass", "count": 3}]}]}
    monkeypatch.setattr(musicbrainz, "_get", mb_get)
    ids = {"Liq A": 20, "Liq B": 21, "Seed": 1}

    def dz(url, **params):
        if "/search/artist" in url:
            n = params.get("q")
            return {"data": [{"id": ids[n], "name": n, "nb_fan": 10}] if n in ids else []}
        return _fake_get(url, **params)
    monkeypatch.setattr(artists, "_get", dz)
    monkeypatch.delenv("LASTFM_API_KEY", raising=False)
    return seen


def run_genre(g, opts=None):
    opts = mixgen.clean_opts(opts)
    j = {"id": "g", "seeds": [], "genre": mixgen.check_genre(g), "opts": opts, "state": "running", "phase": "collecting",
         "done": 0, "total": 1, "cancel": False, "started": time.time(), "note": ""}
    mixgen._run(j)
    assert j["state"] == "done", j.get("error")
    return j, [j["items"][i] for i in j["order"]]


def test_check_genre_and_tags():
    assert mixgen.check_genre({"genre": "Drum & Bass", "sub": "Liquid"}) == LIQ
    assert mixgen.check_genre({"genre": "Drum & Bass", "sub": "Gibtsnicht"}) == {"genre": "Drum & Bass", "sub": None}
    assert mixgen.check_genre({"genre": "Polka"}) is None
    assert "liquid funk" in mixgen.genre_tags(LIQ)


def test_mb_focus_rule():
    want, fam = {"liquid funk"}, {"liquid funk", "drum and bass"}
    assert mixgen.mb_relevant([{"name": "drum and bass", "count": 4}, {"name": "liquid funk", "count": 1}], want, fam) == 1
    assert mixgen.mb_relevant([{"name": "funk", "count": 12}, {"name": "liquid funk", "count": 1}], want, fam) == 0
    assert mixgen.mb_relevant([{"name": "rock", "count": 3}], want, fam) == 0


def test_genre_mix_uses_confirmed_artists_and_library(fake_mb):
    store.add_to_playlist("Liquid Abend", Track("Eigener Song", ["Liq C"], genre="Drum & Bass", subgenre="Liquid"))
    j, picked = run_genre(LIQ, {"level": "locker", "count": 40, "per_artist": 10})
    whys = {it["artist"]: it["reasons"][0] for it in picked}
    assert "Liquid laut MusicBrainz" in whys["Rel10"]                        # Liq A (Deezer-ID 20)
    assert whys["Liq C"].endswith("aus deiner Bibliothek")
    assert not any("Prinz" in it["artist"] or "Nur Treffer" in it["artist"] for it in picked)
    assert any(it["reasons"][0].startswith("aus dem Radio") for it in picked)   # „Locker“ füllt über das Radio auf
    assert j["genre"] == LIQ and j["found"] > 5


def test_genre_dj_exact_only_confirmed(fake_mb):
    _, picked = run_genre(LIQ, {"level": "genau", "count": 40, "per_artist": 10})
    assert picked and all(not it["reasons"][0].startswith("aus dem Radio") for it in picked)


def test_niche_subgenre_falls_back_to_main_genre(fake_mb, monkeypatch):
    monkeypatch.setattr(mixgen, "_mb_artists", lambda g: [] if g["sub"] else [("Liq B", "")])
    j, picked = run_genre({"genre": "Drum & Bass", "sub": "Jungle"}, {"level": "locker", "count": 10})
    assert "kaum Daten" in j["note"]
    assert any("Jungle nicht bestätigt" in it["reasons"][0] for it in picked)


def test_genre_api(fake_mb):
    from fastapi.testclient import TestClient

    from tunebridge.web import app as webapp
    c = TestClient(webapp.app)
    assert c.post("/api/mix/start", json={"genre": {"genre": "Polka"}}).status_code == 400
    jid = c.post("/api/mix/start", json={"genre": LIQ, "opts": {"level": "locker", "count": 5}}).json()["job"]
    for _ in range(100):
        j = c.get(f"/api/mix/{jid}").json()
        if j["state"] != "running":
            break
        time.sleep(0.05)
    assert j["state"] == "done" and j["genre"] == LIQ and len(j["order"]) == 5

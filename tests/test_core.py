from tunebridge.genres import classify
from tunebridge.matching import best_match, score
from tunebridge.models import Track
from tunebridge.split import split_by_genre


def test_isrc_match():
    a = Track("Afterglow", ["Wilkinson"], isrc="GBCEN1300123")
    b = Track("Afterglow (feat. Becky Hill)", ["Wilkinson", "Becky Hill"], isrc="gbcen1300123")
    assert score(a, b).reason == "isrc"


def test_youtube_title_noise():
    src = Track("Afterglow", ["Wilkinson"], duration_ms=210_000)
    yt = Track("Wilkinson - Afterglow (Official Video)", ["WilkinsonVEVO"], duration_ms=212_000)
    assert best_match(src, [yt]) is not None


def test_vip_is_not_original():
    src = Track("Tarantula", ["Pendulum"], duration_ms=330_000)
    vip = Track("Tarantula VIP", ["Pendulum"], duration_ms=330_000)
    orig = Track("Tarantula", ["Pendulum"], duration_ms=331_000)
    assert best_match(src, [vip, orig]).candidate is orig


def test_classify_dnb_liquid():
    c = classify({"drum and bass": 100, "liquid funk": 80, "electronic": 60, "seen live": 10})
    assert (c.genre, c.subgenre) == ("Drum & Bass", "Liquid")


def test_classify_riddim():
    c = classify({"dubstep": 100, "riddim": 70})
    assert (c.genre, c.subgenre) == ("Dubstep", "Riddim")


def test_split():
    ts = [Track("a", ["x"], genre="Drum & Bass", subgenre="Liquid"),
          Track("b", ["x"], genre="Drum & Bass", subgenre="Neurofunk"),
          Track("c", ["x"])]
    assert {p.name for p in split_by_genre(ts, "main")} == {"Drum & Bass", "Unsortiert"}
    assert len(split_by_genre(ts, "sub")) == 3


def test_suggest_prefers_matching_subgenre():
    from tunebridge.models import Playlist
    from tunebridge.suggest import suggest
    liquid = Playlist("Chill Abends", [Track("x", ["Hybrid Minds"], genre="Drum & Bass", subgenre="Liquid")] * 5)
    neuro = Playlist("Ballern", [Track("y", ["Noisia"], genre="Drum & Bass", subgenre="Neurofunk")] * 5)
    empty = Playlist("Liquid DnB", [])
    t = Track("Paradise", ["Etherwood"], genre="Drum & Bass", subgenre="Liquid")
    names = [s.playlist for s in suggest(t, [neuro, liquid, empty])]
    assert names[0] in ("Chill Abends", "Liquid DnB") and names.index("Ballern") > 0


def test_suggest_new_playlist():
    from tunebridge.suggest import suggest
    t = Track("a", ["b"], genre="Dubstep", subgenre="Riddim")
    s = suggest(t, [])
    assert s[0].new and s[0].playlist == "Dubstep – Riddim"


def test_bpm_guess():
    from tunebridge.enrich import bpm_guess
    assert bpm_guess(173, ["Dance"]) == "Drum & Bass"
    assert bpm_guess(173, ["Pop"]) is None


def test_meter_analyze():
    import numpy as np
    from tunebridge.recognize.meter import BANDS, analyze
    t = np.arange(4096) / 22050
    loud = (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    a = analyze(loud)
    assert -10 < a["rms"] < -5 and len(a["bands"]) == BANDS and max(a["bands"]) > 0.5
    assert analyze(np.zeros(4096, dtype=np.float32))["rms"] <= -90


def test_key_extraction():
    from tunebridge.keys import SERVICES, extract
    page = """Your API account
Application name   tunebridge
API key  0123456789abcdef0123456789abcdef
Shared secret  fedcba9876543210fedcba9876543210"""
    assert extract(SERVICES["lastfm"], page) == {"LASTFM_API_KEY": "0123456789abcdef0123456789abcdef"}
    acr = """Host
identify-eu-west-1.acrcloud.com
Access Key
aaaabbbbccccddddeeeeffff00001111
Access Secret
AbCdEfGhIjKlMnOpQrStUvWxYz0123456789AbCd"""
    got = extract(SERVICES["acrcloud"], acr)
    assert got["ACRCLOUD_HOST"] == "identify-eu-west-1.acrcloud.com"
    assert got["ACRCLOUD_ACCESS_KEY"] == "aaaabbbbccccddddeeeeffff00001111"
    assert got["ACRCLOUD_ACCESS_SECRET"].startswith("AbCd")
    # Shared secret darf nicht als API-Key durchgehen, wenn die Beschriftung fehlt
    assert extract(SERVICES["lastfm"], "Shared secret fedcba9876543210fedcba9876543210") == {}


def test_llm_option_mapping():
    from tunebridge.enrich import _pick_option
    subs = ["Liquid", "Jungle", "Darkstep / Techstep"]
    assert _pick_option("junglist", "Drum & Bass", subs) == "Jungle"
    assert _pick_option("liquid", "Drum & Bass", subs) == "Liquid"
    assert _pick_option("Techstep", "Drum & Bass", subs) == "Darkstep / Techstep"
    assert _pick_option("Uplifting: uplifting trance", "Trance", ["Uplifting", "Psytrance"]) == "Uplifting"
    assert _pick_option(None, "Drum & Bass", subs) is None

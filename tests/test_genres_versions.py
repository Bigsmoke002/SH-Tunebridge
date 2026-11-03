"""Genre-Erkennung (Breakcore & Co.), Slowed-/Sped-up-Erkennung."""

from tunebridge.genres import classify
from tunebridge.recognize import variants
from tunebridge.recognize.engines import Recognition
from tunebridge.versions import main_artist, speed_label, split_version


def test_breakcore_beats_dnb_parent_tags():
    # echte Last.fm-Tags von „usedcvnt – Just Leave Me To Bleed“
    c = classify({"breakcore": 50, "drum and bass": 50, "jungle": 8, "electronic": 2, "drum n bass": 1})
    assert c.genre == "Breakcore"


def test_tag_suffix_and_niche_genres():
    assert classify({"emo breakcore": 40, "jungle": 30}).subgenre == "Atmospheric Breakcore"
    assert classify({"phonk": 40, "hip hop": 50, "trap": 30}).genre == "Phonk"
    assert classify({"classical crossover": 30}).genre == "Classical / Cinematic"
    assert classify({"new wave": 50, "rock": 10}).genre == "Rock / Metal"   # „wave“ zählt nicht als Wortende
    assert classify({"liquid funk": 100, "drum and bass": 80}).subgenre == "Liquid"


def test_fallback_only_when_nothing_else():
    assert classify({"electronic": 40, "dance": 20}).genre == "Electronic"
    assert classify({"electronic": 40, "techno": 5}).genre == "Techno"
    assert classify({"germany": 50}).genre is None


def test_split_version():
    assert split_version("Just Leave Me To Bleed (Slowed + Reverb)", ["usedcvnt"]) == \
        ("Just Leave Me To Bleed", ["usedcvnt"], "Slowed + Reverb")
    assert split_version("Sweater Weather [sped up]", ["The Neighbourhood"])[2] == "Sped Up"
    assert split_version("after dark", ["Mr.Kitty, slowed"]) == ("after dark", ["Mr.Kitty"], "Slowed + Reverb")
    assert split_version("Dancin (Krono Remix) - Slowed & Reverb Version", ["A"])[0] == "Dancin (Krono Remix)"
    # keine Fehlalarme
    assert split_version("Slow Down", ["Selena Gomez"])[2] is None
    assert split_version("Reverb Love", ["X"])[2] is None
    assert main_artist("trapeia/entris") == "trapeia" and main_artist("Antent & TRE FLIP") == "Antent"
    assert speed_label(0.85) == "Slowed (~85 % Tempo)"


def test_variant_search_only_when_suspicious():
    exact = Recognition("shazam", "Get Lucky", ["Daft Punk"], skew=0.00006)
    skewed = Recognition("shazam", "Lust & Pride", ["Nicolas Cuer"], skew=0.0146)
    other = Recognition("shazam+audd", "X", ["Y"], skew=0.02)   # mehrere Dienste einig -> vertrauen
    assert variants.suspicious(None)
    assert not variants.suspicious(exact)
    assert variants.suspicious(skewed)
    assert not variants.suspicious(other)


def test_catalog_niche_genres():
    from tunebridge.genres.classify import CATALOG_STATS
    assert CATALOG_STATS.get("total", 0) > 6000
    c = classify({"dariacore": 40, "breakcore": 10})
    assert (c.genre, c.subgenre, c.niche) == ("Breakcore", "Mashcore / Dariacore", None)   # nicht doppelt
    c = classify({"jersey club": 40})
    assert (c.genre, c.subgenre, c.niche) == ("Electronic", "Ghetto Club", "Jersey Club")
    assert classify({"drift phonk": 50}).subgenre == "Drift Phonk"         # früher: „ft“ wurde abgeschnitten
    assert classify({"sigilkore": 30}).genre == "Hip-Hop"
    assert classify({"splittercore": 30}).genre == "Hardstyle / Hardcore"
    assert classify({"hadrami music": 30}).niche == "Hadrami Music"        # Nische ohne Familie


def test_normalize_keeps_words_containing_ft():
    from tunebridge.matching import normalize
    assert normalize("Lift Me Up") == "lift me up"
    assert normalize("Song (feat. X)") == "song"


def test_learn_new_genre_automatically(tmp_path, monkeypatch):
    """Ein unbekannter Tag bei mehreren Songs desselben Genres wird automatisch gelernt (ohne LLM: ab 4 Songs)."""
    from tunebridge import store
    from tunebridge.genres import learn
    from tunebridge.genres.classify import set_learned
    monkeypatch.setattr(store, "DB", tmp_path / "t.db")
    monkeypatch.setattr(learn, "_ask_llm", lambda label, cooc: None)          # LLM aus
    # Hintergrund-Thread im Test direkt ausführen
    monkeypatch.setattr(learn.threading, "Thread", lambda target, args, daemon: type("T", (), {"start": lambda s: target(*args)})())
    set_learned({})

    assert classify({"glorpwave": 60}).genre is None
    # alter Verlaufseintrag mit dem Tag -> soll nach dem Lernen neu bestimmt werden
    from tunebridge.models import Track
    store.add_recognition("desktop", "shazam", 1, Track("Alt", ["X"], tags={"glorpwave": 60}), {"genre_source": "tags"})
    for i in range(3):
        learn.observe(f"k{i}", {"glorpwave": 60, "rap": 80}, "Hip-Hop", ["glorpwave"])
    assert learn.overview()["candidates"][0]["songs"] == 3          # noch zu wenig
    learn.observe("k3", {"glorpwave": 60, "rap": 80}, "Hip-Hop", ["glorpwave"])
    ov = learn.overview()
    assert ov["learned"] and ov["learned"][0]["main"] == "Hip-Hop" and ov["learned"][0]["how"] == "auto"
    c = classify({"glorpwave": 60})
    assert (c.genre, c.niche) == ("Hip-Hop", "Glorpwave")
    assert store.history(1)[0]["track"]["genre"] == "Hip-Hop"     # alter Eintrag aktualisiert

    # uneinig -> bleibt Kandidat
    for i, g in enumerate(["House", "Techno", "House", "Pop"]):
        learn.observe(f"m{i}", {"blubbcore": 50}, g, ["blubbcore"])
    assert any(d["tag"] == "blubbcore" for d in learn.overview()["candidates"])

    # Nutzer lehnt ab / ordnet zu
    learn.set_term("blubbcore", "accept", "House", None)
    assert classify({"blubbcore": 50}).genre == "House"
    learn.set_term("glorpwave", "reject")
    assert classify({"glorpwave": 60}).genre is None
    set_learned({})


def test_noise_tags_are_not_learned():
    from tunebridge.genres.learn import is_noise
    for t in ["seen live", "2019", "90s", "russian", "sad", "my favourites", "albums i own", "female vocalists",
              "dreamscape records", "under 2000 listeners", "5 stars", "tiktok"]:
        assert is_noise(t), t
    for t in ["sigilkore", "hexd", "krushclub", "dreamscape", "jungle terror", "latin trap"]:
        assert not is_noise(t), t


def test_ratelimit_budget_and_pause(monkeypatch):
    import pytest
    from tunebridge import ratelimit
    lim = ratelimit._Limit("Test", 3, 60, gap=0, pause=30)
    monkeypatch.setitem(ratelimit.LIMITS, "test", lim)
    for _ in range(3):
        ratelimit.wait_sync("test", max_wait=0)
    assert ratelimit.free("test") == 0
    with pytest.raises(ratelimit.LimitReached):          # Budget aufgebraucht -> nicht ewig warten
        ratelimit.wait_sync("test", max_wait=1)
    lim.hits.clear()
    ratelimit.blocked("test", 12, "HTTP 429")             # Dienst blockt -> Pause wird angezeigt
    st = next(x for x in ratelimit.state() if x["id"] == "test")
    assert 10 <= st["paused"] <= 12 and st["reason"] == "HTTP 429"
    with pytest.raises(ratelimit.LimitReached):
        ratelimit.wait_sync("test", max_wait=999)


def test_lastfm_garbage_response_is_http_error(monkeypatch):
    """Fehlerseite statt JSON darf die Genre-Bestimmung nicht abstürzen lassen."""
    import httpx
    import pytest

    from tunebridge.genres.sources import lastfm

    lf = lastfm.LastFM(api_key="x")
    calls = []

    def fake_get(url, params=None):
        calls.append(1)
        return httpx.Response(502, text="<html>Bad Gateway</html>", request=httpx.Request("GET", url))

    monkeypatch.setattr(lf.http, "get", fake_get)
    monkeypatch.setattr("time.sleep", lambda s: None)
    with pytest.raises(httpx.HTTPError):
        lf._call("track.getTopTags", artist="a", track="b")
    assert len(calls) == 2


def test_junk_tags_and_genre_fixes():
    from tunebridge.enrich import junk_tags
    from tunebridge.genres.classify import classify

    assert junk_tags({"rock": 100, "grunge": 100, "test-tag": 65, "batch-test": 32})
    assert not junk_tags({"phonk": 50, "drift phonk": 3})
    # Sammelbegriff „Electronic“ (witch house) darf konkretes „wave“ nicht schlagen
    assert classify({"witch house": 50, "wave": 28, "hardwave": 18.5, "phonk": 1}).subgenre == "Wave"
    # Stimmungs-Tag „chill“ ist kein Ambient
    assert classify({"chill": 21, "synthwave": 30}).genre == "Synthwave"
    # „trap“ mit Rap-Tags = Hip-Hop, mit Phonk bleibt Phonk
    assert classify({"trap": 100, "rap": 39}).genre == "Hip-Hop"
    assert classify({"phonk": 40, "hip hop": 50, "trap": 30}).genre == "Phonk"
    assert classify({"industrial metal": 100, "industrial": 35}).genre == "Rock / Metal"
    assert classify({"br funk": 20, "phonk": 10}).subgenre == "Brazilian Phonk"


def test_namesake_artist_does_not_beat_apple_genre(tmp_path, monkeypatch):
    """Poni – NOTHING LEFT TO LOVE: Last.fm kennt den Song nicht, „Poni“ ist dort eine albanische Popsängerin.
    Per Link (kein Shazam-Genre) muss Apples Genre „Dubstep“ gewinnen, nicht die Künstler-Tags „pop“."""
    from tunebridge import config, enrich, links, store
    from tunebridge.genres.sources import lastfm
    from tunebridge.recognize.engines import Recognition
    monkeypatch.setattr(store, "DB", tmp_path / "t.db")
    monkeypatch.setattr(config, "opt", lambda k, d=None: "x" if k == "LASTFM_API_KEY" else d)
    monkeypatch.setattr(enrich, "deezer", lambda rec: {})
    monkeypatch.setattr(enrich, "deezer_genres", lambda dz: [])
    monkeypatch.setattr(enrich, "llm_genre", lambda t: None)
    monkeypatch.setattr(enrich, "llm_subgenre", lambda t, g, provider=None: None)
    monkeypatch.setattr(lastfm.LastFM, "song_tags", lambda self, t: {})
    monkeypatch.setattr(enrich, "mb_tags", lambda t: {})
    monkeypatch.setattr(lastfm.LastFM, "artist_tags", lambda self, a: {"pop": 100.0, "albania": 25.0, "electronic": 4.0})
    monkeypatch.setattr(links, "itunes_song", lambda t: {"url": "u", "genre": "Dubstep"})
    rec = Recognition(engine="link", title="NOTHING LEFT TO LOVE", artists=["Poni", "NO-VA", "Sunborn"])
    track, _ = enrich._enrich_online(rec)
    assert track.genre == "Dubstep"


def test_service_genres_agree_by_main_genre():
    from tunebridge.genres.classify import services_agree
    assert services_agree("Dubstep", "Electro")          # Poni: Apple + Deezer einig
    assert services_agree("Pop", "Pop")
    assert not services_agree("Pop", "Electro")           # Kordhell: nur grobes Etikett
    assert not services_agree("Classical", "Dance")

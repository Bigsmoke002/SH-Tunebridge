"""Link-Import, Kauf-Links ohne Provision, KI-Musik-Hinweise, KI-Anbieter-Einwilligung."""

import pytest

from tunebridge.models import Track


@pytest.fixture
def db(tmp_path, monkeypatch):
    from tunebridge import config, store
    monkeypatch.setattr(config, "DATA", tmp_path)
    monkeypatch.setattr(store, "DB", tmp_path / "t.db")
    return store


@pytest.mark.parametrize("url,exp", [
    ("https://www.deezer.com/de/playlist/123", ("deezer", "playlist", "123")),
    ("https://open.spotify.com/intl-de/album/4aawyAB9vmqN3uQ7FjRGTy?si=x", ("spotify", "album", "4aawyAB9vmqN3uQ7FjRGTy")),
    ("https://tidal.com/browse/playlist/0b5df380-47d3-48fe-ae66-8f0dba90b1ee", ("tidal", "playlist", "0b5df380-47d3-48fe-ae66-8f0dba90b1ee")),
    ("https://music.apple.com/de/album/x/1440857781?i=1440857795", ("apple", "track", "1440857795")),
    ("https://music.youtube.com/watch?v=abc&list=RDx", ("youtube", "track", "abc")),
    ("https://www.youtube.com/playlist?list=PL1", ("youtube", "playlist", "PL1")),
])
def test_parse_links(url, exp):
    from tunebridge import linkimport
    p = linkimport.parse(url)
    assert (p["service"], p["kind"], p["id"]) == exp


def test_unknown_link():
    from tunebridge import linkimport
    with pytest.raises(linkimport.LinkError):
        linkimport.parse("https://example.com/song")


def test_split_youtube_title():
    from tunebridge.linkimport import split_title
    assert split_title("Netsky - Come Alive (Official Video)") == (["Netsky"], "Come Alive")
    assert split_title("Come Alive", "Netsky - Topic") == (["Netsky"], "Come Alive")


def test_buy_links_have_no_affiliate(db):
    from tunebridge import links
    shops = links.buy_links(Track(title="One More Time", artists=["Daft Punk"]))
    tiers = [s["tier"] for s in shops]                 # beste Qualität zuerst: Hi-Res -> verlustfrei -> MP3/AAC
    rank = {"hires": 0, "lossless": 1, "lossy": 2}
    assert tiers == sorted(tiers, key=rank.get) and tiers[0] == "hires" and tiers[-1] == "lossy"
    assert all(s["format"] for s in shops)
    for s in shops:
        assert not any(k in s["url"].lower() for k in ("tag=", "affiliate", "at=", "ref=", "partner"))


def test_ai_hints(db):
    from tunebridge import aidetect
    ai = Track(title="Dust on the Wind", artists=["The Velvet Sundown"], tags={"ai": 100, "ai slop": 60, "rock": 50})
    assert aidetect.check(ai)["status"] in ("hinweis", "wahrscheinlich")
    assert aidetect.check(Track(title="x", artists=["Y"], tags={"rock": 100}))["status"] == "kein_hinweis"
    assert aidetect.check(Track(title="Story", artists=["AI"], tags={"ai": 100, "j-pop": 80}))["status"] == "kein_hinweis"
    assert aidetect.check(Track(title="x", artists=["Y"]), {"label": "Made with Suno"})["status"] != "kein_hinweis"
    aidetect.mark(ai, "mensch")
    assert aidetect.check(ai)["status"] == "markiert_mensch"
    aidetect.mark(ai, None)
    assert aidetect.check(ai)["status"] != "markiert_mensch"


def test_cloud_ai_needs_key_and_consent(db, monkeypatch):
    from tunebridge import ai, config
    monkeypatch.delenv("TB_OPENAI_KEY", raising=False)
    monkeypatch.setattr(config, "CONFIG_FILE", db.DB.parent / "c.env")
    monkeypatch.setattr(config, "CONFIG_DIR", db.DB.parent)
    ai.save_settings({"provider": "openai"})
    assert ai.settings()["auto_genre"] is False          # Cloud: automatisch aus
    assert not ai.ready()[0] and "Key" in ai.ready()[1]
    ai.save_settings({"key": "sk-test"})
    assert not ai.ready()[0] and "zustimmen" in ai.ready()[1]
    ai.save_settings({"consent": {"openai": True}})
    assert ai.ready()[0]
    with pytest.raises(ai.AIError):
        ai.ask_auto("x") or ai.ask("x")                  # kein Modell gewählt -> sauberer Fehler

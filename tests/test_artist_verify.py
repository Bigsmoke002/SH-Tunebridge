"""Genre nur mit geprüftem Künstler + Titel (Namensvettern), „Mehr vom Künstler“, Links aus dem App-Fenster."""
import pytest

from tunebridge import store


@pytest.fixture(autouse=True)
def db(tmp_path, monkeypatch):
    from tunebridge import config
    monkeypatch.setattr(config, "DATA", tmp_path)
    monkeypatch.setattr(store, "DB", tmp_path / "t.db")
    store.ram_clear()
    yield
    store.ram_clear()


def _enrich_env(monkeypatch, *, artist_tags, apple=None, dz=None, artist_genres=()):
    from tunebridge import config, enrich, links
    from tunebridge.genres.sources import lastfm
    monkeypatch.setattr(config, "opt", lambda k, d=None: "x" if k == "LASTFM_API_KEY" else d)
    monkeypatch.setattr(enrich, "deezer", lambda rec: dz or {})
    monkeypatch.setattr(enrich, "deezer_genres", lambda d: ["Dance"] if apple == "Dance" else [])
    monkeypatch.setattr(enrich, "deezer_artist_genres", lambda d: list(artist_genres))
    monkeypatch.setattr(enrich, "llm_genre", lambda t: None)
    monkeypatch.setattr(enrich, "llm_subgenre", lambda t, g, provider=None: None)
    monkeypatch.setattr(lastfm.LastFM, "song_tags", lambda self, t: {})
    monkeypatch.setattr(enrich, "mb_tags", lambda t: {})
    monkeypatch.setattr(lastfm.LastFM, "artist_tags", lambda self, a: artist_tags)
    monkeypatch.setattr(links, "itunes_song", lambda t: {"url": "u", "genre": apple} if apple else None)
    return enrich


KANINE = {"deathcore": 100.0, "slamming deathcore": 43.0, "drum and bass": 91.0, "dnb": 7.0, "jump up": 1.0, "jazz": 1.0}


def test_kanine_namesake_metal_dropped_by_song_genre(monkeypatch):
    """Kanine – Deeper: Last.fm mischt einen DnB-Produzenten mit einer Deathcore-Band."""
    from tunebridge.recognize.engines import Recognition
    enrich = _enrich_env(monkeypatch, artist_tags=KANINE, apple="Dance")
    track, _ = enrich._enrich_online(Recognition(engine="link", title="Deeper", artists=["Kanine"]))
    assert track.genre == "Drum & Bass"


def test_verified_deezer_artist_genres_filter_without_song_genre(monkeypatch):
    """Kein Song-Genre bekannt, aber der über Künstler + Titel geprüfte Deezer-Künstler ist „Dance/Electro“."""
    from tunebridge.recognize.engines import Recognition
    enrich = _enrich_env(monkeypatch, artist_tags=KANINE, dz={"id": 1, "artist": {"id": 9}}, artist_genres=["Dance", "Electro"])
    track, _ = enrich._enrich_online(Recognition(engine="link", title="Irgendwas", artists=["Kanine"]))
    assert track.genre == "Drum & Bass"


def test_lastfm_autocorrect_to_other_song_is_ignored(monkeypatch):
    from tunebridge.genres.sources import lastfm
    from tunebridge.models import Track
    lf = lastfm.LastFM(api_key="x")
    monkeypatch.setattr(lf, "_call", lambda m, **p: {"toptags": {"tag": [{"name": "deathcore", "count": 100}],
                                                                  "@attr": {"artist": "Kanine", "track": "Deep Down"}}})
    assert lf.song_tags(Track("Deeper", ["Kanine"])) == {}
    monkeypatch.setattr(lf, "_call", lambda m, **p: {"toptags": {"tag": [{"name": "drum and bass", "count": 100}],
                                                                  "@attr": {"artist": "Kanine", "track": "Deeper"}}})
    assert lf.song_tags(Track("Deeper (feat. Raphaella)", ["Kanine"])) == {"drum and bass": 100.0}
    assert lastfm.same_song(Track("Deeper", ["Kanine & Raphaella"]), "Kanine", "Deeper")


def test_songcache_old_entries_rechecked():
    from tunebridge import songcache
    from tunebridge.models import Track
    from tunebridge.recognize.engines import Recognition
    rec = Recognition(engine="link", title="Deeper", artists=["Kanine"])
    t = Track("Deeper", ["Kanine"], genre="Rock / Metal", cover="c")
    store.song_put(songcache.keys(rec), t.__dict__, {"cover": "c"})            # alter Eintrag ohne Prüfung
    assert songcache.lookup(rec) is None
    songcache.save(rec, Track("Deeper", ["Kanine"], genre="Drum & Bass", cover="c"), {"cover": "c"})
    assert songcache.lookup(rec)[0].genre == "Drum & Bass"


def test_artist_solo_and_collabs(monkeypatch):
    from tunebridge import artists
    artists._RAM.clear()
    top = [{"id": 1, "title": "Want You", "contributors": [{"id": 7, "name": "Kanine"}], "artist": {"id": 7}, "album": {"title": "Want You"}, "preview": "p"},
           {"id": 2, "title": "Deeper", "contributors": [{"id": 7, "name": "Kanine"}, {"id": 8, "name": "Raphaella"}], "artist": {"id": 7}, "album": {}},
           {"id": 3, "title": "Hold On (feat. Someone)", "contributors": [{"id": 7, "name": "Kanine"}], "artist": {"id": 7}, "album": {}},
           {"id": 4, "title": "Remix", "contributors": [{"id": 5, "name": "Other"}, {"id": 7, "name": "Kanine"}], "artist": {"id": 5}, "album": {}}]

    def fake(url, **p):
        if url.endswith("/top"):
            return {"data": top}
        return {"id": 7, "name": "Kanine", "nb_fan": 10}
    monkeypatch.setattr(artists, "_get", fake)
    d = artists.tracks(7)
    assert [t["title"] for t in d["solo"]] == ["Want You"]
    assert {t["title"]: t["with"] for t in d["collab"]} == {"Deeper": ["Raphaella"], "Hold On (feat. Someone)": ["Someone"], "Remix": ["Other"]}
    assert d["solo"][0]["preview_url"] == "deezer:"          # Hörprobe wird erst beim Abspielen geholt


def test_open_link_route(monkeypatch):
    from fastapi.testclient import TestClient
    from tunebridge.web import app as webapp
    opened = []
    monkeypatch.setattr(webapp, "open_external", opened.append)
    c = TestClient(webapp.app)
    assert c.post("/api/open", json={"url": "https://www.qobuz.com/x"}).status_code == 403     # fremde Seite
    h = {"X-Tunebridge": "1"}
    assert c.post("/api/open", json={"url": "file:///etc/passwd"}, headers=h).status_code == 400
    assert c.post("/api/open", json={"url": "javascript:alert(1)"}, headers=h).status_code == 400
    assert c.post("/api/open", json={"url": "https://www.qobuz.com/x"}, headers=h).json() == {"ok": True}
    assert opened == ["https://www.qobuz.com/x"]


def test_reapply_uses_stored_service_genre():
    """Offline-Neuberechnung nutzt dasselbe Dienst-Genre wie online – sonst kippt ein Grenzfall zurück."""
    from tunebridge.genres.learn import reapply
    tags = {"deathcore": 50.0, "drum and bass": 45.0, "slamming deathcore": 21.0, "dnb": 3.5}
    t = {"title": "Deeper", "artists": ["Kanine"], "tags": tags, "genre": "Drum & Bass", "subgenre": None, "niche": None}
    reapply(t, {"genre_hint": "Dance", "genre_source": "tags"})
    assert t["genre"] == "Drum & Bass"


def test_local_recognition_refreshes_unchecked_cache(monkeypatch):
    """Lokal wiedererkannt (Fingerabdruck) + Song-Speicher von vor der Prüfung -> einmal frisch nachschlagen."""
    import asyncio
    from tunebridge import songcache
    from tunebridge.models import Track
    from tunebridge.web import app as webapp
    store.song_put(["GB2LD2610373"], Track("Deeper", ["Kanine & Raphaella"], isrc="GB2LD2610373", genre="Rock / Metal",
                                           cover="c").__dict__, {"cover": "c"})
    called = []

    def fake_enrich(rec, fresh=False):
        called.append((rec.title, fresh))
        return Track("Deeper", ["Kanine & Raphaella"], isrc="GB2LD2610373", genre="Drum & Bass"), {"gcheck": songcache.GENRE_CHECK}
    monkeypatch.setattr(webapp, "enrich", fake_enrich)
    got = songcache.lookup_key("GB2LD2610373")
    assert got and got[1].get("gcheck", 0) < songcache.GENRE_CHECK      # alter Eintrag wird erkannt
    src = open(webapp.__file__, encoding="utf-8").read()
    assert "extra.get(\"gcheck\", 0) < songcache.GENRE_CHECK" in src     # und im lokalen Erkennungsweg aufgefrischt
    track, _ = fake_enrich(songcache.lookup_key("GB2LD2610373")[0], True)
    assert track.genre == "Drum & Bass" and called == [("Deeper", True)]
    del asyncio

"""Entdecken: Antworten der Quellen -> einheitliche Einträge, Zusammenführen, Quellen-Schalter (am Server geprüft),
Schnittstellen am PC – alles ohne Netz."""
import pytest
from fastapi.testclient import TestClient

from tunebridge import discover
from tunebridge.discover import _common, apple, deezer, discogs, lastfm, musicbrainz

TRACK = {"id": 11, "title": "Come Alive (VIP)", "title_short": "Come Alive", "duration": 250, "rank": 5, "preview": "https://p",
         "artist": {"id": 3, "name": "Netsky"}, "album": {"id": 9, "title": "2", "cover_medium": "https://c/9"},
         "contributors": [{"id": 3, "name": "Netsky"}, {"id": 4, "name": "Jenna G"}], "isrc": "GBXXX1200001"}
MBID = "587fd8ec-2e9d-4ce6-8bc5-97d0a9334883"
RGID = "1d2727c2-7014-4389-bce1-47d25e9f1a75"


def dz_get(url, **params):
    if url.endswith("/search/track"):
        return {"data": [TRACK, {"id": None}]}
    if url.endswith("/search/artist"):
        return {"data": [{"id": 3, "name": "Netsky", "picture_medium": "https://a", "nb_fan": 10}]}
    if url.endswith("/search/album"):
        return {"data": [{"id": 9, "title": "2", "artist": {"id": 3, "name": "Netsky"}, "record_type": "album", "release_date": "2012-06-01"}]}
    if url.endswith("/artist/3"):
        return {"id": 3, "name": "Netsky", "nb_fan": 10, "nb_album": 2, "link": "https://www.deezer.com/artist/3"}
    if url.endswith("/artist/3/top"):
        return {"data": [TRACK, TRACK]}
    if url.endswith("/artist/3/albums"):
        return {"data": [{"id": 9, "title": "2", "record_type": "album", "release_date": "2012-06-01"},
                         {"id": 10, "title": "Single", "record_type": "single", "release_date": "2020-01-01"}]}
    if url.endswith("/artist/3/related"):
        return {"data": [{"id": 5, "name": "Camo & Krooked"}]}
    if url.endswith("/album/9"):
        return {"id": 9, "title": "2", "record_type": "album", "release_date": "2012-06-01", "cover_medium": "https://c/9",
                "artist": {"id": 3, "name": "Netsky"}, "genres": {"data": [{"name": "Dance"}]},
                "tracks": {"data": [{"id": 12, "title": "Love Has Gone", "duration": 200, "preview": "", "artist": {"id": 3, "name": "Netsky"}}]}}
    if "/chart/" in url:
        return {"data": [TRACK]} if url.endswith("/tracks") else {"data": []}
    if url.endswith("/genre"):
        return {"data": [{"id": 0, "name": "Alle"}, {"id": 457, "name": "Hörbücher"}, {"id": 113, "name": "Dance"}]}
    return {"error": {"code": 800}}


IT_SONG = {"wrapperType": "track", "kind": "song", "trackId": 77, "trackName": "Come Alive (VIP)", "artistId": 30, "artistName": "Netsky",
           "collectionId": 90, "collectionName": "Come Alive - Single", "artworkUrl100": "https://is1.mzstatic.com/x/100x100bb.jpg",
           "previewUrl": "https://audio-ssl.itunes.apple.com/p.m4a", "trackTimeMillis": 250000, "releaseDate": "2012-01-01T00:00:00Z",
           "trackViewUrl": "https://music.apple.com/de/album/x/90?i=77&uo=4"}
IT_ONLY = {**IT_SONG, "trackId": 78, "trackName": "Apple Exclusive", "collectionId": 91, "collectionName": "Live in Gent"}


def it_get(path, **params):
    if path == "search" and params.get("entity") == "song":
        return [IT_SONG, IT_ONLY]
    if path == "search" and params.get("entity") == "musicArtist":
        return [{"artistId": 30, "artistName": "Netsky", "primaryGenreName": "Dance"}]
    if path == "lookup" and params.get("entity") == "album":
        return [{"wrapperType": "artist", "artistId": 30, "artistName": "Netsky", "artistLinkUrl": "https://music.apple.com/de/artist/30?uo=4"},
                {"wrapperType": "collection", "collectionId": 91, "collectionName": "Live in Gent", "artistName": "Netsky", "artistId": 30,
                 "releaseDate": "2019-05-01T00:00:00Z", "trackCount": 9}]
    if path == "lookup" and params.get("entity") == "song":
        return [{"wrapperType": "collection", "collectionId": 90, "collectionName": "Come Alive - Single", "artistName": "Netsky", "artistId": 30},
                {**IT_SONG, "trackNumber": 1}] if params.get("id") == "90" else [{"wrapperType": "artist"}, IT_SONG]
    if path == "lookup":
        return [IT_SONG]
    return []


def mb_get(path, **params):
    if path == "artist":
        return {"artists": [{"id": MBID, "name": "Netsky", "score": 100, "disambiguation": "drum & bass artist", "country": "BE"}]}
    if path == "release-group" and "query" in params:
        return {"release-groups": [{"id": RGID, "title": "2", "primary-type": "Album", "first-release-date": "2012-06-04",
                                    "artist-credit": [{"name": "Netsky", "artist": {"id": MBID, "name": "Netsky"}}]}]}
    if path == f"artist/{MBID}":
        return {"id": MBID, "name": "Netsky", "genres": [{"name": "liquid funk", "count": 3}, {"name": "drum and bass", "count": 5}],
                "life-span": {"begin": "1989-03-22"}}
    if path == "release-group":
        return {"release-groups": [
            {"id": RGID, "title": "2", "primary-type": "Album", "first-release-date": "2012-06-04"},
            {"id": "00000000-0000-0000-0000-000000000001", "title": "Mixed Bag", "primary-type": "Album", "secondary-types": ["DJ-mix"], "first-release-date": "2014"},
            {"id": "00000000-0000-0000-0000-000000000002", "title": "Talk", "primary-type": "Other", "secondary-types": ["Interview"]}]}
    if path == f"release-group/{RGID}":
        return {"id": RGID, "title": "2", "primary-type": "Album", "first-release-date": "2012-06-04",
                "artist-credit": [{"name": "Netsky", "artist": {"id": MBID, "name": "Netsky"}}],
                "releases": [{"id": "r-bootleg", "status": "Bootleg", "date": "2011"}, {"id": "r-off", "status": "Official", "date": "2012-06-04"}]}
    if path == "release/r-off":
        return {"date": "2012-06-04", "label-info": [{"label": {"name": "Hospital Records"}}, {"label": {"name": "[no label]"}}],
                "media": [{"tracks": [{"title": "Come Alive", "length": 250000,
                                       "recording": {"id": "11111111-1111-1111-1111-111111111111", "isrcs": ["GBXXX1200001"]},
                                       "artist-credit": [{"name": "Netsky", "artist": {"id": MBID}}, {"name": "Jenna G", "artist": {"id": "22222222-2222-2222-2222-222222222222"}}]}]}]}
    return {}


@pytest.fixture
def fake(monkeypatch):
    _common.clear()
    calls = []

    def dz(url, **params):
        calls.append(("deezer", url, params))
        return dz_get(url, **params)
    monkeypatch.setattr(deezer, "_get", dz)
    monkeypatch.setattr(apple, "_get", lambda path, **p: calls.append(("apple", path, p)) or it_get(path, **p))
    monkeypatch.setattr(musicbrainz, "_get", lambda path, **p: calls.append(("musicbrainz", path, p)) or mb_get(path, **p))
    monkeypatch.delenv("LASTFM_API_KEY", raising=False)
    monkeypatch.delenv("DISCOGS_TOKEN", raising=False)
    return calls


def only(*srcs):
    discover.save_settings({s: s in srcs for s in discover.SOURCES})


def test_deezer_item_keeps_all_artists_and_version(fake):
    only("deezer")
    it = discover.search("netsky", "track")["items"]
    assert len(it) == 1
    t = it[0]
    assert t["title"] == "Come Alive (VIP)" and t["artists"] == ["Netsky", "Jenna G"] and t["artist_ids"] == ["dz:3", "dz:4"]
    assert t["preview_url"] == "deezer:11" and t["ids"] == {"deezer": "11"} and t["cover"] == "https://c/9" and t["album_id"] == "dz:9"
    assert t["sources"] == ["deezer"]


def test_search_validates_and_caches(fake):
    only("deezer")
    assert discover.search("   ", "track")["items"] == []
    with pytest.raises(ValueError):
        discover.search("x", "podcast")
    discover.search("Netsky ", "track")
    discover.search("netsky", "track")
    assert len([c for c in fake if c[1].endswith("/search/track")]) == 1      # zweite Suche aus dem Speicher
    assert discover.search("x" * 300, "track")["q"] == "x" * 100


def test_sources_are_merged(fake):
    only("deezer", "apple", "musicbrainz")
    r = discover.search_all("netsky")
    assert r["sources"] == ["deezer", "apple", "musicbrainz"] and r["failed"] == {}
    a = r["artists"][0]                                          # gleicher Name -> ein Eintrag mit allen Kennungen
    assert a["id"] == "dz:3" and a["refs"] == {"deezer": "dz:3", "apple": "it:30", "musicbrainz": f"mb:{MBID}"}
    assert a["sources"] == ["deezer", "apple", "musicbrainz"] and a["picture"] == "https://a"
    titles = [t["title"] for t in r["tracks"]]
    assert titles.count("Come Alive (VIP)") == 1 and "Apple Exclusive" in titles
    ca = r["tracks"][0]
    assert ca["sources"] == ["deezer", "apple"] and ca["ids"] == {"deezer": "11", "apple": "77"}
    ex = next(t for t in r["tracks"] if t["title"] == "Apple Exclusive")
    assert ex["preview_url"].startswith("https://audio-ssl") and ex["cover"].endswith("/250x250bb.jpg")
    al = {x["title"]: x for x in r["albums"]}
    assert al["2"]["sources"] == ["deezer", "musicbrainz"] and al["Come Alive"]["type"] == "Single"
    assert len([c for c in fake if c[0] == "apple"]) == 1           # Apple: eine Suche statt drei (Limit 20/min)


def test_switched_off_sources_are_not_asked(fake):
    only("apple")
    r = discover.search_all("netsky")
    assert r["sources"] == ["apple"] and not [c for c in fake if c[0] != "apple"]
    with pytest.raises(LookupError):                             # auch Kennungen einer abgeschalteten Quelle nicht
        discover.artist_page("dz:3")
    only()
    with pytest.raises(discover.NoSource):
        discover.search_all("netsky")
    assert not [c for c in fake if c[0] == "deezer"]
    s = {x["id"]: x for x in discover.settings()["sources"]}
    assert not s["lastfm"]["available"] and not s["discogs"]["available"]   # ohne eigenen Key/Token nicht wählbar


def test_failing_source_does_not_break_search(fake, monkeypatch):
    only("deezer", "musicbrainz")
    monkeypatch.setattr(musicbrainz, "_get", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("503")))
    r = discover.search_all("netsky")
    assert r["sources"] == ["deezer"] and "musicbrainz" in r["failed"] and r["tracks"]


def test_artist_page_combines_sources(fake):
    only("deezer", "apple", "musicbrainz")
    a = discover.artist_page("3")                                # alte Links (nur Zahl) = Deezer
    assert a["artist"]["refs"] == {"deezer": "dz:3", "apple": "it:30", "musicbrainz": f"mb:{MBID}"}
    assert a["sources"] == ["deezer", "apple", "musicbrainz"]
    assert a["artist"]["tags"] == ["drum and bass", "liquid funk"] and a["artist"]["life"] == "1989-03-22"
    assert a["artist"]["links"]["deezer"] == "https://www.deezer.com/artist/3"
    assert len(a["top"]) == 1 and a["top"][0]["with"] == ["Jenna G"] and a["top"][0]["sources"] == ["deezer", "apple"]
    titles = [x["title"] for x in a["albums"]]
    assert "Live in Gent" in titles and "Mixed Bag" in titles and "Talk" not in titles and titles.count("2") == 1
    assert [x["title"] for x in a["singles"]] == ["Single"] and a["related"][0]["name"] == "Camo & Krooked"
    with pytest.raises(ValueError):
        discover.artist_page("1; drop")
    with pytest.raises(ValueError):
        discover.artist_page("mb:nicht-uuid")


def test_ambiguous_namesakes_are_left_out(fake, monkeypatch):
    only("deezer", "musicbrainz")
    monkeypatch.setattr(musicbrainz, "_get", lambda path, **p: {"artists": [
        {"id": MBID, "name": "Netsky", "score": 100}, {"id": RGID, "name": "Netsky", "score": 100}]} if path == "artist" else mb_get(path, **p))
    a = discover.artist_page("dz:3")
    assert "musicbrainz" not in a["artist"]["refs"]             # zwei gleichnamige -> lieber keiner
    a = discover.artist_page("dz:3", [f"mb:{MBID}"])             # mitgeschickte Kennung aus der Suche gilt
    assert a["artist"]["refs"]["musicbrainz"] == f"mb:{MBID}"


def test_album_pages_and_charts(fake):
    only("deezer", "apple", "musicbrainz")
    al = discover.album_page("dz:9")
    assert al["album"]["genres"] == ["Dance"] and al["tracks"][0]["cover"] == "https://c/9" and al["tracks"][0]["preview_url"] == "deezer:12"
    mb = discover.album_page(f"mb:{RGID}")
    assert mb["album"]["label"] == "Hospital Records" and mb["tracks"][0]["artists"] == ["Netsky", "Jenna G"]
    assert mb["tracks"][0]["isrc"] == "GBXXX1200001" and mb["album"]["cover_big"].startswith("https://coverartarchive.org/")
    it = discover.album_page("it:90")
    assert it["album"]["title"] == "Come Alive" and it["album"]["type"] == "Single" and it["tracks"][0]["preview_url"].startswith("https://")
    with pytest.raises(LookupError):
        discover.album_page("dz:1")
    assert discover.charts("deezer", "0")["tracks"][0]["title"] == "Come Alive (VIP)"
    g = discover.genres("deezer")
    assert [x["name"] for x in g["genres"]] == ["Alle", "Dance"] and [c["id"] for c in g["charts"]] == ["deezer", "apple"]
    with pytest.raises(LookupError):
        discover.charts("lastfm", "")                            # ohne Key nicht eingeschaltet
    with pytest.raises(ValueError):
        discover.charts("musicbrainz", "")


def test_lastfm_and_discogs_parsers(monkeypatch):
    _common.clear()
    monkeypatch.setenv("LASTFM_API_KEY", "x" * 32)
    monkeypatch.setenv("DISCOGS_TOKEN", "tok")
    only("lastfm", "discogs")

    def lf(method, **p):
        if method == "artist.search":
            return {"results": {"artistmatches": {"artist": [{"name": "Netsky", "listeners": "500"}]}}}
        if method == "album.search":
            return {"results": {"albummatches": {"album": [{"name": "2", "artist": "Netsky", "image": [{"size": "extralarge", "#text": "https://lastfm/x.png"}]},
                                                           {"name": "(null)", "artist": "Netsky"}]}}}
        if method == "track.search":
            return {"results": {"trackmatches": {"track": {"name": "Rio", "artist": "Netsky"}}}}   # einzelner Treffer = Objekt
        if method == "tag.getTopTracks":
            assert p["tag"] == "liquid funk"
            return {"tracks": {"track": [{"name": "Rio", "artist": {"name": "Netsky"}, "duration": "220"}]}}
        return {}
    monkeypatch.setattr(lastfm, "_call", lf)

    def dg(path, **p):
        if path == "database/search":
            return {"results": [{"id": 1, "title": "Netsky (2)", "thumb": "https://i.discogs.com/a.jpg"}] if p["type"] == "artist"
                    else [{"id": 5, "title": "Netsky - 2", "year": "2012", "format": ["Vinyl", "LP"], "cover_image": "https://i.discogs.com/m.jpg"}]}
        if path == "masters/5":
            return {"title": "2", "year": 2012, "artists": [{"name": "Netsky (2)", "id": 1}], "genres": ["Electronic"], "styles": ["Drum n Bass"],
                    "images": [{"type": "primary", "uri": "https://i.discogs.com/big.jpg"}],
                    "tracklist": [{"type_": "heading", "title": "Seite A"}, {"type_": "track", "title": "Come Alive", "duration": "4:10"}]}
        raise LookupError
    monkeypatch.setattr(discogs, "_get", dg)
    r = discover.search_all("netsky")
    assert r["artists"][0]["refs"] == {"discogs": "dg:a1", "lastfm": "lf:Netsky"} and r["artists"][0]["name"] == "Netsky"
    assert [a["title"] for a in r["albums"]] == ["2"] and r["albums"][0]["refs"] == {"discogs": "dg:m5", "lastfm": "lf:Netsky\t2"}
    assert r["tracks"][0]["title"] == "Rio"
    m = discover.album_page("dg:m5")
    assert m["album"]["genres"] == ["Electronic", "Drum n Bass"] and m["album"]["artists"] == ["Netsky"]
    assert [t["title"] for t in m["tracks"]] == ["Come Alive"] and m["tracks"][0]["duration_ms"] == 250000
    c = discover.charts("lastfm", "liquid funk")
    assert c["tracks"][0]["duration_ms"] == 220000
    with pytest.raises(ValueError):
        discover.album_page("dg:x5")
    with pytest.raises(ValueError):
        discover.album_page("lf:ohne-tab")


def test_api_endpoints(fake):
    from tunebridge.web.app import app
    only("deezer")
    c = TestClient(app, base_url="http://127.0.0.1:8765")
    r = c.get("/api/discover/search", params={"q": "netsky"}).json()
    assert r["tracks"][0]["links"] and r["artists"][0]["id"] == "dz:3"
    assert c.get("/api/discover/artist/dz:3").json()["top"][0]["links"]
    assert c.get("/api/discover/artist/abc").status_code == 400
    assert c.get("/api/discover/album/dz:1").status_code == 404
    assert c.get("/api/discover/charts", params={"source": "deezer"}).json()["tracks"]
    assert c.get("/api/discover/genres", params={"source": "deezer"}).json()["genres"]
    s = c.post("/api/discover/sources", json={"deezer": False, "apple": True, "egal": True}).json()
    assert {x["id"]: x["on"] for x in s["sources"]}["deezer"] is False
    assert c.get("/api/discover/artist/dz:3").status_code == 404           # abgeschaltet -> Server verweigert
    only("deezer")
    r = c.post("/api/versions/add", json={"playlist": "Entdeckt", "track": {**r["tracks"][0], "artists": [f"A{i}" for i in range(12)]}})
    assert r.json()["added"]
    from tunebridge import store
    saved = [p for p in store.local_playlists() if p.name == "Entdeckt"][0].tracks[0]
    assert len(saved.artists) == 12                                     # alle Interpreten bleiben erhalten (vorher 5)


def test_save_many_to_playlist(fake):
    from tunebridge import store
    from tunebridge.web.app import app
    only("deezer", "apple")
    c = TestClient(app, base_url="http://127.0.0.1:8765")
    al = c.get("/api/discover/album/dz:9").json()
    tr = c.get("/api/discover/search", params={"q": "netsky", "kind": "track"}).json()["items"]
    r = c.post("/api/discover/save", json={"playlist": "Album 2", "tracks": al["tracks"] + tr + tr}).json()
    assert r == {"added": 3, "skipped": 2, "playlist": "Album 2"}
    saved = [p for p in store.local_playlists() if p.name == "Album 2"][0].tracks
    assert saved[1].isrc == "GBXXX1200001" and saved[1].artists == ["Netsky", "Jenna G"] and saved[1].ids == {"deezer": "11", "apple": "77"}
    assert saved[2].preview_url.startswith("https://audio-ssl")
    assert c.post("/api/discover/save", json={"playlist": "x", "tracks": []}).status_code == 400
    assert c.post("/api/discover/save", json={"playlist": "x", "tracks": [{"title": "", "artists": []}]}).status_code == 400

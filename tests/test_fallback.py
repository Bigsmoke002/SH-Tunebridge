"""Ersatz-Hörprobe (YouTube/Spotify-Player): Einwilligung am Server erzwungen, Quellen-Reihenfolge, Zwischenspeicher."""
from fastapi.testclient import TestClient

from tunebridge import fallback, store
from tunebridge.models import Track

H = {"X-Tunebridge": "1"}


def _client():
    from tunebridge.web import app as webapp
    return TestClient(webapp.app)


def test_without_consent_nothing_is_looked_up(monkeypatch):
    calls = []
    monkeypatch.setattr(fallback, "_youtube_search", lambda t: calls.append(t) or "abcdefghijk")
    c = _client()
    assert c.get("/api/fallback", params={"artist": "A", "title": "T", "dz": "1"}).status_code == 403
    assert calls == []
    try:
        fallback.resolve(Track(title="T", artists=["A"], ids={"deezer": "1"}))
        raise AssertionError("ohne Einwilligung muss resolve abbrechen")
    except fallback.NotAllowed:
        pass
    assert calls == []


def test_known_ids_first_then_search_and_only_consented_kinds(monkeypatch):
    calls = []
    monkeypatch.setattr(fallback, "_youtube_search", lambda t: calls.append(t.title) or "zzzzzzzzzzz")
    monkeypatch.setattr(fallback, "_spotify_search", lambda t: (_ for _ in ()).throw(AssertionError("nicht eingewilligt")))
    c = _client()
    assert c.post("/api/fallback/settings", json={"youtube": True}, headers=H).json()["youtube"] is True
    # bekannte Video-ID: keine Anfrage
    r = c.get("/api/fallback", params={"artist": "A", "title": "T", "dz": "1", "yt": "aaaaaaaaaaa"}).json()
    assert r["youtube"] == "aaaaaaaaaaa" and r["spotify"] is None and calls == []
    # unbekannt: offizielle YouTube-Suche; Spotify wird nicht geliefert (nicht eingewilligt)
    r = c.get("/api/fallback", params={"artist": "B", "title": "U", "dz": "7"}).json()
    assert r == {"youtube": "zzzzzzzzzzz", "spotify": None, "via": {"youtube": "YouTube-Suche"}} and calls == ["U"]
    # zweiter Aufruf: aus dem Zwischenspeicher
    c.get("/api/fallback", params={"artist": "B", "title": "U", "dz": "7"})
    assert calls == ["U"]


def test_invalid_ids_are_ignored_and_search_is_last(monkeypatch):
    monkeypatch.setattr(fallback, "_youtube_search", lambda t: "bbbbbbbbbbb")
    monkeypatch.setattr(fallback, "_spotify_search", lambda t: None)
    fallback.save({"youtube": True, "spotify": True})
    r = fallback.resolve(Track(title="T", artists=["A"]), {"youtube": "x\"><script>", "spotify": "../../etc"})
    assert r["youtube"] == "bbbbbbbbbbb" and r["via"]["youtube"] == "YouTube-Suche" and r["spotify"] is None


def test_revoking_clears_remembered_ids(monkeypatch):
    monkeypatch.setattr(fallback, "_youtube_search", lambda t: "ccccccccccc")
    fallback.save({"youtube": True})
    fallback.resolve(Track(title="T", artists=["A"], ids={"deezer": "3"}))
    assert store.cache_get("fallback", "a|t") is not None
    s = fallback.save({"youtube": False})
    assert s["youtube"] is False and s["at"]["youtube"] is None
    assert store.cache_get("fallback", "a|t") is None


def test_youtube_search_with_own_key(monkeypatch):
    """Mit eigenem Key: Suche nur in der Musik-Kategorie, nur einbettbare Videos, bester Treffer per Abgleich."""
    from tunebridge import config

    class R:
        status_code = 200

        def json(self):
            return {"items": [
                {"id": {"videoId": "wrongwrong1"}, "snippet": {"title": "Something Else", "channelTitle": "X - Topic"}},
                {"id": {"videoId": "60ItHLz5WEA"}, "snippet": {"title": "Faded", "channelTitle": "Alan Walker - Topic"}}]}
    seen = {}
    monkeypatch.setattr(config, "opt", lambda k, *a: "KEY" if k == "YOUTUBE_API_KEY" else None)
    monkeypatch.setattr(fallback._http, "get", lambda url, params=None: seen.update(params) or R())
    assert fallback._youtube_search(Track(title="Faded", artists=["Alan Walker"])) == "60ItHLz5WEA"
    assert seen["videoCategoryId"] == "10" and seen["videoEmbeddable"] == "true" and seen["key"] == "KEY"

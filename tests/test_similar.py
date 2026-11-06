"""Ähnliche Songs: Deezer springt ein, wenn Last.fm leer bleibt; leere Ergebnisse werden nicht gemerkt."""
from tunebridge import enrich, similar, store
from tunebridge.models import Track


def _fake_dz(url, **kw):
    if url.endswith("/artist/1/related"):
        return {"data": [{"id": 10 + i, "name": f"A{i}"} for i in range(5)]}
    if "/top" in url:
        aid = int(url.split("/artist/")[1].split("/")[0])
        return {"data": [{"id": aid * 100, "title": f"Hit {aid}", "artist": {"id": aid, "name": f"A{aid - 10}"}}]}
    if url.endswith("/artist/1/radio"):
        return {"data": [{"id": 900 + i, "title": f"R{i}", "artist": {"id": 1 if i == 0 else 50, "name": "Seed" if i == 0 else "Same"}}
                         for i in range(6)]}
    raise AssertionError(url)


def test_deezer_fallback_when_lastfm_empty(monkeypatch):
    monkeypatch.setenv("LASTFM_API_KEY", "x")
    from tunebridge.genres.sources import lastfm
    monkeypatch.setattr(lastfm.LastFM, "similar", lambda self, t, limit=20: [])
    monkeypatch.setattr(enrich, "deezer", lambda rec: {"id": 5, "artist": {"id": 1, "name": "Seed"}})
    monkeypatch.setattr(enrich, "_dz", _fake_dz)
    out = similar.find(Track("Song", ["Seed"]), limit=8)
    names = [t.artists[0] for t, _ in out]
    assert len(out) == 7 and names[:5] == ["A0", "A1", "A2", "A3", "A4"]
    assert names.count("Same") == similar.PER_ARTIST and "Seed" not in names     # Vielfalt, nicht der Künstler selbst


def test_empty_not_cached(monkeypatch):
    monkeypatch.setattr(enrich, "deezer", lambda rec: {})
    monkeypatch.delenv("LASTFM_API_KEY", raising=False)
    assert similar.find(Track("X", ["Y"])) == []
    assert store.cache_get("deezer_similar", "y|x|15") is None

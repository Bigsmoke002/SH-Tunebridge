"""Remixe, Covers & andere Versionen: Einordnung, Filter gegen Füllware/Fremd-Songs, API."""
from tunebridge import remixes
from tunebridge.models import Track


def _h(i, title, artist, dur=200, rank=1000, version="", short=None):
    return {"id": i, "title": title, "title_short": short or title, "title_version": version, "duration": dur,
            "rank": rank, "artist": {"name": artist}, "album": {"title": "A", "cover_medium": f"https://c/{i}.jpg"},
            "preview": f"https://p/{i}.mp3", "link": f"https://www.deezer.com/track/{i}"}


HITS = [
    _h(1, "Faded", "Alan Walker", 212, 900000),
    _h(2, "Faded (Tiesto's Deep House Remix)", "Alan Walker", 200, 500000),
    _h(3, "Faded (Hardstyle Remix)", "Alan Walker", 180, 1000),
    _h(4, "Faded (Live)", "Alan Walker", 230, 2000),
    _h(5, "Faded (Acoustic)", "Alan Walker", 210, 3000),
    _h(6, "Faded (Slowed + Reverb)", "Alan Walker", 260, 4000),
    _h(7, "Faded (Restrung)", "Alan Walker", 215, 5000),          # Klammer ohne Versions-Wort -> anderer Kerntitel
    _h(8, "Faded", "Some Singer", 220, 6000),                      # Cover, Länge passt
    _h(9, "Faded", "Other Band", 600, 7000),                       # gleicher Titel, Länge passt nicht -> raus
    _h(10, "Faded (Karaoke Version)", "Karaoke Kings", 212, 8000),  # Füllware -> raus
    _h(11, "Faded (DJ X Remix)", "DJ X", 190, 9000),               # Remix anderer Künstler -> „andere“
    _h(12, "Faded - Radio Edit", "Alan Walker", 190, 10000),
    _h(13, "Something Else", "Alan Walker", 200, 11000),
]


def _fake(monkeypatch, hits=HITS):
    calls = []

    def q(query, n):
        calls.append(query)
        return list(hits)
    monkeypatch.setattr(remixes, "_query", q)
    return calls


def test_core_title_keeps_title_brackets():
    assert remixes.core_title("Faded (Tiesto's Deep House Remix) - Radio Edit") == "Faded"
    assert remixes.core_title("Blue (Da Ba Dee)") == "Blue (Da Ba Dee)"
    assert remixes.core_title("Blue (Da Ba Dee) [Gabry Ponte Remix]") == "Blue (Da Ba Dee)"
    assert remixes.core_title("Song (feat. Someone)") == "Song"


def test_classify():
    c = remixes.classify
    assert c("Faded (Tiesto's Deep House Remix)", "", "Alan Walker", "Alan Walker") == ("remix", "Remix von Tiesto")
    assert c("Faded (Hardstyle Remix)", "", "Alan Walker", "Alan Walker") == ("remix", "Hardstyle-Remix")
    assert c("Faded (Live)", "", "Alan Walker", "Alan Walker")[0] == "live"
    assert c("Faded (Acoustic)", "", "Alan Walker", "Alan Walker")[0] == "akustik"
    assert c("Faded (Instrumental)", "", "Alan Walker", "Alan Walker")[0] == "instrumental"
    assert c("Faded - Radio Edit", "", "Alan Walker", "Alan Walker")[0] == "edit"
    assert c("Faded (Remastered 2011)", "", "Alan Walker", "Alan Walker")[0] == "original"
    assert c("Faded", "", "Some Singer", "Alan Walker") == ("andere", "Cover oder gleichnamiger Song von Some Singer")
    assert c("Faded (DJ X Remix)", "", "DJ X", "Alan Walker") == ("andere", "Remix von DJ X")
    # Original-Künstler im Titel eines Covers macht es nicht zum Original
    assert c("Mr Brightside [The Killers Cover]", "", "The Hit House", "The Killers")[0] == "andere"


def test_find_groups_and_filters(monkeypatch):
    calls = _fake(monkeypatch)
    out = remixes.find(Track(title="Faded", artists=["Alan Walker"], duration_ms=212000))
    ids = [v["ids"]["deezer"] for v in out]
    assert "9" not in ids and "10" not in ids and "7" not in ids and "13" not in ids
    kinds = [v["kind"] for v in out]
    order = [k for k, _ in remixes.KINDS]
    assert kinds == sorted(kinds, key=order.index)            # nach Art gruppiert
    by = {v["ids"]["deezer"]: v for v in out}
    assert by["1"]["kind"] == "original" and by["2"]["kind"] == "remix" and by["6"]["kind"] == "tempo"
    assert by["8"]["kind"] == "andere" and by["11"]["kind"] == "andere" and by["12"]["kind"] == "edit"
    assert any('artist:"Alan Walker"' in q for q in calls)
    # Zweiter Aufruf aus dem Zwischenspeicher – keine neue Anfrage
    n = len(calls)
    assert remixes.find(Track(title="Faded", artists=["Alan Walker"])) == out
    assert len(calls) == n


def test_find_without_reference_length_drops_short_title_covers(monkeypatch):
    _fake(monkeypatch, [_h(8, "Blue", "Some Singer", 220), _h(11, "Blue (DJ X Remix)", "DJ X", 190)])
    out = remixes.find(Track(title="Blue", artists=["Nobody Known"]))
    assert [v["ids"]["deezer"] for v in out] == ["11"]       # Remix bleibt, Cover eines Allerwelts-Titels nicht


def test_empty_result_not_cached(monkeypatch):
    calls = _fake(monkeypatch, [])
    assert remixes.find(Track(title="Faded", artists=["Alan Walker"])) == []
    n = len(calls)
    remixes.find(Track(title="Faded", artists=["Alan Walker"]))
    assert len(calls) > n


def test_api_versions_and_add(monkeypatch):
    from fastapi.testclient import TestClient

    from tunebridge import store
    from tunebridge.web import app as webapp
    _fake(monkeypatch)
    c = TestClient(webapp.app)
    d = c.get("/api/versions", params={"artist": "Alan Walker", "title": "Faded"}).json()
    assert d["core"] == "Faded" and [k["id"] for k in d["kinds"]][0] == "original"
    v = next(x for x in d["items"] if x["kind"] == "remix")
    assert v["preview_url"] == f"deezer:{v['ids']['deezer']}"     # Hörprobe wird frisch geholt (Adressen laufen ab)
    assert v["links"]
    h = {"X-Tunebridge": "1"}
    r = c.post("/api/versions/add", json={"playlist": "Remixe", "track": v}, headers=h).json()
    assert r == {"added": True, "playlist": "Remixe"}
    assert c.post("/api/versions/add", json={"playlist": "Remixe", "track": v}, headers=h).json()["added"] is False
    assert c.post("/api/versions/add", json={"playlist": " ", "track": v}, headers=h).status_code == 400
    assert c.post("/api/versions/add", json={"playlist": "X", "track": {"title": "", "artists": []}}, headers=h).status_code == 400
    # nur https-Adressen werden übernommen
    bad = {**v, "cover": "javascript:alert(1)", "ids": {"deezer": "../x"}}
    c.post("/api/versions/add", json={"playlist": "Y", "track": bad}, headers=h)
    (t,) = [e["track"] for e in store.playlist_entries("Y")]
    assert not t.get("cover") and "deezer" not in (t.get("ids") or {})
    assert c.get("/api/versions").status_code == 404

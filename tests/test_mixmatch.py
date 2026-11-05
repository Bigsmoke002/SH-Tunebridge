"""„Passt dazu“: mixbare Songs aus der eigenen Bibliothek."""
from tunebridge import audiofeat, mixmatch, store
from tunebridge.models import Track


def test_find_tempo_key_and_unmeasured(monkeypatch):
    me = Track("Ich", ["A"])
    lib = {"Gleich": (128, "8A"), "Nachbar": (126, "9A"), "Halb": (64.5, "8B"), "Weit": (140, "8A"),
           "Bruch": (128, "2B"), "Ungemessen": None}
    for t, f in lib.items():
        tr = Track(t, ["K"])
        store.add_to_playlist("Liste", tr)
        if f:
            store.cache_set("audiofeat", store.track_key(tr), {"bpm": f[0], "camelot": f[1]})
    store.add_to_playlist("Liste", me)                       # der Song selbst zählt nicht
    monkeypatch.setattr(audiofeat, "features", lambda t, deezer_bpm=None: {"bpm": 128, "camelot": "8A", "key": "A Moll"})
    d = mixmatch.find(me)
    assert [m["title"] for m in d["matches"]] == ["Gleich", "Halb", "Nachbar"]
    assert d["unmeasured"] == 1 and d["total"] == 7 and d["song"]["camelot"] == "8A"
    assert d["matches"][0]["playlists"] == ["Liste"]


def test_no_preview(monkeypatch):
    monkeypatch.setattr(audiofeat, "features", lambda t, deezer_bpm=None: None)
    assert mixmatch.find(Track("x", ["y"]))["error"]

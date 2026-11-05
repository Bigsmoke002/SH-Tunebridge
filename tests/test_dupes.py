"""Doppelte Songs in lokalen Playlists."""
from tunebridge import dupes, store
from tunebridge.models import Track


def _add(pl, title, artists, isrc=None):
    store.add_to_playlist(pl, Track(title=title, artists=artists, isrc=isrc))


def test_find_kinds_and_remove():
    _add("Techno", "Song A", ["DJ X"], isrc="DEAA11111111")
    _add("Techno", "Song A (Official Video)", ["DJ X feat. Y"])       # gleicher Song ohne ISRC -> doppelt
    _add("Party", "Song A", ["DJ X"], isrc="DEAA11111111")            # auch in anderer Playlist -> mehrfach
    _add("Techno", "Song A (Hardtekk Remix)", ["DJ X"])                # Version
    _add("Techno", "Song A - Slowed + Reverb", ["DJ X"])               # Version
    _add("Techno", "Anderer Song", ["DJ Z"])
    d = dupes.find()
    assert d["zahlen"]["doppelt"] == 1
    g = d["doppelt"][0]
    assert g["playlist"] == "Techno" and g["keep"]["isrc"] == "DEAA11111111"
    assert d["zahlen"]["mehrfach"] == 1 and {o["playlist"] for o in d["mehrfach"][0]["in"]} == {"Techno", "Party"}
    assert d["zahlen"]["versionen"] == 1
    titles = [o["title"] for o in d["versionen"][0]["songs"]]
    assert titles[0] == "Song A" and len(titles) == 3
    assert dupes.remove([{"playlist": o["playlist"], "key": o["key"]} for o in g["remove"]]) == 1
    assert dupes.find()["zahlen"]["doppelt"] == 0
    assert dupes.remove([{"playlist": "Gibt es nicht", "key": "x"}]) == 0


def test_vip_is_version_not_duplicate():
    _add("A", "Tune", ["Prod"])
    _add("A", "Tune VIP", ["Prod"])
    d = dupes.find()
    assert d["zahlen"]["doppelt"] == 0
    # „Tune VIP“ ohne Klammer zählt nicht als Version (könnte ein eigener Titel sein) – nur bewusst gekennzeichnete
    assert dupes.base_key({"title": "Tune (VIP)", "artists": ["Prod"]}) == dupes.base_key({"title": "Tune", "artists": ["Prod"]})

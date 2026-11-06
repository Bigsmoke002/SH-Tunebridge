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


def test_remix_with_wrong_original_isrc_is_not_duplicate():
    """Alte Einträge: Remix/Flip/Bootleg trugen die ISRC des Originals (falscher Treffer beim Nachschlagen)."""
    rows = [{"playlist": "P", "key": f"k{i}", "ts": i, "track": {"title": t, "artists": ["DJ X"], "isrc": "DEAA11111111"}}
            for i, t in enumerate(["Song A", "Song A (Y Remix)", "Song A (Z Flip)", "Song A (Q Bootleg)", "Song A (Radio Edit)"])]
    d = dupes.find(rows)
    assert d["zahlen"]["doppelt"] == 1                        # nur Radio Edit = derselbe Song wie das Original
    assert {o["title"] for o in d["doppelt"][0]["remove"]} == {"Song A (Radio Edit)"}
    assert d["zahlen"]["versionen"] == 1 and len(d["versionen"][0]["songs"]) == 4


def test_matching_keeps_versions_apart():
    from tunebridge.matching import best_match
    src = Track("Song (A Remix)", ["DJ X"])
    assert best_match(src, [Track("Song", ["DJ X"])], threshold=75) is None
    assert best_match(src, [Track("Song (B Remix)", ["DJ X"])], threshold=75) is None
    assert best_match(src, [Track("Song - A Remix", ["DJ X"])], threshold=75) is not None
    assert best_match(Track("Song (Radio Edit)", ["DJ X"]), [Track("Song", ["DJ X"])], threshold=75) is not None
    assert best_match(Track("Live Forever", ["Oasis"]), [Track("Live Forever", ["Oasis"])], threshold=75) is not None

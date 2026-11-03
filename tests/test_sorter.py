from tunebridge import sorter


def _it(genre, sub=None, bpm=None, cam=None, e=None, conf=0.8, tags=()):
    return {"genre": genre, "subgenre": sub, "bpm": bpm, "camelot": cam, "energy": e, "confidence": conf,
            "tags": list(tags), "artist": "x", "duration_ms": 200_000}


ITEMS = [_it("Drum & Bass", "Liquid", 174, "8A", 0.5), _it("Drum & Bass", "Liquid", 172, "9A", 0.55),
         _it("Drum & Bass", "Neurofunk", 174, "8A", 0.7), _it("Drum & Bass", "Liquid", 175, "8B", 0.5), _it("Drum & Bass", None, 170, "7A", 0.6),
         _it("House", "Deep House", 122, "5A", 0.4), _it("House", "Deep House", 124, "6A", 0.45),
         _it("House", "Tech House", 126, "5A", 0.55), _it("Ambient / Chill", None, None, None, None),
         _it(None)]


def names(level, m=2):
    return [g["name"] for g in sorter.sort(ITEMS, level, m)]


def test_all_levels_keep_every_song():
    for lvl in range(1, 7):
        idx = sorted(i for g in sorter.sort(ITEMS, lvl, 2) for i in g["items"])
        assert idx == list(range(len(ITEMS))), lvl


def test_micro_falls_back_to_genre_when_group_too_small():
    n = names(6)
    assert "Drum & Bass – Liquid" in n and "House – Deep House" in n
    assert "Drum & Bass" in n                     # Neurofunk allein -> zu „Drum & Bass“ (2 Songs)
    assert "House" not in n and "Sonstiges" in n  # Tech House allein: House (1) -> Elektronisch (1) -> Sonstiges
    assert n[-1] == sorter.UNSORTED


def test_family_and_genre():
    assert set(names(4)) >= {"Elektronisch", sorter.UNSORTED}
    assert "Drum & Bass" in names(5)


def test_mixes_split_by_tempo_and_order_by_key():
    groups = sorter.sort(ITEMS, 1, 2)
    assert groups[0]["name"].startswith("Mix 1 · 122–126 BPM")
    assert groups[1]["name"].startswith("Mix 2 · 170–175 BPM")
    assert groups[-1]["name"] == "Tempo unbekannt"


def test_camelot_distance():
    from tunebridge.audiofeat import camelot_distance, fold_bpm
    assert camelot_distance("8A", "8A") == 0 and camelot_distance("8A", "9A") == 1
    assert camelot_distance("8A", "8B") == 1 and camelot_distance("12A", "1A") == 1
    assert camelot_distance("8A", "2A") == 6
    assert fold_bpm(87, "Drum & Bass") == 174 and fold_bpm(70, "Dubstep") == 140


def test_ai_review_only_accepts_known_genres(monkeypatch):
    from tunebridge import ai
    items = [{"artist": "Noisia", "title": "Stigma", "genre": "Drum & Bass", "subgenre": "Liquid"},
             {"artist": "Kordhell", "title": "Murder In My Mind", "genre": "Pop", "subgenre": None},
             {"artist": "X", "title": "Y", "genre": "House", "subgenre": None}]
    answer = ('{"fixes": [{"i": 0, "genre": "Drum & Bass", "subgenre": "Neurofunk", "grund": "bekannt"},'
              ' {"i": 1, "genre": "Phonk", "subgenre": "Drift Phonk", "grund": "Drift-Phonk-Hit"},'
              ' {"i": 2, "genre": "Vaporstep", "subgenre": null, "grund": "erfunden"},'
              ' {"i": 7, "genre": "House", "subgenre": null}]}')
    monkeypatch.setattr(ai, "settings", lambda: {**ai.DEFAULTS, "provider": "test", "use": []})  # nie die echte Datenbank lesen
    monkeypatch.setattr(ai, "voters", lambda: ["test"])
    monkeypatch.setattr(ai, "ask", lambda prompt, max_tokens=300, provider=None, wait=90: answer)
    fixes = ai.review_genres(items)
    assert [(f["i"], f["genre"], f["subgenre"]) for f in fixes] == [
        (0, "Drum & Bass", "Neurofunk"), (1, "Phonk", "Drift Phonk")]

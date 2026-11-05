"""YouTube-„Mag ich“ enthält auch Videos ohne Musik – die dürfen beim Sortieren nicht unter „Unsortiert“ landen."""
from tunebridge import services, sorter
from tunebridge.models import Track
from tunebridge.providers.youtube import NO_MUSIC, mark_non_music


def _t(vid, title="X"):
    return Track(title=title, artists=["A"], ids={"youtube": vid})


def test_mark_non_music_uses_category_and_topic_channel():
    tr = [_t("m"), _t("topic"), _t("short"), _t("weg")]
    calls = []

    def get(path, **p):
        calls.append((path, p["id"]))
        return {"items": [{"id": "m", "snippet": {"categoryId": "10"}},
                          {"id": "topic", "snippet": {"categoryId": "22", "channelTitle": "Künstler - Topic"}},
                          {"id": "short", "snippet": {"categoryId": "20"}}]}     # „weg“ fehlt (gelöscht) -> unmarkiert
    assert mark_non_music(tr, get) == 1
    assert [NO_MUSIC in t.tags for t in tr] == [False, False, True, False]
    assert calls == [("videos", "m,topic,short,weg")]


def test_mark_non_music_batches_of_50_and_survives_errors():
    tr = [_t(str(i)) for i in range(120)]
    n = []

    def get(path, **p):
        n.append(len(p["id"].split(",")))
        if len(n) == 2:
            raise RuntimeError("Kontingent")
        return {"items": [{"id": i, "snippet": {"categoryId": "24"}} for i in p["id"].split(",")]}
    assert mark_non_music(tr, get) == 50
    assert n == [50, 50]


def test_sorter_puts_videos_in_own_group_at_end():
    items = [{"title": "a", "genre": "Techno"}, {"title": "v", "nomusic": True}, {"title": "b", "genre": "Techno"},
             {"title": "c", "genre": "Techno"}, {"title": "u"}]
    for level in (1, 2, 5):
        res = sorter.sort(items, level, 1)
        assert res[-1]["name"] == sorter.NOMUSIC and res[-1]["items"] == [1]
        rest = sorted(i for g in res[:-1] for i in g["items"])
        assert rest == [0, 2, 3, 4]


def test_sort_job_skips_lookup_for_videos(monkeypatch):
    from tunebridge import linkimport
    looked = []
    monkeypatch.setattr(linkimport, "_analyse_one", lambda t: looked.append(t.title) or
                        {"title": t.title, "artist": "A", "artists": ["A"], "ids": t.ids, "genre": "Techno"})
    video = _t("v", "Short"); video.tags = {NO_MUSIC: 1.0}
    job = {"state": "queued", "done": 0, "total": 0, "items": [], "cancel": False, "name": "x",
           "preset": ("x", [_t("s", "Song"), video])}
    services._run(job)
    assert job["state"] == "done" and looked == ["Song"]
    assert job["nomusic"] == 1 and job["items"][1]["nomusic"]

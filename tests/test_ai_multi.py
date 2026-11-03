"""Mehrere KIs: Ersatz-Kette, Abstimmung und Aufräumen der Modell-Liste."""

import json

import pytest

from tunebridge import ai


def _fixes(*f):
    return json.dumps({"fixes": [{"i": i, "genre": g, "subgenre": s, "grund": "x"} for i, g, s in f]})


ITEMS = [{"artist": "Noisia", "title": "Tentacles", "genre": "Pop", "subgenre": None},
         {"artist": "Kordhell", "title": "Murder In My Mind", "genre": "Pop", "subgenre": None}]


def test_vote_needs_majority(monkeypatch):
    answers = {"gemini": _fixes((0, "Drum & Bass", "Neurofunk"), (1, "Phonk", None)),
               "claude": _fixes((0, "Drum & Bass", "Neurofunk"), (1, "Hip-Hop", None))}
    monkeypatch.setattr(ai, "voters", lambda: list(answers))
    monkeypatch.setattr(ai, "ask", lambda prompt, mt=300, p=None, wait=90: answers[p])
    monkeypatch.setattr(ai, "settings", lambda: {**ai.DEFAULTS, "use": list(answers), "provider": "gemini",
                                                  "combine": "abstimmung"})
    out = ai.review_genres(ITEMS)
    assert [(f["i"], f["genre"], f["subgenre"]) for f in out] == [(0, "Drum & Bass", "Neurofunk")]
    assert "2 von 2" in out[0]["grund"]


def test_chain_falls_back(monkeypatch):
    calls = []
    monkeypatch.setattr(ai, "settings", lambda: {**ai.DEFAULTS, "use": ["gemini", "claude"], "provider": "gemini"})
    monkeypatch.setattr(ai, "ready", lambda p=None: (True, ""))

    def fake(p, *a, **k):
        calls.append(p)
        if p == "gemini":
            raise ai.AIError("Limit")
        return "ok"
    monkeypatch.setattr(ai, "_gemini", lambda *a: fake("gemini"))
    monkeypatch.setattr(ai, "_claude", lambda *a: fake("claude"))
    assert ai.ask("frage") == "ok"
    assert calls == ["gemini", "claude"]


def test_chain_all_fail(monkeypatch):
    monkeypatch.setattr(ai, "settings", lambda: {**ai.DEFAULTS, "use": ["gemini"], "provider": "gemini"})
    monkeypatch.setattr(ai, "ready", lambda p=None: (True, ""))
    monkeypatch.setattr(ai, "_gemini", lambda *a: (_ for _ in ()).throw(ai.AIError("kaputt")))
    with pytest.raises(ai.AIError, match="kaputt"):
        ai.ask("frage")


def test_clean_models_drops_variants():
    ids = ["gemini-2.5-flash", "gemini-flash-latest", "gemini-2.5-flash-preview-tts", "gemini-3-pro-image",
           "gemini-3.8-flash", "gemini-3.1-pro-preview", "gemini-3.8-flash", "gemini-robotics-er-2-preview"]
    assert ai.clean_models("gemini", ids) == ["gemini-3.8-flash", "gemini-2.5-flash", "gemini-3.1-pro-preview"]

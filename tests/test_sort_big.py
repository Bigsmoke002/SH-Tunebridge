"""Große Bibliotheken beim Sortieren: Grenze, schlanke Fortschritts-Abfrage, lange Aufträge bleiben erhalten."""

import time

from tunebridge import scanall, services


def test_grenze_80000():
    assert scanall.MAX_TRACKS == 80000


def test_songliste_erst_wenn_fertig(monkeypatch):
    services._jobs["x"] = {"id": "x", "state": "analysing", "items": [{"title": "A"}] * 3, "cancel": False,
                           "started": time.time(), "done": 3, "total": 10}
    try:
        j = services.job("x")
        assert j["items"] == [] and j["done"] == 3
        services._jobs["x"]["state"] = "done"
        assert len(services.job("x")["items"]) == 3
    finally:
        services._jobs.pop("x", None)


def test_laufender_auftrag_wird_nicht_verworfen(monkeypatch):
    monkeypatch.setattr(services, "_run", lambda job: None)
    old = time.time() - 10 * 3600
    services._jobs["lauf"] = {"id": "lauf", "state": "analysing", "items": [], "started": old}
    services._jobs["alt"] = {"id": "alt", "state": "done", "items": [], "started": old, "finished": old + 60}
    try:
        jid = services.start("spotify", "pl")
        assert "lauf" in services._jobs and "alt" not in services._jobs
        services._jobs.pop(jid, None)
    finally:
        services._jobs.pop("lauf", None)
        services._jobs.pop("alt", None)

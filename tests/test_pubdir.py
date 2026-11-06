"""Öffentliches Playlist-Verzeichnis: Einwilligung, ausdrückliche Bestätigung, Textprüfung, nur Metadaten."""
import pytest

from tunebridge import consent, pubdir, store, upload
from tunebridge.models import Track


@pytest.fixture
def srv(monkeypatch):
    sent = []
    upload._key()                                      # Installations-Schlüssel wie nach dem ersten Senden

    def post(path, payload, timeout=20):
        sent.append((path, payload))
        if path == "/v1/pub/publish":
            return {"id": payload.get("id") or "a" * 24, "n": len(payload["tracks"])}
        if path == "/v1/pub/mine":
            return {"playlists": [{"id": "a" * 24}], "max": 20}
        if path == "/v1/pub/delete":
            return {"geloescht": 1}
        return {"gemeldet": True}
    monkeypatch.setattr(upload, "_signed_post", post)
    pubdir._cache.clear()
    return sent


def allow():
    consent.save({"privacy": True, "server": {"domain": True, "verzeichnis": True}})


def playlist(name="Meine Mischung"):
    store.add_to_playlist(name, Track(title="Song A", artists=["Künstler"], album="Album", isrc="DEABC2400001",
                                      ids={"spotify": "123abc"}, cover="https://bild.example/c.jpg", duration_ms=200000))


def test_needs_consent_and_confirm(srv):
    playlist()
    with pytest.raises(PermissionError):
        pubdir.publish("Meine Mischung", "BassKatze", confirm=True)
    allow()
    with pytest.raises(pubdir.PubError, match="bestätigen"):
        pubdir.publish("Meine Mischung", "BassKatze")
    assert not srv


def test_publish_only_metadata_and_update_same_id(srv):
    allow()
    playlist()
    r = pubdir.publish("Meine Mischung", "BassKatze", "Techno", "Für lange Nächte", confirm=True)
    path, p = srv[-1]
    assert path == "/v1/pub/publish" and "id" not in p
    t = p["tracks"][0]
    assert t["title"] == "Song A" and t["isrc"] == "DEABC2400001" and t["ids"] == {"spotify": "123abc"}
    assert not any("cover" in k for k in t)
    pubdir.publish("Meine Mischung", "BassKatze", confirm=True)
    assert srv[-1][1]["id"] == r["id"]
    assert pubdir.alias() == "BassKatze"


@pytest.mark.parametrize("text", ["Hör mal www.beispiel.de", "Schreib an a@b.de", "Ruf an +49 151 2345678", "0711 1234567", "http://x"])
def test_texts_without_contact_data(text):
    with pytest.raises(pubdir.PubError):
        pubdir.check_text(text, "Beschreibung", 0, 300)


@pytest.mark.parametrize("text", ["Best of 2010-2019", "Top 100 2024-2025", "Mr. Me & Mrs. You", "Drum & Bass 174"])
def test_normal_texts_pass(text):
    assert pubdir.check_text(text, "Name", 2, 80) == text


def test_delete_all_works_after_withdrawal(srv):
    allow()
    playlist()
    pubdir.publish("Meine Mischung", "BassKatze", confirm=True)
    consent.save({"server": {"verzeichnis": False}})
    with pytest.raises(PermissionError):
        pubdir.unpublish("a" * 24)
    assert pubdir.unpublish(all_=True)["geloescht"] == 1
    assert pubdir._map() == {}


def test_report_needs_known_reason(srv):
    allow()
    with pytest.raises(pubdir.PubError):
        pubdir.report("a" * 24, "weil")
    pubdir.report("a" * 24, "spam", "Werbung")
    assert srv[-1] == ("/v1/pub/" + "a" * 24 + "/report", {"grund": "spam", "text": "Werbung"})

"""Genre-Datenbank: eigene Einordnungen, Playlist-Namen (nur lokal), Senden nur erlaubter Felder,
Gemeinschafts-Datenbank nur mit gültiger Signatur."""
import json
import shutil
import subprocess

import pytest

from tunebridge import consent, genredb
from tunebridge.models import Track


def _allow(**server):
    consent.save({"privacy": True, "server": {"domain": True, **server}})


def test_playlist_name_genre_is_local_and_conservative():
    assert genredb.playlist_genre("Hardtekk 2024 🔥") == ("Techno", "Hardtekk")
    assert genredb.playlist_genre("DnB Liquid Mix") == ("Drum & Bass", "Liquid")
    assert genredb.playlist_genre("Gym Montag") == (None, None)
    assert genredb.playlist_genre("Rock & Techno") == (None, None)       # zwei Richtungen -> keine Aussage
    assert genredb.playlist_genre("Chill") == (None, None)               # Stimmung ist kein Genre
    assert genredb.playlist_genre("Für Lisa ❤") == (None, None)


def test_own_vote_wins_and_is_applied():
    t = Track("AGAINST", ["Kloud"], isrc="QZ1234567890", genre="Techno")
    extra = {"confidence": 0.4}
    assert not genredb.apply(t, extra)
    genredb.vote(["Kloud"], "AGAINST", "qz1234567890", "Techno", "Hardtekk", "korrektur")
    assert genredb.apply(t, extra)
    assert (t.genre, t.subgenre) == ("Techno", "Hardtekk") and extra["genre_source"] == "eigene Einordnung"
    # auch ohne ISRC über Künstler + Titel
    t2 = Track("AGAINST", ["Kloud"])
    assert genredb.apply(t2, {}) and t2.subgenre == "Hardtekk"
    with pytest.raises(ValueError):
        genredb.vote(["X"], "Y", None, "Erfundenes Genre", None, "app")


def test_upload_only_allowed_fields_and_only_after_consent(monkeypatch):
    from tunebridge import outbox, upload
    genredb.vote(["Alt"], "Vorher", None, "Techno", None, "playlist")       # vor der Einwilligung
    _allow(genres=True)
    sent = []
    monkeypatch.setattr(upload, "send", lambda pkg: sent.append(pkg) or {"angenommen": len(pkg["eintraege"])})
    genredb.vote(["Neu"], "Song", "DEX111", "Techno", "Hardtekk", "playlist")
    done = outbox.flush()
    assert done.get("genres") == 1
    e = sent[0]["eintraege"][0]
    assert set(e) == {"uid", "zeit", "art", "song", "details"} and e["art"] == "genre"
    assert e["song"] == {"artist": "Neu", "title": "Song", "isrc": "DEX111"}
    assert e["details"] == {"genre": "Techno", "subgenre": "Hardtekk", "herkunft": "playlist",
                            "schluessel": ["DEX111", "neu|song"]}
    assert "Tekk" not in json.dumps(sent)                                   # kein Playlist-Name
    assert outbox.flush().get("genres") is None                             # nichts doppelt


def test_accept_marks_changes_as_correction(monkeypatch):
    jid = "t1"
    genredb._jobs[jid] = {"items": [
        {"i": 0, "title": "A", "artists": ["X"], "isrc": None, "genre": "Techno", "subgenre": None, "source": "app"},
        {"i": 1, "title": "B", "artists": ["Y"], "isrc": None, "genre": "Techno", "subgenre": None, "source": "playlist"}],
        "started": 0}
    r = genredb.accept(jid, [{"i": 0, "genre": "Techno", "subgenre": None},
                             {"i": 1, "genre": "Techno", "subgenre": "Hardtekk"}])
    assert r["saved"] == 2
    assert genredb.own(["X"], "A")["source"] == "app"
    assert genredb.own(["Y"], "B")["source"] == "korrektur"


def test_propose_flags_conflicts():
    it = {"app_genre": "Hip-Hop", "app_subgenre": None, "confidence": 0.8, "pl_genre": "Techno", "pl_subgenre": "Hardtekk"}
    genredb._propose(it)
    assert it["genre"] == "Techno" and it["status"] == "pruefen"
    it = {"app_genre": "Techno", "app_subgenre": None, "confidence": 0.7, "pl_genre": None,
          "ki": {"genre": "Techno", "subgenre": "Hardtekk"}}
    genredb._propose(it)
    assert (it["genre"], it["subgenre"], it["status"]) == ("Techno", "Hardtekk", "ok")


def test_ai_gets_only_facts(monkeypatch):
    from tunebridge import ai
    seen = []
    monkeypatch.setattr(ai, "ask_all", lambda prompt, *a: seen.append(prompt) or
                        {"x": '{"songs": [{"i": 0, "genre": "Techno", "subgenre": "Hardtekk"}]}'})
    out = ai.judge_genres([{"artists": ["Kloud"], "title": "AGAINST", "album": "AG", "bpm": 160,
                            "app_genre": "Rock / Metal", "tags": ["deathcore"]}])
    assert out == [{"i": 0, "genre": "Techno", "subgenre": "Hardtekk", "n": 1}]
    assert "deathcore" not in seen[0] and "Rock / Metal" not in seen[0].split("Songs (")[1]


@pytest.mark.skipif(not shutil.which("ssh-keygen"), reason="ssh-keygen fehlt")
def test_community_db_only_with_valid_signature(tmp_path, monkeypatch):
    import httpx

    from tunebridge import sshsig
    key = tmp_path / "k"
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)], check=True)
    signers = f'* namespaces="{genredb.NAMESPACE}" ' + (tmp_path / "k.pub").read_text().split(" comment")[0]
    monkeypatch.setattr(genredb, "_verify", lambda d, s: sshsig.verify(d, s, signers, "sh-tunebridge", genredb.NAMESPACE))
    data = json.dumps({"format": 1, "version": 5, "songs": {"QZ1": ["Techno", "Hardtekk", 4],
                                                             "kloud|against": ["Techno", "Hardtekk", 4]}}).encode()
    (tmp_path / "db.json").write_bytes(data)
    subprocess.run(["ssh-keygen", "-q", "-Y", "sign", "-f", str(key), "-n", genredb.NAMESPACE, str(tmp_path / "db.json")],
                   check=True)
    good = (tmp_path / "db.json.sig").read_bytes()
    files = {"/v1/genredb/meta": json.dumps({"version": 5}).encode(), "/v1/genredb": data, "/v1/genredb.sig": good}

    def get(url, **k):
        path = url.split("bs002.de")[-1] if "bs002.de" in url else url[url.index("/v1"):]
        return httpx.Response(200, content=files[path], request=httpx.Request("GET", url))
    monkeypatch.setattr(httpx, "get", get)
    assert genredb.update(force=True)["ok"] is False                        # ohne Einwilligung: nichts
    assert not (genredb._path()).exists()
    _allow(genredb=True)
    files["/v1/genredb.sig"] = good.replace(b"A", b"B", 1)                  # manipuliert
    r = genredb.update(force=True)
    assert not r["ok"] and not genredb._path().exists()
    files["/v1/genredb.sig"] = good
    assert genredb.update(force=True)["updated"]
    t = Track("AGAINST", ["Kloud"])
    assert genredb.apply(t, {}) and t.subgenre == "Hardtekk"
    _allow(genredb=False)
    assert genredb.lookup(Track("AGAINST", ["Kloud"])) is None              # Erlaubnis weg -> nicht benutzt

"""Playlist-Dateien aus den Export-Funktionen der Dienste."""

import plistlib

import pytest

from tunebridge import linkimport, playlistfile


def test_apple_music_xml():
    data = plistlib.dumps({"Tracks": {"11": {"Track ID": 11, "Name": "Murder In My Mind", "Artist": "Kordhell",
                                             "Album": "Murder In My Mind", "Total Time": 142000},
                                      "12": {"Track ID": 12, "Name": "Close Eyes", "Artist": "DVRST"}},
                           "Playlists": [{"Name": "Phonk", "Playlist Items": [{"Track ID": 12}, {"Track ID": 11}]}]})
    name, tracks = playlistfile.parse("Phonk.xml", data)
    assert name == "Phonk"
    assert [(t.artists, t.title) for t in tracks] == [(["DVRST"], "Close Eyes"), (["Kordhell"], "Murder In My Mind")]
    assert tracks[1].duration_ms == 142000


def test_apple_music_txt_utf16_german_header():
    text = "Name\tInterpret\tKomponist\tAlbum\r\nSahara\tHensonn\t\tSahara\r\nWhy Not\tGhostface Playa\t\tWhy Not\r\n"
    name, tracks = playlistfile.parse("Meine Liste.txt", text.encode("utf-16"))
    assert name == "Meine Liste" and len(tracks) == 2 and tracks[0].artists == ["Hensonn"]


def test_exportify_csv():
    csv = ('"Track URI","Track Name","Artist Name(s)","Album Name","ISRC","Track Duration (ms)"\n'
           '"spotify:track:1","SICKO MODE","Travis Scott, Drake","ASTROWORLD","USSM11806889","312820"\n')
    _, tracks = playlistfile.parse("liste.csv", csv.encode())
    t = tracks[0]
    assert t.title == "SICKO MODE" and t.artists == ["Travis Scott", "Drake"] and t.isrc == "USSM11806889"
    assert t.duration_ms == 312820


def test_semicolon_csv_and_m3u():
    _, tracks = playlistfile.parse("x.csv", "Titel;Künstler\nNightcall;Kavinsky\n".encode("cp1252"))
    assert tracks[0].artists == ["Kavinsky"]
    m3u = "#EXTM3U\n#EXTINF:215,Daft Punk - One More Time\nC:\\Musik\\a.mp3\n#EXTINF:-1,Unbekannt\n"
    _, tracks = playlistfile.parse("x.m3u8", m3u.encode())
    assert (tracks[0].artists, tracks[0].title, tracks[0].duration_ms) == (["Daft Punk"], "One More Time", 215000)
    assert all("Musik" not in t.title for t in tracks)       # keine Dateipfade übernehmen


def test_takeout_video_ids(monkeypatch):
    seen = []
    monkeypatch.setattr(linkimport, "_youtube", lambda kind, vid: (seen.append(vid) or ("", [
        linkimport.Track(title="Titel " + vid, artists=["Kanal"])])))
    _, tracks = playlistfile.parse("Playlist.csv", b"Video ID,Time Added\nabcdefghijk,2024\nkaputt,2024\n")
    assert seen == ["abcdefghijk"] and tracks[0].title == "Titel abcdefghijk"


def test_bad_files():
    with pytest.raises(playlistfile.FileError):
        playlistfile.parse("x.csv", b"foo,bar\n1,2\n")
    with pytest.raises(playlistfile.FileError):
        playlistfile.parse("x.csv", b"x" * (6 * 1024 * 1024))


def test_profile_links():
    assert linkimport.parse("https://www.deezer.com/de/profile/123456") == {"service": "deezer", "kind": "profile", "id": "123456"}
    assert linkimport.parse("https://www.last.fm/user/RJ/loved") == {"service": "lastfm", "kind": "loved", "id": "RJ"}
    assert linkimport.parse("https://www.last.fm/de/user/someone")["id"] == "someone"

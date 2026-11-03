"""Datenverbrauch (Socket-Zählung, Tagessummen) und Discord Rich Presence (gegen einen falschen Discord)."""
import json
import os
import socket
import sys
import struct
import threading
import time

import pytest

from tunebridge import discord_rpc, store, traffic


@pytest.fixture(autouse=True)
def db(tmp_path, monkeypatch):
    """Nie die echte Datenbank anfassen."""
    from tunebridge import config
    monkeypatch.setattr(config, "DATA", tmp_path)
    monkeypatch.setattr(store, "DB", tmp_path / "t.db")
    store.ram_clear()
    yield store
    traffic._day_pending.clear()          # Hintergrund-Thread soll nichts Gemessenes später woanders hinschreiben
    discord_rpc.RPC.song = discord_rpc.RPC.preview = None
    store.ram_clear()


def test_group_names():
    assert traffic.group("cdn-images.dzcdn.net") == "Deezer"
    assert traffic.group("generativelanguage.googleapis.com") == "KI: Gemini"
    assert traffic.group("www.googleapis.com") == "YouTube"
    assert traffic.group("is1-ssl.mzstatic.com") == "Apple / iTunes"
    assert traffic.group("example.org") == "example.org"


def test_socket_counting(monkeypatch):
    traffic.install()
    monkeypatch.setattr(traffic, "_local", lambda ip: False)      # Testserver läuft auf 127.0.0.1
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port = srv.getsockname()[1]

    def serve():
        c, _ = srv.accept()
        c.recv(100)
        c.sendall(b"x" * 5000)
        c.close()
    threading.Thread(target=serve, daemon=True).start()
    monkeypatch.setattr(traffic, "group", lambda h: "Deezer" if h == "localhost" else (h or "x"))
    old = traffic._sess.get("Deezer", [0, 0, False])
    before = {"i": old[0], "o": old[1]}
    c = socket.create_connection(("localhost", port))
    c.sendall(b"hallo")
    got = b""
    while len(got) < 5000:
        d = c.recv(4096)
        if not d:
            break
        got += d
    c.close()
    srv.close()
    e = traffic._sess["Deezer"]
    assert e[0] - before["i"] >= 5000 and e[1] - before["o"] >= 5
    # eingehende Verbindung (Server-Seite) wurde nicht als Deezer gezählt -> genau einmal gezählt
    assert e[0] - before["i"] < 10000


def test_daily_summary_and_reset():
    traffic.reset()
    traffic.add("api.deezer.com", 1000, 200)
    traffic.add("i.scdn.co", 50_000, 0, estimated=True)
    s = traffic.summary()
    names = {r["name"]: r for r in s["rows"]["today"]}
    assert names["Deezer"]["in"] == 1000 and names["Deezer"]["out"] == 200
    assert names["Spotify"]["est"] is True
    assert s["rows"]["today"][0]["name"] == "Spotify"          # größter zuerst
    traffic.reset()
    assert traffic.summary()["rows"]["today"] == []


class FakeDiscord:
    def __init__(self, path):
        self.path, self.acts = path, []
        self.srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.srv.bind(path)
        self.srv.listen(4)
        threading.Thread(target=self.run, daemon=True).start()

    def _read(self, c, n):
        b = b""
        while len(b) < n:
            d = c.recv(n - len(b))
            if not d:
                raise ConnectionError
            b += d
        return b

    def _send(self, c, op, obj):
        raw = json.dumps(obj).encode()
        c.sendall(struct.pack("<II", op, len(raw)) + raw)

    def run(self):
        while True:
            c, _ = self.srv.accept()
            try:
                op, ln = struct.unpack("<II", self._read(c, 8))
                hello = json.loads(self._read(c, ln))
                if hello.get("client_id") != "123456789":
                    self._send(c, 2, {"code": 4000, "message": "Invalid Client ID"})
                    c.close()
                    continue
                self._send(c, 1, {"cmd": "DISPATCH", "evt": "READY", "data": {"user": {"username": "tester"}}})
                while True:
                    op, ln = struct.unpack("<II", self._read(c, 8))
                    msg = json.loads(self._read(c, ln))
                    self.acts.append(msg["args"]["activity"])
                    self._send(c, 1, {"cmd": "SET_ACTIVITY", "data": msg["args"]["activity"], "nonce": msg["nonce"]})
            except ConnectionError:
                c.close()


@pytest.mark.skipif(not hasattr(socket, "AF_UNIX") or sys.platform == "win32",
                    reason="Windows nutzt Named Pipes statt Unix-Sockets")
def test_discord_presence(tmp_path, monkeypatch):
    import tempfile
    short = tempfile.mkdtemp(prefix="tbd", dir="/tmp")          # macOS: Unix-Socket-Pfade max. 104 Zeichen
    path = os.path.join(short, "discord-ipc-0")
    fake = FakeDiscord(path)
    monkeypatch.setenv("TUNEBRIDGE_DISCORD_IPC", path)
    st = discord_rpc.save({"enabled": True, "client_id": "123456789", "idle": False})
    assert st["enabled"] and st["client_id"] == "123456789"
    discord_rpc.RPC.on_song("Deeper", ["Kanine", "Raphaella"], "https://cdn.example/x.jpg", "Drum & Bass", "Jump Up", None)
    for _ in range(50):
        if fake.acts and fake.acts[-1]:
            break
        time.sleep(0.1)
    a = fake.acts[-1]
    assert a["type"] == 2 and a["details"] == "Deeper" and a["state"] == "Kanine, Raphaella"
    assert a["assets"]["large_image"].startswith("https://") and a["assets"]["large_text"] == "Drum & Bass – Jump Up"
    assert a["buttons"][0]["label"] == "Song anhören"
    # Einstellungen greifen: ohne Cover/Genre/Knöpfe
    discord_rpc.save({"cover": False, "genre": False, "buttons": False})
    for _ in range(50):
        if fake.acts[-1] and "assets" not in fake.acts[-1] and "buttons" not in fake.acts[-1]:
            break
        time.sleep(0.1)
    assert "assets" not in fake.acts[-1] and "buttons" not in fake.acts[-1]
    # Ausschalten löscht den Status
    discord_rpc.save({"enabled": False})
    for _ in range(50):
        if fake.acts[-1] is None:
            break
        time.sleep(0.1)
    assert fake.acts[-1] is None
    assert discord_rpc.status()["state"] == "aus"


def test_discord_compose_activity_and_expiry():
    r = discord_rpc._RPC()
    cfg = {**discord_rpc.DEFAULTS, "enabled": True, "client_id": "1"}
    assert r.compose(cfg) is None
    r.on_view("playlists")
    assert r.compose(cfg)["details"] == "Sieht sich Playlists an"
    r.song = {"title": "A", "artists": ["B"], "cover": None, "genre": None, "subgenre": None, "url": None, "ts": time.time() - 3600}
    assert r.compose(cfg)["details"] == "Sieht sich Playlists an"     # Song nach keep_min abgelaufen
    assert r.compose({**cfg, "activity": False}) is None

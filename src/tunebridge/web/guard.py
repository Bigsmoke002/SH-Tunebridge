"""Schutz der lokalen App-Schnittstelle vor fremden Webseiten.

Die App lauscht auf 127.0.0.1 – erreichbar ist sie aber auch für jede Webseite, die im Browser des Nutzers
offen ist. Ohne Prüfung könnte eine Seite im Hintergrund Anfragen an die App schicken (CSRF) oder per
DNS-Rebinding (eigene Domain zeigt plötzlich auf 127.0.0.1) sogar Antworten mitlesen. Deshalb:

1. Host-Kopf muss 127.0.0.1 / localhost / ::1 sein (gegen DNS-Rebinding) – außer die Oberfläche wurde
   bewusst im Netz geöffnet (`tunebridge ui --host …`, setzt TUNEBRIDGE_OPEN_HOST).
2. Schickt der Browser einen Origin-Kopf, muss er genau die App selbst sein (gleiche Herkunft).
3. Meldet der Browser per Sec-Fetch-Site eine fremde Seite, wird abgelehnt – Ausnahmen: ein normaler
   Seitenaufruf (Weiterleitung nach einem Login bei Spotify & Co. landet als GET-Navigation hier) und der
   Player-Rahmen `/embed/player` als iframe (das Fenster auf 127.0.0.1 lädt ihn von localhost, weil YouTube
   manche Videos unter einer reinen IP-Adresse nicht einbetten lässt – der Rahmen enthält nur den offiziellen
   Player und gibt keine Daten der App heraus).

Programme ohne Browser (Begleiter, Tests) schicken weder Origin noch Sec-Fetch-* und sind nicht betroffen.
"""
from __future__ import annotations

import json
import os

LOOPBACK = {"127.0.0.1", "localhost", "::1", "[::1]"}


def _hostname(host: str) -> str:
    host = host.strip().lower()
    if host.startswith("["):                       # [::1]:8765
        return host.split("]")[0] + "]"
    return host.rsplit(":", 1)[0] if host.count(":") == 1 else host


EMBED_PATH = "/embed/player"


def check(method: str, headers: dict[str, str], ws: bool = False, path: str = "") -> str | None:
    """Gibt einen Ablehnungsgrund zurück oder None, wenn die Anfrage in Ordnung ist."""
    host = headers.get("host", "")
    if not os.environ.get("TUNEBRIDGE_OPEN_HOST") and _hostname(host) not in LOOPBACK:
        return "fremder Host"
    origin = headers.get("origin")
    if origin is not None and origin.lower() not in (f"http://{host}".lower(), f"https://{host}".lower()):
        return "fremde Herkunft"
    site = headers.get("sec-fetch-site")
    if site in ("cross-site", "same-site"):
        nav = (not ws and method == "GET" and headers.get("sec-fetch-mode") == "navigate"
               and headers.get("sec-fetch-dest", "document") == "document")
        frame = (not ws and method == "GET" and path == EMBED_PATH and headers.get("sec-fetch-mode") == "navigate"
                 and headers.get("sec-fetch-dest") == "iframe")
        if not (nav or frame):
            return "Anfrage von fremder Seite"
    return None


class GuardMiddleware:
    """Reine ASGI-Middleware – deckt HTTP und WebSockets ab."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            return await self.app(scope, receive, send)
        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}
        why = check(scope.get("method", "GET"), headers, ws=scope["type"] == "websocket", path=scope.get("path", ""))
        if why is None:
            return await self.app(scope, receive, send)
        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": 1008})
            return
        body = json.dumps({"detail": f"Abgelehnt: {why}"}).encode()
        await send({"type": "http.response.start", "status": 403,
                    "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]})
        await send({"type": "http.response.body", "body": body})

"""Rate-Limits aller Online-Dienste an einer Stelle – vorab einhalten statt erst geblockt werden.

* Jeder Dienst hat ein Budget (n Anfragen pro Zeitfenster) und einen Mindestabstand.
  Vor jeder Anfrage wird gewartet, bis wieder Budget frei ist (kurz) – oder abgebrochen (lang).
* Antwortet ein Dienst trotzdem mit „zu viele Anfragen“ (HTTP 429 o. ä.), pausiert die App
  diesen Dienst (Retry-After oder Standardpause) und zeigt das in der Oberfläche an.

Grenzen: Last.fm ≤ 5/s (API-Bedingungen), Deezer 50 pro 5 s (Doku), iTunes-Suche ~20/min (Apple).
Shazam ist inoffiziell und nennt keine Grenze – deshalb bewusst vorsichtig.
"""

from __future__ import annotations

import asyncio
import threading
import time
from collections import deque
from dataclasses import dataclass, field


class LimitReached(RuntimeError):
    def __init__(self, service: str, wait: float, why: str):
        self.service, self.wait = service, wait
        super().__init__(why)


@dataclass
class _Limit:
    label: str
    count: int            # Anfragen …
    window: float         # … pro so vielen Sekunden
    gap: float = 0.0      # Mindestabstand zwischen zwei Anfragen
    pause: float = 60.0   # Standardpause nach „zu viele Anfragen“
    hits: deque = field(default_factory=deque)
    paused_until: float = 0.0
    reason: str = ""
    blocked_total: int = 0


LIMITS: dict[str, _Limit] = {
    "shazam": _Limit("Shazam", 12, 60, gap=1.0, pause=90),
    "lastfm": _Limit("Last.fm", 4, 1, gap=0.2, pause=60),
    "deezer": _Limit("Deezer", 40, 5, pause=10),
    "itunes": _Limit("iTunes-Suche", 18, 60, gap=0.5, pause=120),
    "musicbrainz": _Limit("MusicBrainz", 1, 1.1, gap=1.1, pause=10),
    "audd": _Limit("AudD", 10, 60, gap=1.0, pause=120),
    "acrcloud": _Limit("ACRCloud", 10, 60, gap=1.0, pause=120),
}
_lock = threading.Lock()


def _delay(lim: _Limit, now: float) -> float:
    """Wartezeit bis zur nächsten erlaubten Anfrage (0 = sofort)."""
    if lim.paused_until > now:
        return lim.paused_until - now
    while lim.hits and now - lim.hits[0] >= lim.window:
        lim.hits.popleft()
    d = 0.0
    if len(lim.hits) >= lim.count:
        d = lim.hits[0] + lim.window - now
    if lim.hits and lim.gap:
        d = max(d, lim.hits[-1] + lim.gap - now)
    return max(0.0, d)


def _reserve(name: str, max_wait: float) -> float:
    lim = LIMITS[name]
    with _lock:
        now = time.time()
        d = _delay(lim, now)
        if lim.paused_until > now:
            raise LimitReached(name, d, f"{lim.label}: Limit erreicht – Pause noch {round(d)} s")
        if d > max_wait:
            raise LimitReached(name, d, f"{lim.label}: zu viele Anfragen – nächste in {round(d)} s möglich")
        lim.hits.append(now + d)   # Platz reservieren
        return d


def wait_sync(name: str, max_wait: float = 10.0) -> None:
    d = _reserve(name, max_wait)
    if d:
        time.sleep(d)


async def wait_async(name: str, max_wait: float = 10.0) -> None:
    d = _reserve(name, max_wait)
    if d:
        await asyncio.sleep(d)


def blocked(name: str, retry_after: float | None = None, why: str = "zu viele Anfragen") -> float:
    """Dienst hat geblockt -> Pause setzen. Gibt die Pause in Sekunden zurück."""
    lim = LIMITS[name]
    pause = retry_after if retry_after and 0 < retry_after < 3600 else lim.pause
    with _lock:
        lim.paused_until = max(lim.paused_until, time.time() + pause)
        lim.reason = why
        lim.blocked_total += 1
    try:
        from . import debuglog as dbg
        dbg.problem("limit", f"{lim.label} blockt ({why}) – Pause {round(pause)} s")
    except Exception:
        pass
    return pause


def paused(name: str) -> float:
    lim = LIMITS[name]
    return max(0.0, lim.paused_until - time.time())


def free(name: str) -> int:
    """Wie viele Anfragen gerade ohne Warten möglich sind."""
    lim = LIMITS[name]
    with _lock:
        now = time.time()
        if lim.paused_until > now:
            return 0
        _delay(lim, now)
        return max(0, lim.count - len(lim.hits))


def state() -> list[dict]:
    now = time.time()
    out = []
    with _lock:
        for k, lim in LIMITS.items():
            _delay(lim, now)
            out.append({"id": k, "label": lim.label, "paused": round(max(0.0, lim.paused_until - now)),
                        "reason": lim.reason if lim.paused_until > now else "",
                        "used": len(lim.hits), "limit": lim.count, "window": lim.window})
    return out


def retry_after(headers) -> float | None:
    try:
        return float(headers.get("retry-after")) if headers.get("retry-after") else None
    except (TypeError, ValueError):
        return None


def httpx_hooks(name: str, max_wait: float = 10.0) -> dict:
    """event_hooks für einen httpx.Client: vor jeder Anfrage warten, 429 erkennen."""
    def before(request):
        wait_sync(name, max_wait)

    def after(response):
        if response.status_code == 429:
            blocked(name, retry_after(response.headers), "HTTP 429")
    return {"request": [before], "response": [after]}

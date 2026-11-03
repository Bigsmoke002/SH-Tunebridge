"""Dauer-Modus: warten, solange derselbe Song läuft – ohne Online-Abfragen.

Nach einer Erkennung weiß die App ungefähr, wie lange der Song noch läuft. Statt alle paar
Sekunden erneut Shazam zu fragen, horcht sie bis dahin nur lokal mit und prüft sofort neu, wenn:
* der Player (MPRIS) einen anderen Titel meldet,
* Stille kommt (Pause / Lücke zwischen zwei Songs),
* sich der Klang deutlich und anhaltend ändert (anderer Song, Crossfade),
* oder die erwartete Restzeit abgelaufen ist.

Der Ton wird dabei nur im Arbeitsspeicher ausgewertet (Pegel + 32 Frequenzbänder), nichts
wird gespeichert oder gesendet.
"""

from __future__ import annotations

import asyncio
import time

import numpy as np

from . import meter, players

SILENCE_DB = -50.0
SILENCE_S = 1.2
MIN_HOLD_S = 6.0          # Klangwechsel erst nach so vielen Sekunden werten (Profil aufbauen)
CHANGE_CORR = 0.55        # Klangbild-Ähnlichkeit darunter = anders
CHANGE_S = 3              # … so viele Sekunden am Stück
LEVEL_JUMP_DB = 14.0


def _corr(a: np.ndarray, b: np.ndarray) -> float:
    a, b = a - a.mean(), b - b.mean()
    d = float(np.linalg.norm(a) * np.linalg.norm(b))
    return float(a @ b / d) if d > 1e-9 else 1.0


async def watch(source: str, max_s: float):
    """Async-Generator: jede Sekunde {left}, am Ende {done: True, why}."""
    t0 = time.time()
    from .. import consent
    use_player = consent.local("player")
    sig0 = await asyncio.to_thread(players.signature) if use_player else ""
    profile: np.ndarray | None = None
    prof_db: float | None = None
    quiet = 0.0
    odd = 0
    sec_bands: list[np.ndarray] = []
    sec_db: list[float] = []
    last_tick = t0
    gen = meter.levels(source)
    try:
        async for fr in gen:
            now = time.time()
            if fr["rms"] < SILENCE_DB:
                quiet += 1 / meter.FPS
                if quiet >= SILENCE_S and now - t0 > 2:
                    yield {"done": True, "why": "stille"}
                    return
            else:
                quiet = 0.0
            sec_bands.append(np.array(fr["bands"], dtype=np.float32))
            sec_db.append(fr["rms"])
            if now - last_tick < 1.0:
                continue
            # ---- einmal pro Sekunde auswerten
            last_tick = now
            vec, db = np.mean(sec_bands, 0), float(np.mean(sec_db))
            sec_bands, sec_db = [], []
            held = now - t0
            if held >= max_s:
                yield {"done": True, "why": "zeit"}
                return
            sig = await asyncio.to_thread(players.signature) if use_player else ""
            if sig != sig0 and sig0 and sig:
                yield {"done": True, "why": "player"}
                return
            if db > SILENCE_DB:
                if profile is None:
                    profile, prof_db = vec, db
                else:
                    c = _corr(vec, profile)
                    jump = abs(db - prof_db) >= LEVEL_JUMP_DB
                    odd = odd + 1 if (c < CHANGE_CORR or jump) and held >= MIN_HOLD_S else 0
                    if odd >= CHANGE_S:
                        yield {"done": True, "why": "klang"}
                        return
                    if c >= CHANGE_CORR:            # Profil langsam mitziehen (Strophe/Refrain)
                        profile = profile * 0.9 + vec * 0.1
                        prof_db = prof_db * 0.9 + db * 0.1
            yield {"left": round(max_s - held)}
    finally:
        await gen.aclose()

"""Slowed-/Sped-up-Versionen erkennen.

Problem: „Slowed + Reverb“-Uploads sind meist einfach langsamer abgespielt (Tempo *und* Tonhöhe
sinken). Der Shazam-Fingerabdruck passt dann nicht mehr – oder schlimmer: er passt zufällig auf
einen *falschen* Song.

Lösung: Die Aufnahme lokal auf typische Tempi zurückrechnen (z. B. ×1,18 für 85 %-Slowed)
und erneut einen Fingerabdruck an Shazam schicken. Weil dabei auch Zufallstreffer vorkommen,
zählt ein Ergebnis nur, wenn **zwei verschiedene Tempi denselben Song** liefern.

Datenschutz: Es geht wie sonst auch nur der lokal berechnete Fingerabdruck an Shazam,
kein hörbares Audio. Die umgerechneten Dateien werden sofort wieder gelöscht.
"""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

from .. import debuglog as dbg
from .engines import Recognition, ShazamBusy, shazam
from .. import osutil

# Faktor, mit dem die Aufnahme beschleunigt wird (>1 = war slowed, <1 = war sped up/nightcore),
# sortiert nach Häufigkeit. Benachbarte Werte liegen eng genug, dass ein echter Treffer
# meist bei zwei von ihnen auftaucht.
FACTORS = (1.18, 0.85, 1.11, 0.8, 1.25, 0.9, 1.33, 0.75, 1.43)
#          slowed ↑   sped up / nightcore ↓ (Original = Aufnahme langsamer abspielen)   super slowed: 1.43
TRUSTED_SKEW = 0.005   # Shazam-Treffer mit so wenig Tempo-Abweichung sind sicher die gespielte Aufnahme


def suspicious(rec: Recognition | None) -> bool:
    """Nichts gefunden – oder ein Shazam-Treffer, der nur mit Tempo-Abweichung passt."""
    if rec is None:
        return True
    return rec.engine == "shazam" and rec.skew is not None and rec.skew > TRUSTED_SKEW


def _load(path: Path) -> tuple[np.ndarray, int, int]:
    with wave.open(str(path)) as w:
        ch, rate = w.getnchannels(), w.getframerate()
        data = np.frombuffer(w.readframes(w.getnframes()), "<i2").astype(np.float32)
    return data.reshape(-1, ch), ch, rate


def _write_speed(x: np.ndarray, ch: int, rate: int, factor: float) -> Path:
    """Wie schneller/langsamer abspielen (Tempo + Tonhöhe zusammen, wie bei Slowed-Uploads)."""
    n = x.shape[0]
    idx = np.arange(0, n - 1, factor)
    y = np.stack([np.interp(idx, np.arange(n), x[:, c]) for c in range(ch)], 1)
    out = osutil.tmpfile(prefix="tunebridge-v-", suffix=".wav")
    with wave.open(str(out), "wb") as w:
        w.setnchannels(ch)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(np.clip(y, -32768, 32767).astype("<i2").tobytes())
    return out


LAST_SEEN: list[str] = []   # Einzeltreffer der letzten Suche (für die Liste „Nicht erkannt“)
BUDGET = 25.0   # Sekunden für die ganze Suche – danach lieber „nichts erkannt“ als ewig laden
MAX_TRIES = 3   # höchstens so viele zusätzliche Shazam-Anfragen pro Scan (die häufigsten Tempi zuerst)
RESERVE = 5     # so viele Shazam-Anfragen pro Minute bleiben immer für normale Scans frei
PAUSE = 2.5     # Sekunden zwischen den Versuchen – schnelle Serien lösen bei Shazam eher eine Sperre aus


def tries_allowed(free: int) -> int:
    """Wie viele Tempo-Versuche jetzt drin sind, ohne den nächsten Scan zu blockieren (0 = gar keine)."""
    return max(0, min(MAX_TRIES, free - RESERVE))


async def find(path: Path, max_tries: int = len(FACTORS), budget: float = BUDGET) -> Recognition | None:
    """-> Original-Song (mit .speed = Tempo der Aufnahme relativ zum Original) oder None."""
    import asyncio
    import time

    x, ch, rate = await asyncio.to_thread(_load, path)
    if x.shape[0] < rate * 4:
        return None
    t0 = time.time()
    seen: list[tuple[float, Recognition]] = []
    LAST_SEEN.clear()
    for i, f in enumerate(FACTORS[:max_tries]):
        if i:
            await asyncio.sleep(PAUSE)
        if time.time() - t0 > budget:
            dbg.problem("tempo", f"Zeitbudget ({budget:.0f} s) aufgebraucht – Suche beendet", versuche=len(seen))
            break
        tmp = await asyncio.to_thread(_write_speed, x, ch, rate, f)
        try:
            rec = await shazam(tmp)
        except ShazamBusy as e:
            dbg.problem("tempo", f"Abbruch: {e}")
            tmp.unlink(missing_ok=True)
            break
        except Exception as e:
            dbg.error("tempo", f"Shazam-Fehler bei Faktor {f}", e)
            rec = None
        finally:
            tmp.unlink(missing_ok=True)
        dbg.event("tempo", f"Faktor {f}", treffer=rec and f"{', '.join(rec.artists)} – {rec.title} (skew {rec.skew})")
        if not rec:
            continue
        for f2, other in seen:
            if rec.same_song(other):
                best, bf = (rec, f) if (rec.skew or 1) <= (other.skew or 1) else (other, f2)
                best.speed = round(1 / bf, 2)
                return best
        rec.engine = "shazam"
        seen.append((f, rec))
        LAST_SEEN.append(f"×{f}: {', '.join(rec.artists)} – {rec.title}")
    dbg.problem("tempo", "Keine zwei Tempi einig – kein sicherer Treffer", versuche=[f"{f}: {r.title}" for f, r in seen])
    return None

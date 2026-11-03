"""Lokaler Wiedererkenner – bekannte Songs ohne Shazam-Anfrage erkennen.

Prinzip (wie bei Shazam, nur klein und auf deinem Rechner):
1. Spektrogramm der Aufnahme berechnen, darin markante Spitzen (Frequenz/Zeit) suchen.
2. Je zwei nahe Spitzen ergeben einen Hash (Frequenz 1, Frequenz 2, Zeitabstand).
3. Nach einer erfolgreichen Online-Erkennung werden diese Hashes zum Song gespeichert.
4. Eine neue Aufnahme wird zuerst lokal verglichen. Liegen genug Hashes desselben Songs im
   gleichen zeitlichen Abstand, ist es dieser Song -> keine Online-Anfrage nötig.

Aus den Hashes lässt sich kein Ton zurückgewinnen. Sie bleiben in der lokalen Datenbank.
Funktioniert nur für Stellen, die schon einmal aufgenommen wurden – je öfter ein Song
läuft, desto mehr davon kennt die App.
"""

from __future__ import annotations

import wave
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from .. import debuglog as dbg
from .. import store

RATE = 11025
N_FFT = 1024
HOP = 256                      # ~23 ms pro Frame
FPS = RATE / HOP
NEIGH_T, NEIGH_F = 10, 12      # Nachbarschaft für Spitzen (Frames, Bins)
PEAKS_PER_SEC = 30
FAN_OUT = 6                    # Partner je Spitze
DT_MIN, DT_MAX = 2, 60         # Zeitabstand der Paare in Frames
# Ein Treffer braucht: genug passende Hashes im gleichen Zeitversatz, deutlich vor dem Zweitbesten
MIN_ALIGNED = 30
MIN_RATIO = 0.06
MIN_LEAD = 3.0


def _load(path: Path) -> np.ndarray:
    with wave.open(str(path)) as w:
        ch, rate = w.getnchannels(), w.getframerate()
        x = np.frombuffer(w.readframes(w.getnframes()), "<i2").astype(np.float32) / 32768.0
    x = x.reshape(-1, ch).mean(1)
    # einfacher Tiefpass + Verkleinern auf 11 kHz
    step = max(1, round(rate / RATE))
    if step > 1:
        k = np.ones(step, dtype=np.float32) / step
        x = np.convolve(x, k, mode="same")[::step]
    return x


def _peaks(x: np.ndarray) -> list[tuple[int, int]]:
    if x.size < N_FFT * 4:
        return []
    from numpy.lib.stride_tricks import sliding_window_view as swv
    frames = swv(x, N_FFT)[::HOP] * np.hanning(N_FFT).astype(np.float32)
    S = np.log1p(np.abs(np.fft.rfft(frames, axis=1)) * 100).astype(np.float32)   # [Zeit, Frequenz]
    S[:, :4] = 0                                             # Gleichanteil/Brummen raus
    # lokales Maximum in einer Nachbarschaft (2D-Max über Fenster)
    pad = np.pad(S, ((NEIGH_T, NEIGH_T), (NEIGH_F, NEIGH_F)), constant_values=-1)
    mx = swv(swv(pad, 2 * NEIGH_F + 1, axis=1).max(-1), 2 * NEIGH_T + 1, axis=0).max(-1)
    cand = (S == mx) & (S > S.mean() + S.std() * 0.5)
    ts, fs = np.nonzero(cand)
    if not ts.size:
        return []
    # nur die stärksten Spitzen – global ausgewählt, damit die Auswahl nicht davon abhängt,
    # wo genau die Aufnahme beginnt
    strength = S[ts, fs]
    n_keep = int(PEAKS_PER_SEC * S.shape[0] / FPS)
    keep = np.argsort(-strength)[:n_keep]
    keep = sorted(keep, key=lambda i: (ts[i], fs[i]))
    return [(int(ts[i]), int(fs[i])) for i in keep]


def fingerprint(path: Path) -> list[tuple[int, int]]:
    """-> [(hash, zeit_frame)]"""
    pk = _peaks(_load(path))
    out = []
    for i, (t1, f1) in enumerate(pk):
        n = 0
        for t2, f2 in pk[i + 1:]:
            dt = t2 - t1
            if dt < DT_MIN:
                continue
            if dt > DT_MAX or n >= FAN_OUT:
                break
            out.append(((f1 & 0x3FF) << 16 | (f2 & 0x3FF) << 6 | (dt & 0x3F), t1))
            n += 1
    return out


def match(hashes: list[tuple[int, int]]) -> dict | None:
    """Lokale Datenbank durchsuchen -> {ref, aligned, ratio, lead, pos_frames} oder None."""
    if len(hashes) < 50:
        return None
    by_hash: dict[int, list[int]] = defaultdict(list)
    for h, t in hashes:
        by_hash[h].append(t)
    rows = store.fp_lookup(list(by_hash))
    if not rows:
        return None
    votes: dict[str, Counter] = defaultdict(Counter)
    for h, ref, t_db in rows:
        for t_q in by_hash[h]:
            votes[ref][t_db - t_q] += 1
    def best_bin(c: Counter) -> tuple[int, int]:
        # Nachbar-Frames zusammenzählen: Aufnahmen beginnen selten exakt auf derselben Frame-Grenze
        return max(((c[d] + c[d + 1], d) for d in c), default=(0, 0))
    ranked = sorted(((*best_bin(c), ref) for ref, c in votes.items()), reverse=True)
    ranked = [(n, ref, d) for n, d, ref in ranked]
    best, ref, delta = ranked[0]
    second = ranked[1][0] if len(ranked) > 1 else 0
    res = {"ref": ref, "aligned": best, "ratio": round(best / len(hashes), 3),
           "lead": round(best / max(second, 1), 1), "pos_frames": delta}
    ok = best >= MIN_ALIGNED and res["ratio"] >= MIN_RATIO and res["lead"] >= MIN_LEAD
    dbg.event("lokal", "Fingerabdruck-Vergleich", treffer=ok, **res, zweit=second, hashes=len(hashes))
    return res if ok else None


def ref_for(song_key: str, speed: float | None) -> str:
    return f"{song_key}@{round(speed or 1.0, 2)}"


def parse_ref(ref: str) -> tuple[str, float]:
    key, _, sp = ref.rpartition("@")
    try:
        return key, float(sp)
    except ValueError:
        return ref, 1.0


def remember(song_key: str, speed: float | None, hashes: list[tuple[int, int]], offset_s: float | None) -> None:
    """Hashes einer erkannten Aufnahme merken. Mit bekannter Song-Position werden sie auf die
    Song-Zeitachse gelegt – dann passen auch Aufnahmen verschiedener Durchläufe zusammen."""
    shift = round(offset_s * FPS) if offset_s else 0
    store.fp_add(ref_for(song_key, speed), [(h, t + shift) for h, t in hashes])

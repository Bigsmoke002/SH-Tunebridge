"""Tempo (BPM), Tonart (Camelot) und Energie aus der offiziellen 30-s-Hörprobe – lokal berechnet.

Warum selbst: Spotify hat „audio-features“ für neue Apps abgeschaltet (Nov. 2024), Deezer liefert BPM nur
manchmal und keine Tonart. Die Hörprobe wird nur im Arbeitsspeicher dekodiert (miniaudio, MIT) und sofort
verworfen; gespeichert werden nur die drei Zahlen (pro Song einmal, im Zwischenspeicher).
"""

from __future__ import annotations

import numpy as np

from . import debuglog as dbg
from . import store
from .models import Track

SR = 22050
N_FFT = 2048
HOP = 512
_TTL = 180 * 86400

NOTES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
# Albrecht-Shanahan-Profile (Dur / Moll) – im eigenen Test mit 30-s-Hörproben am besten (vor Krumhansl, Temperley, EDMA)
_MAJOR = np.array([0.238, 0.006, 0.111, 0.006, 0.137, 0.094, 0.016, 0.214, 0.009, 0.080, 0.008, 0.081])
_MINOR = np.array([0.220, 0.006, 0.104, 0.123, 0.019, 0.103, 0.012, 0.214, 0.062, 0.022, 0.061, 0.052])
# Camelot-Rad: Tonika -> Nummer (B = Dur, A = Moll)
_CAMELOT_MAJOR = {"B": 1, "F#": 2, "C#": 3, "G#": 4, "D#": 5, "A#": 6, "F": 7, "C": 8, "G": 9, "D": 10, "A": 11, "E": 12}
_CAMELOT_MINOR = {"G#": 1, "D#": 2, "A#": 3, "F": 4, "C": 5, "G": 6, "D": 7, "A": 8, "E": 9, "B": 10, "F#": 11, "C#": 12}

# typische Tempobereiche -> halbe/doppelte Tempo-Fehler korrigieren (häufigster Fehler jeder Beat-Erkennung)
GENRE_BPM = {
    "Drum & Bass": (160, 182), "Breakcore": (150, 200), "Dubstep": (135, 152), "Hardstyle / Hardcore": (145, 220),
    "House": (115, 132), "Techno": (120, 150), "Trance": (125, 145), "UK Garage / Bass": (125, 142),
    "Phonk": (95, 170), "Hip-Hop": (60, 170), "Trap / Future Bass": (130, 160), "Synthwave": (80, 130),
    "Ambient / Chill": (60, 130), "Reggae / Dancehall": (60, 110), "Latin": (85, 105),
}


def decode(data: bytes) -> np.ndarray:
    import miniaudio
    snd = miniaudio.decode(data, output_format=miniaudio.SampleFormat.FLOAT32, nchannels=1, sample_rate=SR)
    return np.asarray(snd.samples, dtype=np.float32)


def _stft_mag(y: np.ndarray) -> np.ndarray:
    if len(y) < N_FFT * 4:
        raise ValueError("Hörprobe zu kurz")
    win = np.hanning(N_FFT).astype(np.float32)
    n = 1 + (len(y) - N_FFT) // HOP
    idx = np.arange(N_FFT)[None, :] + HOP * np.arange(n)[:, None]
    return np.abs(np.fft.rfft(y[idx] * win, axis=1))          # (frames, bins)


def _tempo(mag: np.ndarray) -> tuple[float, float]:
    """-> (BPM, Sicherheit 0..1) aus Autokorrelation der Onset-Kurve (spektraler Fluss)."""
    logm = np.log1p(100 * mag)
    flux = np.maximum(0, np.diff(logm, axis=0)).sum(axis=1)
    k = 16
    flux = flux - np.convolve(flux, np.ones(k) / k, mode="same")
    flux = np.maximum(flux, 0)
    if not flux.any():
        return 0.0, 0.0
    ac = np.correlate(flux, flux, mode="full")[len(flux) - 1:]
    ac /= ac[0] + 1e-9
    fps = SR / HOP
    lags = np.arange(len(ac))
    bpm = np.where(lags > 0, 60 * fps / np.maximum(lags, 1), 0)
    ok = (bpm >= 60) & (bpm <= 200)
    # leichte Bevorzugung um 120 BPM (log-normal), damit nicht zufällig das halbe Tempo gewinnt
    prior = np.exp(-0.5 * (np.log2(np.maximum(bpm, 1) / 120) / 0.9) ** 2)
    score = np.where(ok, ac * prior, -1)
    lag = int(np.argmax(score))
    # Feinjustierung per Parabel
    if 1 <= lag < len(ac) - 1:
        a, b, c = ac[lag - 1], ac[lag], ac[lag + 1]
        d = (a - c) / (2 * (a - 2 * b + c) + 1e-9)
        lag_f = lag + float(np.clip(d, -0.5, 0.5))
    else:
        lag_f = float(lag)
    conf = float(np.clip((ac[lag] - np.median(ac[ok])) / (1 - np.median(ac[ok]) + 1e-9), 0, 1))
    return 60 * fps / lag_f, conf


def fold_bpm(bpm: float, genre: str | None) -> float:
    """Halbes/doppeltes Tempo in den typischen Bereich des Genres schieben (DnB 87 -> 174)."""
    if not bpm or genre not in GENRE_BPM:
        return bpm
    lo, hi = GENRE_BPM[genre]
    for f in (1, 2, 0.5, 1.5, 2 / 3):
        if lo <= bpm * f <= hi:
            return bpm * f
    return bpm


def _chroma(y: np.ndarray) -> np.ndarray:
    """Tonklassen-Profil (12 Werte). Große FFT (≈2,7 Hz Auflösung), damit auch tiefe Töne sauber zugeordnet
    werden; jede Tonklasse durch ihre Bin-Zahl geteilt (sonst bevorzugt das Raster einzelne Töne) und jeder
    Frame einzeln normiert (laute Drops dominieren sonst)."""
    n, hop = 8192, 2048
    if len(y) < n * 2:
        return np.zeros(12)
    win = np.hanning(n).astype(np.float32)
    frames = 1 + (len(y) - n) // hop
    idx = np.arange(n)[None, :] + hop * np.arange(frames)[:, None]
    mag = np.abs(np.fft.rfft(y[idx] * win, axis=1))
    freqs = np.fft.rfftfreq(n, 1 / SR)
    sel = (freqs >= 65) & (freqs <= 2100)
    mag = mag[:, sel]
    # Harmonisch/Perkussiv trennen (Median über Zeit vs. über Frequenz) – Schlagzeug verfälscht sonst die Tonart
    w = 9
    padt = np.pad(mag, ((w // 2, w // 2), (0, 0)), mode="edge")
    harm = np.median(np.lib.stride_tricks.sliding_window_view(padt, w, axis=0), axis=-1)
    padf = np.pad(mag, ((0, 0), (w // 2, w // 2)), mode="edge")
    perc = np.median(np.lib.stride_tricks.sliding_window_view(padf, w, axis=1), axis=-1)
    mag = mag * (harm ** 2 / (harm ** 2 + perc ** 2 + 1e-12))
    semis = 12 * np.log2(freqs[sel] / 440.0) + 9
    near = np.abs(semis - np.round(semis)) < 0.35          # nur Bins nahe an einem Halbton
    pc = (np.round(semis[near]).astype(int)) % 12
    m = np.log1p(mag[:, near] * 10)
    per_frame = np.stack([np.bincount(pc, weights=row, minlength=12) for row in m])
    per_frame /= np.maximum(np.bincount(pc, minlength=12), 1)
    per_frame /= per_frame.max(axis=1, keepdims=True) + 1e-9
    return per_frame.mean(axis=0)


def _key(y: np.ndarray) -> tuple[str, str, float]:
    """-> (z. B. 'A Moll', Camelot '8A', Sicherheit) über Chroma + Krumhansl-Profile."""
    chroma = _chroma(y)
    if not chroma.any():
        return "", "", 0.0
    chroma = chroma - chroma.min()
    best = (-2.0, 0, "maj")
    scores = []
    for r in range(12):
        for mode, prof in (("maj", _MAJOR), ("min", _MINOR)):
            s = float(np.corrcoef(chroma, np.roll(prof, r))[0, 1])
            scores.append(s)
            if s > best[0]:
                best = (s, r, mode)
    s, r, mode = best
    second = sorted(scores)[-2]
    note = NOTES[r]
    cam = (f"{_CAMELOT_MAJOR[note]}B" if mode == "maj" else f"{_CAMELOT_MINOR[note]}A")
    return f"{note} {'Dur' if mode == 'maj' else 'Moll'}", cam, round(max(0.0, s - second) * 5, 2)


def _energy(y: np.ndarray, mag: np.ndarray, bpm: float) -> float:
    """0..1 aus Lautheit, Anschlagdichte, Helligkeit und Tempo (grob wie Spotifys „energy“)."""
    frames = y[: len(y) // HOP * HOP].reshape(-1, HOP) if len(y) >= HOP else y.reshape(1, -1)
    rms = np.sqrt(np.mean(frames ** 2, axis=1) + 1e-12)
    loud = 20 * np.log10(np.mean(rms) + 1e-9)                       # dBFS, typ. -30 … -6
    loud_n = np.clip((loud + 30) / 24, 0, 1)
    logm = np.log1p(100 * mag)
    flux = np.maximum(0, np.diff(logm, axis=0)).mean()
    flux_n = np.clip((flux - 20) / 60, 0, 1)
    freqs = np.fft.rfftfreq(N_FFT, 1 / SR)
    cent = float((mag * freqs).sum() / (mag.sum() + 1e-9))
    bright_n = np.clip((cent - 800) / 2700, 0, 1)
    tempo_n = np.clip((bpm - 70) / 110, 0, 1) if bpm else 0.5
    return round(float(0.4 * loud_n + 0.3 * flux_n + 0.15 * bright_n + 0.15 * tempo_n), 2)


def analyse(data: bytes, genre: str | None = None) -> dict:
    y = decode(data)
    y = y - y.mean()
    mag = _stft_mag(y)
    bpm, bconf = _tempo(mag)
    bpm = fold_bpm(bpm, genre)
    key, cam, kconf = _key(y)
    return {"bpm": round(bpm, 1) if bpm else None, "bpm_conf": round(bconf, 2), "key": key or None,
            "camelot": cam or None, "key_conf": kconf, "energy": _energy(y, mag, bpm)}


def features(t: Track, deezer_bpm: float | None = None, refresh: bool = False) -> dict | None:
    """Tempo/Tonart/Energie für einen Song – aus dem Speicher oder aus der Deezer-Hörprobe. None = keine Hörprobe."""
    key = store.track_key(t)
    if not refresh and (hit := store.cache_get("audiofeat", key, max_age=_TTL)) is not None:
        return hit or None
    from . import preview
    data = None
    for url in ([t.preview_url] if t.preview_url and "dzcdn" in (t.preview_url or "") else []) + \
            preview._fresh_deezer_urls(t.isrc, t.ids.get("deezer"), t.artist, t.title):
        if (data := preview._download(url)):
            break
    if not data:
        store.cache_set("audiofeat", key, {})
        return None
    try:
        f = analyse(data, t.genre)
    except Exception as e:  # noqa: BLE001 – kaputte Datei darf nichts abbrechen
        dbg.error("audio", "Hörprobe nicht auswertbar", e, song=f"{t.artist} – {t.title}")
        return None
    if deezer_bpm and deezer_bpm > 40:      # Deezers BPM (vom Label) ist genauer als 30 s Analyse
        f["bpm"], f["bpm_conf"] = round(fold_bpm(float(deezer_bpm), t.genre), 1), 1.0
    store.cache_set("audiofeat", key, f)
    return f


def camelot_distance(a: str | None, b: str | None) -> int:
    """0 = gleich, 1 = Nachbar (±1 oder Dur/Moll-Wechsel) … 6 = Gegenpol. Unbekannt -> 3."""
    if not a or not b:
        return 3
    na, ma, nb, mb = int(a[:-1]), a[-1], int(b[:-1]), b[-1]
    d = min((na - nb) % 12, (nb - na) % 12)
    return d + (0 if ma == mb else 1) if d else (0 if ma == mb else 1)

"""Lauf-Wellenform: Bass/Mitten/Höhen werden sauber getrennt, Stille bleibt flach."""
import numpy as np

from tunebridge.recognize import meter as m


def _sine(f, a=0.8):
    t = np.arange(m.FFT_N) / m.RATE
    return (a * np.sin(2 * np.pi * f * t)).astype(np.float32)


def test_bands_are_separated():
    for f, idx in ((60, 0), (1000, 1), (6000, 2)):
        cols = m.wave_cols(_sine(f), m.CHUNK)
        assert len(cols) == m.WAVE_SUB
        c = cols[-1]
        assert c[idx] > 0.6 and all(c[j] < 0.05 for j in range(3) if j != idx), (f, c)


def test_silence_and_amplitude():
    assert m.wave_cols(np.zeros(m.FFT_N, np.float32), m.CHUNK) == [[0.0, 0.0, 0.0]] * m.WAVE_SUB
    loud, quiet = m.wave_cols(_sine(120, .8), m.CHUNK)[-1][0], m.wave_cols(_sine(120, .2), m.CHUNK)[-1][0]
    assert 3 < loud / quiet < 5                                  # linear wie am DJ-Player

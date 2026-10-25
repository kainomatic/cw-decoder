"""Testmatrix: erzeugt Signale mit verschiedenen Störungen und misst die
Decodier-Genauigkeit. Aufruf: python tests/run_matrix.py [--verbose]
"""
import sys
import os
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from cwdecoder import utf8_console  # noqa: E402
from cwdecoder.gen import render  # noqa: E402
from cwdecoder.decode_wav import decode_signal, similarity  # noqa: E402

TEXT = "CQ TEST DE DL1ABC DL1ABC K"
TEXT2 = "UR RST 599 599 TU 73 DE OK1XYZ <SK>"

CASES = [
    # name, text, kwargs
    ("sauber 20 WPM", TEXT, dict(wpm=20, snr_db=30)),
    ("sauber 35 WPM", TEXT, dict(wpm=35, snr_db=30)),
    ("sauber 12 WPM", TEXT, dict(wpm=12, snr_db=30)),
    ("45 WPM", TEXT, dict(wpm=45, snr_db=25)),
    ("Farnsworth 15/8", TEXT, dict(wpm=15, farnsworth_wpm=8, snr_db=25)),
    ("Pitch 450 Hz", TEXT, dict(wpm=25, pitch=450, snr_db=20)),
    ("Pitch 1000 Hz", TEXT, dict(wpm=25, pitch=1000, snr_db=20)),
    ("Drift ±80 Hz", TEXT, dict(wpm=25, drift_hz=80, snr_db=20)),
    ("SNR 10 dB", TEXT, dict(wpm=25, snr_db=10)),
    ("SNR 6 dB", TEXT, dict(wpm=25, snr_db=6)),
    ("SNR 3 dB", TEXT, dict(wpm=25, snr_db=3)),
    ("SNR 0 dB", TEXT, dict(wpm=20, snr_db=0)),
    ("SNR -3 dB", TEXT, dict(wpm=20, snr_db=-3)),
    ("QSB 0.3 Hz tief", TEXT, dict(wpm=25, snr_db=15, qsb_hz=0.3, qsb_depth=0.9)),
    ("QSB + SNR 6", TEXT, dict(wpm=25, snr_db=6, qsb_hz=0.5, qsb_depth=0.7)),
    ("QRM 500 Hz -6 dB", TEXT, dict(wpm=25, snr_db=15, qrm_hz=500, qrm_db=-6)),
    ("QRM 850 Hz -3 dB", TEXT, dict(wpm=25, snr_db=15, qrm_hz=850, qrm_db=-3)),
    ("Jitter 15%", TEXT, dict(wpm=25, snr_db=20, jitter=0.15)),
    ("schwer gewichtet", TEXT, dict(wpm=25, snr_db=20, weight=1.3)),
    ("leicht gewichtet", TEXT, dict(wpm=25, snr_db=20, weight=0.75)),
    ("Zahlen/Prosign", TEXT2, dict(wpm=28, snr_db=12)),
    ("alles zusammen", TEXT2, dict(wpm=30, snr_db=8, drift_hz=40, qsb_hz=0.4,
                                   qsb_depth=0.6, jitter=0.1)),
]


def main():
    utf8_console()
    verbose = "--verbose" in sys.argv
    scores = []
    for name, text, kw in CASES:
        sig = render(text, fs=8000, seed=42, **kw)
        dec, _ = decode_signal(sig, 8000, block=512)
        got = dec.get_text()
        sc = similarity(got, text)
        scores.append(sc)
        s = dec.status
        flag = "OK " if sc >= 0.95 else ("~  " if sc >= 0.8 else "!! ")
        print(f"{flag}{name:18s} {100 * sc:5.1f}%  {s['wpm']:4.0f} WPM  {s['freq_hz']:5.0f} Hz"
              + (f"\n      {got}" if verbose or sc < 0.95 else ""))
    print(f"\nMittel: {100 * np.mean(scores):.1f} %")


if __name__ == "__main__":
    main()

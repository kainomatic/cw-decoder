# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""Testsignal-Generator: Morsetext -> WAV mit Rauschen, Pitch-Drift, QSB, QRM.

Beispiel:
    python -m cwdecoder.gen "CQ CQ DE DL1ABC" -o test.wav --wpm 25 --snr 6 --drift 80
"""
import argparse
import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, lfilter

from .morse import encode_text


def keying_pattern(text: str, wpm: float, farnsworth_wpm: float = None,
                   weight: float = 1.0, jitter: float = 0.0, rng=None):
    """Liefert Liste von (on: bool, dauer_sek) für den gegebenen Text.

    wpm:     Gebegeschwindigkeit (PARIS-Standard: Punkt = 1.2 / wpm Sekunden)
    farnsworth_wpm: wenn gesetzt, werden Zeichen- und Wortabstände auf diese
             (langsamere) Geschwindigkeit gestreckt
    weight:  Verhältnis Strich/Punkt-Länge relativ zu 3 (1.0 = sauber)
    jitter:  zufällige relative Schwankung der Elementlängen (0.0 .. 0.3)
    """
    rng = rng or np.random.default_rng()
    dit = 1.2 / wpm
    gap_dit = 1.2 / (farnsworth_wpm or wpm)

    def j(x):
        if jitter <= 0:
            return x
        return x * float(np.clip(1.0 + rng.normal(0, jitter), 0.5, 1.6))

    seq = []
    codes = encode_text(text)
    first = True
    for code in codes:
        if code == " ":
            # Wortabstand = 7 Punkte, davon ist 1 Punkt (Element-Pause) schon
            # als Rest vom letzten Zeichen "gedacht"; wir setzen explizit 7.
            if seq and not seq[-1][0]:
                seq[-1] = (False, 7 * gap_dit)
            else:
                seq.append((False, 7 * gap_dit))
            continue
        if not first:
            # Zeichenabstand 3 Punkte (ersetzt die letzte Elementpause),
            # ein bereits gesetzter Wortabstand bleibt erhalten
            if seq and not seq[-1][0] and seq[-1][1] < 2 * gap_dit:
                seq[-1] = (False, 3 * gap_dit)
        first = False
        for k, el in enumerate(code):
            if k > 0:
                seq.append((False, j(dit)))
            if el == ".":
                seq.append((True, j(dit)))
            else:
                seq.append((True, j(3 * dit * weight)))
        seq.append((False, dit))
    return seq


def render(text: str, fs: int = 8000, wpm: float = 25, pitch: float = 700.0,
           drift_hz: float = 0.0, snr_db: float = 20.0, qsb_hz: float = 0.0,
           qsb_depth: float = 0.0, qrm_hz: float = None, qrm_db: float = -10.0,
           farnsworth_wpm: float = None, weight: float = 1.0, jitter: float = 0.0,
           rise_ms: float = 5.0, lead_s: float = 1.0, tail_s: float = 1.0,
           ssb_filter: bool = True, seed: int = None):
    """Erzeugt ein float32-Signal in [-1, 1]."""
    rng = np.random.default_rng(seed)
    seq = keying_pattern(text, wpm, farnsworth_wpm, weight, jitter, rng)

    total = lead_s + sum(d for _, d in seq) + tail_s
    n = int(total * fs)
    t = np.arange(n) / fs

    # Tastsignal (0/1) mit raised-cosine Flanken
    key = np.zeros(n)
    pos = int(lead_s * fs)
    for on, dur in seq:
        m = int(round(dur * fs))
        if on:
            key[pos:pos + m] = 1.0
        pos += m
    if rise_ms > 0:
        r = max(1, int(rise_ms * fs / 1000))
        win = 0.5 * (1 - np.cos(np.pi * np.arange(r) / r))
        # Glätten der Flanken per Faltung mit Kosinusrampe
        kern = np.concatenate([win, win[::-1]]) / r
        key = np.convolve(key, kern, mode="same")
        key = np.clip(key, 0, 1)

    # Tonhöhe mit langsamer Drift (Sinus über die ganze Dauer) + leichtes Wandern
    if drift_hz:
        f_inst = pitch + drift_hz * np.sin(2 * np.pi * t / max(total, 1) * 1.3)
    else:
        f_inst = np.full(n, pitch)
    phase = 2 * np.pi * np.cumsum(f_inst) / fs
    tone = np.sin(phase)

    # QSB (Fading)
    if qsb_hz > 0 and qsb_depth > 0:
        fade = 1.0 - qsb_depth * 0.5 * (1 + np.sin(2 * np.pi * qsb_hz * t + rng.uniform(0, 6.28)))
    else:
        fade = np.ones(n)

    sig = key * tone * fade

    # Rauschen: weiß, optional durch SSB-Filter 300..2700 Hz
    noise = rng.normal(0, 1, n)
    if ssb_filter:
        b, a = butter(4, [300 / (fs / 2), min(2700, fs / 2 - 100) / (fs / 2)], btype="band")
        noise = lfilter(b, a, noise)
    noise /= np.std(noise) + 1e-12

    # SNR-Definition: Signalleistung (Ton bei Key=1) zu Rauschleistung im
    # SSB-Band (2.4 kHz). Das entspricht der üblichen "SNR in 2.4 kHz"-Angabe.
    sig_power = 0.5  # Sinus mit Amplitude 1
    noise_power = sig_power / (10 ** (snr_db / 10))
    noise *= np.sqrt(noise_power)

    out = sig + noise

    # QRM: zweite Station auf anderer Tonhöhe
    if qrm_hz:
        qrm_seq = keying_pattern("VVV TEST TEST DE DK9ZZ", wpm * 0.8, rng=rng)
        qrm_key = np.zeros(n)
        p = int(0.3 * fs)
        for on, dur in qrm_seq:
            m = int(round(dur * fs))
            if p >= n:
                break
            if on:
                qrm_key[p:min(p + m, n)] = 1.0
            p += m
        qrm = qrm_key * np.sin(2 * np.pi * qrm_hz * t) * (10 ** (qrm_db / 20))
        out = out + qrm

    peak = np.max(np.abs(out)) + 1e-9
    out = (out / peak * 0.8).astype(np.float32)
    return out


def write_wav(path, sig, fs):
    wavfile.write(path, fs, (sig * 32767).astype(np.int16))


def main():
    p = argparse.ArgumentParser(description="Morse-Testsignal erzeugen")
    p.add_argument("text")
    p.add_argument("-o", "--out", default="test.wav")
    p.add_argument("--fs", type=int, default=8000)
    p.add_argument("--wpm", type=float, default=25)
    p.add_argument("--farnsworth", type=float, default=None)
    p.add_argument("--pitch", type=float, default=700)
    p.add_argument("--drift", type=float, default=0, help="Drift-Amplitude in Hz")
    p.add_argument("--snr", type=float, default=20, help="SNR in dB (2.4 kHz Bandbreite)")
    p.add_argument("--qsb", type=float, default=0, help="Fading-Frequenz in Hz")
    p.add_argument("--qsb-depth", type=float, default=0, help="Fading-Tiefe 0..1")
    p.add_argument("--qrm", type=float, default=None, help="Störstation auf dieser Frequenz (Hz)")
    p.add_argument("--qrm-db", type=float, default=-10)
    p.add_argument("--weight", type=float, default=1.0)
    p.add_argument("--jitter", type=float, default=0.0)
    p.add_argument("--seed", type=int, default=None)
    a = p.parse_args()
    sig = render(a.text, fs=a.fs, wpm=a.wpm, pitch=a.pitch, drift_hz=a.drift,
                 snr_db=a.snr, qsb_hz=a.qsb, qsb_depth=a.qsb_depth, qrm_hz=a.qrm,
                 qrm_db=a.qrm_db, farnsworth_wpm=a.farnsworth, weight=a.weight,
                 jitter=a.jitter, seed=a.seed)
    write_wav(a.out, sig, a.fs)
    print(f"geschrieben: {a.out} ({len(sig) / a.fs:.1f} s)")


if __name__ == "__main__":
    main()

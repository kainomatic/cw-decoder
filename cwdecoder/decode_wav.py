"""WAV-Datei offline decodieren, optional mit Referenztext zur Bewertung.

    python -m cwdecoder.decode_wav test.wav
    python -m cwdecoder.decode_wav test.wav --expect "CQ CQ DE DL1ABC" --block 1024
"""
import argparse
import difflib
import numpy as np
from scipy.io import wavfile

from .decoder import CWDecoder, DecoderConfig


def load_wav(path):
    fs, data = wavfile.read(path)
    if data.dtype == np.int16:
        x = data.astype(np.float64) / 32768.0
    elif data.dtype == np.int32:
        x = data.astype(np.float64) / 2147483648.0
    elif data.dtype == np.uint8:
        x = (data.astype(np.float64) - 128) / 128.0
    else:
        x = data.astype(np.float64)
    if x.ndim > 1:
        x = x.mean(axis=1)
    return fs, x


def decode_signal(x, fs, block=512, cfg=None, trace=False):
    dec = CWDecoder(fs, cfg)
    log = []
    for i in range(0, len(x), block):
        dec.process(x[i:i + block])
        if trace and (i // block) % 20 == 0:
            s = dec.status
            log.append((dec.t_ms / 1000, s["freq_hz"], s["snr_db"], s["wpm"]))
    dec.flush()
    return dec, log


def similarity(got: str, expect: str) -> float:
    a = " ".join(got.upper().split())
    b = " ".join(expect.upper().split())
    return difflib.SequenceMatcher(None, a, b).ratio()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("wav")
    p.add_argument("--expect", default=None)
    p.add_argument("--block", type=int, default=512)
    p.add_argument("--freq", type=float, default=None, help="feste Tonfrequenz statt Suche")
    p.add_argument("--trace", action="store_true")
    a = p.parse_args()
    fs, x = load_wav(a.wav)
    cfg = DecoderConfig()
    if a.freq:
        cfg.tracker.fixed_freq = a.freq
    dec, log = decode_signal(x, fs, a.block, cfg, trace=a.trace)
    text = dec.get_text()
    s = dec.status
    print(f"Ton: {s['freq_hz']:.0f} Hz  SNR: {s['snr_db']:.0f} dB  Tempo: {s['wpm']:.0f} WPM")
    print("Text:", text)
    if a.trace:
        for t, f, snr, wpm in log:
            print(f"  t={t:5.1f}s f={f:6.1f}Hz snr={snr:4.1f}dB wpm={wpm:4.1f}")
    if a.expect:
        print(f"Übereinstimmung: {100 * similarity(text, a.expect):.1f} %")


if __name__ == "__main__":
    main()

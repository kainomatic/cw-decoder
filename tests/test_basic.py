"""Schnelltests: python -m pytest tests/  oder  python tests/test_basic.py"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from cwdecoder.gen import render
from cwdecoder.decode_wav import decode_signal, similarity
from cwdecoder.morse import encode_text, decode_symbol
from cwdecoder.callsign import looks_like_call


def test_morse_roundtrip():
    text = "CQ DE DL1ABC <SK>"
    codes = [c for c in encode_text(text) if c != " "]
    assert "".join(decode_symbol(c) for c in codes) == "CQDEDL1ABC<SK>"


def test_clean_decode():
    for fs in (8000, 48000):
        sig = render("CQ TEST DE DL1ABC K", fs=fs, wpm=25, snr_db=20, seed=1)
        dec, _ = decode_signal(sig, fs, block=int(fs * 0.02))
        assert similarity(dec.get_text(), "CQ TEST DE DL1ABC K") >= 0.95


def test_speed_change():
    a = render("CQ TEST", fs=8000, wpm=15, snr_db=20, seed=2, tail_s=0.5)
    b = render("DE DL1ABC K", fs=8000, wpm=32, snr_db=20, seed=3, lead_s=0.5)
    import numpy as np
    dec, _ = decode_signal(np.concatenate([a, b]), 8000, block=160)
    assert similarity(dec.get_text(), "CQ TEST DE DL1ABC K") >= 0.85


def test_callsign():
    assert looks_like_call("DL1ABC") and looks_like_call("W1AW/P")
    assert not looks_like_call("599") and not looks_like_call("TEST")


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)

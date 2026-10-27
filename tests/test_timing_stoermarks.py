# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""Störmark-Filter: Aussetzer am Rand eines Elements (ADR-0025, #21)."""
import pytest

from cwdecoder.decode_wav import decode_signal
from cwdecoder.decoder import DecoderConfig
from cwdecoder.gen import render
from cwdecoder.timing import TimingConfig, TimingDecoder

TEXT = "CQ CQ DE DL1ABC DL1ABC TEST TEST 73 K"
# die ersten Töne laufen ohne Filter (Tempo noch nicht eingemessen)
TAIL = "DL1ABC DL1ABC TEST TEST 73 K"


def _decode(glitch_filter, wpm, seed, dropouts=0.3):
    sig = render(TEXT, fs=8000, wpm=wpm, snr_db=20, dropouts=dropouts, seed=seed)
    cfg = DecoderConfig()
    cfg.timing.glitch_filter = glitch_filter
    dec, _ = decode_signal(sig, 8000, block=512, cfg=cfg)
    return dec.get_text()


@pytest.mark.parametrize("wpm,seed", [(15, 1), (15, 3), (20, 1), (20, 3)])
def test_aussetzer_in_strichen(wpm, seed):
    assert TAIL in _decode(True, wpm, seed)
    assert TAIL not in _decode(False, wpm, seed)


def test_ohne_aussetzer_unveraendert():
    assert _decode(True, 20, 1, dropouts=0.0).split() == TEXT.split()


def _warm(t, n=10):
    """Tempo einmessen: n Punkte, 60 ms Punkt, Zeichen 'E'."""
    for _ in range(n):
        t.mark(60.0)
        t.gap(180.0)


def _run(t, seq):
    out = []
    t.on_char = out.append
    for k, d in enumerate(seq):
        (t.mark if k % 2 == 0 else t.gap)(float(d))
    t.force_flush()
    return "".join(out)


def test_kurzer_rest_nach_kurzer_pause_wird_angehaengt():
    # Strich 150 ms, Aussetzer 20 ms, Rest 15 ms (< 0,4 Punkt): ein Strich
    t = TimingDecoder()
    _warm(t)
    assert _run(t, [150, 20, 15, 180]) == "T"


def test_kurzer_anfang_vor_kurzer_pause_wird_vorangestellt():
    t = TimingDecoder()
    _warm(t)
    assert _run(t, [15, 20, 150, 180]) == "T"


def test_nie_bei_frischem_tempo():
    seq = [150, 20, 22, 180, 60, 60, 150, 20, 22, 400]
    on = _run(TimingDecoder(), seq)
    off = _run(TimingDecoder(TimingConfig(glitch_filter=False)), seq)
    assert on == off


def test_zeichen_wird_nie_leer():
    # einzelner kurzer Ton zwischen langen Pausen bleibt (alte Regel:
    # erst unter 0,3 Punkt verworfen)
    t = TimingDecoder()
    _warm(t)
    assert _run(t, [22, 400]) == "E"


def test_verwerfen_nur_mit_schalter():
    seq = [60, 60, 60, 60, 22, 400]                # I + Knackser 22 ms
    t = TimingDecoder()
    _warm(t)
    assert _run(t, seq) == "S"                     # Standard: nicht verwerfen
    t = TimingDecoder(TimingConfig(glitch_discard=True))
    _warm(t)
    assert _run(t, seq) == "I"


def test_filter_abschaltbar():
    # Rest 22 ms (0,37 Punkt) liegt über der alten 0,3-Punkt-Grenze
    t = TimingDecoder(TimingConfig(glitch_filter=False))
    _warm(t)
    assert _run(t, [150, 20, 22, 180]) == "N"     # Strich + Punkt
    t = TimingDecoder()
    _warm(t)
    assert _run(t, [150, 20, 22, 180]) == "T"


@pytest.mark.parametrize("block", [80, 160, 512])
def test_blockgroesse_egal(block):
    sig = render(TEXT, fs=8000, wpm=20, snr_db=20, dropouts=0.3, seed=1)
    dec, _ = decode_signal(sig, 8000, block=block)
    assert TAIL in dec.get_text()

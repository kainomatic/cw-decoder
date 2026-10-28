# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""Der Text hängt nicht von der Blockgröße des Aufrufers ab (#22, ADR-0028).

CWDecoder.process zerlegt die Samples intern in feste Teilblöcke
(DecoderConfig.chunk_ms). Die GUI liefert 20-ms-Blöcke (160 Samples bei
8 kHz), die Matrix 512: Beide müssen exakt denselben Text sehen.
"""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(__file__))
import run_matrix  # noqa: E402
from cwdecoder.decode_wav import decode_signal  # noqa: E402
from cwdecoder.decoder import CWDecoder, DecoderConfig  # noqa: E402

SIZES = (80, 160, 512, 1024)
N_MATRIX = 20


def _texts(x, fs):
    return {b: decode_signal(x, fs, block=b)[0].get_text() for b in SIZES}


def _assert_same(texts, name):
    ref = texts[SIZES[0]]
    diff = {b: t for b, t in texts.items() if t != ref}
    assert not diff, f"{name}: Text hängt von der Blockgröße ab\n{SIZES[0]}: {ref}\n" + \
        "\n".join(f"{b}: {t}" for b, t in diff.items())


def _matrix_cases():
    cases = run_matrix.build_cases(10, 1000)
    # gleichmäßig über alle Kategorien verteilt
    idx = np.linspace(0, len(cases) - 1, N_MATRIX).astype(int)
    return [cases[i] for i in idx]


@pytest.mark.slow
@pytest.mark.parametrize("case", _matrix_cases(), ids=lambda c: c[1])
def test_matrix_blockgroesse(case):
    from cwdecoder.gen import render
    cat, name, text, kw, seed = case
    sig = render(text, fs=8000, seed=seed, **kw)
    _assert_same(_texts(sig, 8000), name)


@pytest.mark.slow
@pytest.mark.skipif(not os.path.isdir(run_matrix.REAL_DIR), reason="testdata/real/ fehlt")
@pytest.mark.parametrize("fname", run_matrix.real_files() if os.path.isdir(run_matrix.REAL_DIR) else [])
def test_real_blockgroesse(fname):
    from cwdecoder.decode_wav import load_wav
    fs, x = load_wav(os.path.join(run_matrix.REAL_DIR, fname))
    _assert_same(_texts(x, fs), fname)


def test_rest_wartet_auf_naechsten_aufruf():
    """Unvollständige Teilblöcke werden gepuffert, flush() verarbeitet sie."""
    dec = CWDecoder(8000, DecoderConfig(freq_lookahead_ms=0.0))
    assert dec.chunk == 80
    dec.process(np.zeros(50))
    assert len(dec._rest) == 50 and dec.t_ms == 0.0
    dec.process(np.zeros(50))
    assert len(dec._rest) == 20 and dec.t_ms == pytest.approx(10.0)
    dec.flush()
    assert len(dec._rest) == 0 and dec.t_ms == pytest.approx(12.5)


def test_frequenz_vorausschau_verzoegert_die_huellkurve():
    """Die Hüllkurve läuft freq_lookahead_ms hinter dem Tracker; flush()
    arbeitet die zurückgehaltenen Teilblöcke ab."""
    cfg = DecoderConfig()
    dec = CWDecoder(8000, cfg)
    n_ahead = round(cfg.freq_lookahead_ms / cfg.chunk_ms)
    dec.process(np.zeros(80 * (n_ahead + 3)))
    assert len(dec._ahead) == n_ahead
    assert dec.t_ms == pytest.approx(3 * cfg.chunk_ms)
    dec.flush()
    assert not dec._ahead and dec.t_ms == pytest.approx((n_ahead + 3) * cfg.chunk_ms)


def test_teilblock_bei_48_khz():
    """Der Takt zählt in internen Samples (nach dem Decimator)."""
    dec = CWDecoder(48000)
    assert dec.fs == 8000 and dec.chunk == 80
    dec44 = CWDecoder(44100)
    assert dec44.chunk == round(10.0 * dec44.fs / 1000.0)

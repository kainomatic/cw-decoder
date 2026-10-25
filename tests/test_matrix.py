# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""Testmatrix als Regressionsschutz in CI.

Ersetzt NICHT den Pflichtlauf `python tests/run_matrix.py` vor und nach
DSP-Änderungen (dort zählt der genaue Mittelwert, zuletzt 95,4 %). Hier nur
eine Untergrenze mit etwas Abstand, damit ein grober Einbruch in CI auffällt.
"""
import numpy as np
import os
import sys

import pytest

from cwdecoder.decode_wav import decode_signal, similarity
from cwdecoder.gen import render

sys.path.insert(0, os.path.dirname(__file__))
import run_matrix  # noqa: E402

MIN_MEAN = 0.94


@pytest.mark.slow
def test_matrix_mean_does_not_collapse():
    scores = []
    for _name, text, kw in run_matrix.CASES:
        sig = render(text, fs=8000, seed=42, **kw)
        dec, _ = decode_signal(sig, 8000, block=512)
        scores.append(similarity(dec.get_text(), text))
    assert np.mean(scores) >= MIN_MEAN, f"Mittel {100 * np.mean(scores):.1f} %"

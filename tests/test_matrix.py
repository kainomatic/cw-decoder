# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""Testmatrix als Regressionsschutz in CI.

Ersetzt NICHT den Pflichtlauf `python tests/run_matrix.py` vor und nach
DSP-Änderungen (dort zählt der genaue Mittelwert, zuletzt 97,0 %). Hier nur
eine Untergrenze mit etwas Abstand, damit ein grober Einbruch in CI auffällt.
Die Kategorie "Rauschen" wird zusätzlich einzeln geprüft: bei reinem Rauschen
darf der Decoder nichts ausgeben (Leitlinie in ROADMAP.md).
"""
import numpy as np
import os
import sys

import pytest

from cwdecoder.decode_wav import decode_signal, similarity
from cwdecoder.gen import render

sys.path.insert(0, os.path.dirname(__file__))
import run_matrix  # noqa: E402

MIN_MEAN = 0.95
MIN_NOISE = 0.99


@pytest.mark.slow
def test_matrix_mean_does_not_collapse():
    overall, means = run_matrix.run(n_per_cat=10, verbose=False)
    assert overall >= MIN_MEAN, f"Mittel {100 * overall:.1f} %"
    assert means["Rauschen"] >= MIN_NOISE, f"Müll bei Rauschen: {100 * means['Rauschen']:.1f} %"

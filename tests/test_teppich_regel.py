# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""Teppich-Regel "Dauerträger" im Thresholder (ADR-0025, #21)."""
import numpy as np

from cwdecoder.dsp import ThresholdConfig, Thresholder


def _floor_after_closed_tone(needs_key: bool) -> float:
    """1 s Rauschen, dann 5 s Ton bei geschlossenem Squelch (Gate zu)."""
    rng = np.random.default_rng(1)
    th = Thresholder(1000, ThresholdConfig(carrier_needs_key=needs_key))
    noise = np.abs(rng.normal(0, 1e-3, 1000)) + 1e-4
    th.process(noise, np.zeros(len(noise), dtype=bool))
    tone = np.full(5000, 0.1)
    th.process(tone, np.zeros(len(tone), dtype=bool))
    assert not th.state
    return th.floor_db


def test_alte_regel_teppich_steigt_auch_nach_pause():
    assert _floor_after_closed_tone(False) > -22.0      # bis an den Tonpegel (-20 dB)


def test_mit_tastung_an_bleibt_teppich_unten():
    assert _floor_after_closed_tone(True) < -30.0       # nur langsames Kriechen


def test_standard_ist_alte_regel():
    assert ThresholdConfig().carrier_needs_key is False

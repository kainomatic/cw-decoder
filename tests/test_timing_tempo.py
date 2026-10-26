# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""Tempo-Grenzen und Tempo-Reset des TimingDecoders (ADR-0018)."""
import numpy as np
import pytest

from cwdecoder.decode_wav import decode_signal
from cwdecoder.gen import render
from cwdecoder.timing import DIT_MAX_MS, DIT_MIN_MS, TimingConfig, TimingDecoder


def test_tempo_bereich_5_bis_60_wpm():
    assert 1200.0 / DIT_MIN_MS == pytest.approx(60.0)
    assert 1200.0 / DIT_MAX_MS == pytest.approx(5.0)
    cfg = TimingConfig()
    assert (cfg.dit_min_ms, cfg.dit_max_ms) == (DIT_MIN_MS, DIT_MAX_MS)


def test_reset_tempo_verwirft_gedaechtnis_und_klemmt_startwert():
    t = TimingDecoder()
    for d in [20.0, 60.0, 20.0, 20.0, 60.0, 20.0]:   # 60 WPM
        t.mark(d)
        t.gap(20.0)
    assert t.n_marks > 0
    t.reset_tempo()
    assert len(t.marks) == 0 and len(t.gaps) == 0 and len(t.char_gaps) == 0
    assert t.n_marks == 0 and not t.confident
    assert 30.0 <= t.dit_ms <= 150.0   # Startwert 8..40 WPM


def test_reines_rauschen_durch_cw_filter_gibt_nichts_aus():
    sig = render("", fs=8000, snr_db=0, pitch=800, rx_filter_hz=120,
                 lead_s=8, tail_s=0.5, seed=3)
    dec, _ = decode_signal(sig, 8000, block=512)
    assert dec.get_text().replace(" ", "") == ""


def test_rx_filter_daempft_ausserhalb_des_durchlassbereichs():
    sig = render("", fs=8000, snr_db=0, pitch=800, rx_filter_hz=100,
                 lead_s=4, tail_s=0.5, seed=1)
    spec = np.abs(np.fft.rfft(sig)) ** 2
    f = np.fft.rfftfreq(len(sig), 1 / 8000)
    inside = spec[(f > 770) & (f < 830)].mean()
    outside = spec[(f > 400) & (f < 600)].mean()
    assert 10 * np.log10(inside / outside) > 30

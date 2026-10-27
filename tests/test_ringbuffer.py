# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""Ringpuffer für Audio und Decoder-Ausgabe (ADR-0024, #19)."""
import threading

import numpy as np
import pytest

from cwdecoder.ringbuffer import AudioRing, TokenRing, excerpt_name, tokens_text


def _ramp(n):
    return np.arange(n, dtype=np.float32)


def test_wrap_around_liefert_neuestes_in_reihenfolge():
    ring = AudioRing(fs=100, seconds=1.0)          # 100 Samples
    sig = _ramp(1234)
    for i in range(0, len(sig), 37):               # krumme Blöcke, mehrfach umlaufend
        ring.write(sig[i:i + 37])
    assert ring.duration_s == 1.0
    assert ring.total_s == pytest.approx(12.34)
    np.testing.assert_array_equal(ring.last(1.0), sig[-100:])
    np.testing.assert_array_equal(ring.last(0.25), sig[-25:])


def test_block_groesser_als_kapazitaet():
    ring = AudioRing(fs=100, seconds=1.0)
    ring.write(_ramp(10))
    ring.write(_ramp(250) + 1000)
    np.testing.assert_array_equal(ring.last(5.0), _ramp(250)[-100:] + 1000)


def test_weniger_vorhanden_als_angefragt():
    ring = AudioRing(fs=1000, seconds=10.0)
    assert len(ring.last(3.0)) == 0
    ring.write(_ramp(1500))
    out, t_end = ring.snapshot(3.0)
    assert len(out) == 1500 and t_end == pytest.approx(1.5)
    np.testing.assert_array_equal(out, _ramp(1500))
    assert ring.duration_s == pytest.approx(1.5)


@pytest.mark.parametrize("block_ms", [10, 20, 64])
@pytest.mark.parametrize("fs", [8000, 48000])
def test_blockgroessen(block_ms, fs):
    ring = AudioRing(fs=fs, seconds=2.0)
    sig = np.sin(np.arange(int(fs * 5.3)) * 0.01).astype(np.float32)
    bs = fs * block_ms // 1000
    for i in range(0, len(sig), bs):
        ring.write(sig[i:i + bs])
    np.testing.assert_array_equal(ring.last(2.0), sig[-2 * fs:])
    np.testing.assert_array_equal(ring.last(0.5), sig[-fs // 2:])


def test_write_allokiert_nicht():
    ring = AudioRing(fs=1000, seconds=1.0)
    buf = ring._buf
    for _ in range(50):
        ring.write(np.ones(333, dtype=np.float32))
    assert ring._buf is buf


def test_threadsicher():
    """Lesen während des Schreibens liefert immer ein lückenloses Stück."""
    ring = AudioRing(fs=1000, seconds=1.0)
    stop = threading.Event()

    def writer():
        k = 0
        while not stop.is_set():
            ring.write(_ramp(160) + k)
            k += 160

    t = threading.Thread(target=writer)
    t.start()
    try:
        for _ in range(300):
            x = ring.last(0.5)
            if len(x) > 1:
                assert np.all(np.diff(x) == 1)
    finally:
        stop.set()
        t.join()


def test_token_ring_schneidet_und_zeiten_relativ():
    tr = TokenRing(seconds=10)
    for i, tok in enumerate("CQ TEST DE DL1ABC"):
        tr.add(1.0 + i, tok, 0.9 if tok != " " else None)
    win = tr.window(5.0, 9.0)
    assert [tok for _t, tok, _c in win] == list("EST D")   # t = 5 … 9
    assert win[0][0] == pytest.approx(0.0)        # t=5 relativ zu 5
    assert win[-1][0] == pytest.approx(4.0)
    assert win[0][2] == 0.9


def test_token_ring_vergisst_altes():
    tr = TokenRing(seconds=10)
    for t in range(100):
        tr.add(float(t), "E", 1.0)
    assert len(tr._items) <= 17                   # 10 s + 5 s Reserve
    assert tr.window(0, 50) == []


def test_tokens_text_und_name():
    toks = [(0.1, "C", 1.0), (0.2, "Q", 1.0), (0.3, " ", None), (0.4, "¶", None),
            (0.5, "K", 0.4)]
    assert tokens_text(toks) == "CQ \n\nK"
    from datetime import datetime
    name = excerpt_name(30, datetime(2026, 10, 27, 21, 5, 9, 123456))
    assert name == "cw_20261027_210509_123_letzte30s.wav"

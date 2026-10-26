# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""Erstes Zeichen nach einer langen Pause (Issue #5, #8).

Im Live-Betrieb liegt vor jedem Durchgang Rauschen. Der Squelch muss
rechtzeitig öffnen, sonst fehlt der Anfang des ersten Zeichens (C -> N/F).
Die GUI liefert Audio in 20-ms-Blöcken; der Decoder muss davon unabhängig
sein, deshalb auch kleine Blöcke.
"""
import pytest

from cwdecoder.decode_wav import decode_signal
from cwdecoder.gen import render


@pytest.mark.parametrize("block_ms", [10, 20, 64])
@pytest.mark.parametrize("lead_s", [1.0, 3.0, 6.0])
@pytest.mark.parametrize("seed", [1, 2, 3])
def test_erstes_zeichen_nach_pause(block_ms, lead_s, seed):
    fs = 8000
    sig = render("CQ TEST DE DL1ABC K", fs=fs, wpm=25, snr_db=15,
                 seed=seed, lead_s=lead_s)
    dec, _ = decode_signal(sig, fs, block=int(fs * block_ms / 1000))
    assert dec.get_text().strip().startswith("CQ")

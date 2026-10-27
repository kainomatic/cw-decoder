# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""„Letzte 30 s speichern“: WAV + Decodier-Log aus dem Ringpuffer (ADR-0024, #19)."""
import os
import re

import numpy as np
import pytest

from cwdecoder.decode_wav import decode_signal, load_wav
from cwdecoder.gen import render
from cwdecoder.live import LiveDecoder
from cwdecoder.ringbuffer import SaveLastError, save_excerpt, tokens_text

SAVE_S = 30


def _feed(live, sig, fs, block_ms=20):
    bs = fs * block_ms // 1000
    for i in range(0, len(sig), bs):
        live.feed(sig[i:i + bs])


def _signal(fs):
    """Zwei Durchgänge; die letzten 30 s beginnen 3 s in der Pause davor."""
    a = render("CQ CQ DE DL1ABC", fs=fs, wpm=25, snr_db=15, tail_s=0.5, seed=11)
    b0 = render("TEST DE DJ7PR DJ7PR K", fs=fs, wpm=25, snr_db=15, lead_s=0.0,
                tail_s=2.0, seed=12)
    lead = SAVE_S - len(b0) / fs + 3.0
    b = render("TEST DE DJ7PR DJ7PR K", fs=fs, wpm=25, snr_db=15, lead_s=lead,
               tail_s=2.0, seed=12)
    return np.concatenate([a, b]).astype(np.float32)


def _read_log(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            t, tok, conf = line.rstrip("\n").split(";")
            rows.append((float(t), tok, float(conf) if conf else None))
    return rows


@pytest.mark.parametrize("fs", [8000, 48000])
def test_speichert_wav_und_txt_im_aufnahmen_ordner(app_env, fs):
    from cwdecoder.paths import get_recordings_dir
    sig = _signal(fs)
    live = LiveDecoder(fs, ring_seconds=60)
    _feed(live, sig, fs)

    rec = get_recordings_dir()
    assert str(rec).startswith(str(app_env))
    wav, secs = save_excerpt(rec, live.ring, live.token_ring, SAVE_S)
    assert os.path.dirname(wav) == str(rec)
    assert re.fullmatch(r"cw_\d{8}_\d{6}_\d{3}_letzte30s\.wav", os.path.basename(wav))
    assert secs == SAVE_S

    fs_wav, x = load_wav(wav)
    assert fs_wav == fs and len(x) == SAVE_S * fs
    # Inhalt = Ende des Signals (16 Bit gerundet)
    np.testing.assert_allclose(x, sig[-SAVE_S * fs:], atol=3 / 32767)

    txt = os.path.splitext(wav)[0] + ".txt"
    rows = _read_log(txt)
    assert rows and all(0.0 <= t <= SAVE_S for t, _tok, _c in rows)
    assert all(c is not None for _t, tok, c in rows if tok.strip() and tok != "¶")
    window_text = " ".join(tokens_text(rows).split())
    assert window_text == "TEST DE DJ7PR DJ7PR K"

    # Abnahme: decode_wav auf der WAV liefert denselben Text wie die TXT
    dec, _ = decode_signal(x, fs_wav)
    assert " ".join("".join(dec.text).split()) == window_text


def test_weniger_im_puffer_als_verlangt(app_env):
    from cwdecoder.paths import get_recordings_dir
    fs = 8000
    live = LiveDecoder(fs, ring_seconds=60)
    sig = render("CQ DE DL1ABC", fs=fs, wpm=25, snr_db=20, seed=3).astype(np.float32)
    _feed(live, sig, fs)
    wav, secs = save_excerpt(get_recordings_dir(), live.ring, live.token_ring, SAVE_S)
    assert secs == pytest.approx(len(sig) / fs, abs=1 / fs)
    _, x = load_wav(wav)
    assert len(x) == len(sig)
    assert " ".join(tokens_text(_read_log(wav[:-4] + ".txt")).split()) == "CQ DE DL1ABC"


def test_ordner_nicht_beschreibbar(tmp_path):
    from cwdecoder.gui_errors import classify_error
    fs = 8000
    live = LiveDecoder(fs, ring_seconds=10)
    live.feed(np.zeros(fs, dtype=np.float32))
    blocker = tmp_path / "datei"
    blocker.write_text("x")
    with pytest.raises(SaveLastError) as ei:
        save_excerpt(blocker / "Aufnahmen", live.ring, live.token_ring, 5)
    info = classify_error(ei.value)
    assert info.expected and info.title == "Ausschnitt nicht gespeichert"

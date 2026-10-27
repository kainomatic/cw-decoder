# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""Absätze im Live-Text und Decodier-Log neben der Aufnahme (#10)."""
import numpy as np

from cwdecoder.decoder import CWDecoder
from cwdecoder.gen import render
from cwdecoder.live import DecodeLog, LiveDecoder, decode_log_path

FS = 8000


def two_overs(pause_s):
    a = render("CQ TEST DE DL1ABC K", fs=FS, wpm=25, snr_db=20, seed=1, tail_s=pause_s)
    b = render("DL1ABC DE OK1XYZ K", fs=FS, wpm=25, snr_db=20, seed=2, lead_s=0.5)
    return np.concatenate([a, b])


def run(sig, dec):
    for i in range(0, len(sig), 160):    # 20-ms-Blöcke wie die GUI
        dec.process(sig[i:i + 160])
    dec.flush()


def test_absatz_nach_langer_pause():
    out = []
    dec = CWDecoder(FS, on_char=out.append, on_space=lambda: out.append(" "),
                    on_paragraph=lambda: out.append("¶"))
    run(two_overs(5.0), dec)
    text = "".join(out)
    assert text.count("¶") == 1, text
    before, after = text.split("¶")
    assert "DL1ABC K" in before and "OK1XYZ" in after


def test_kein_absatz_ohne_text_davor():
    out = []
    dec = CWDecoder(FS, on_char=out.append, on_paragraph=lambda: out.append("¶"))
    run(render("", fs=FS, snr_db=0, lead_s=8, tail_s=0.5, seed=4), dec)
    assert "¶" not in "".join(out)


def test_get_text_ohne_absaetze():
    dec = CWDecoder(FS, on_paragraph=lambda: None)
    run(two_overs(5.0), dec)
    assert "\n" not in dec.get_text()


def test_decodier_log(tmp_path):
    wav = tmp_path / "cw_20261026_231339_217.wav"
    assert decode_log_path(str(wav)) == str(tmp_path / "cw_20261026_231339_217.txt")
    texts = []
    live = LiveDecoder(FS, on_text=texts.append)
    live.decode_log = DecodeLog(decode_log_path(str(wav)))
    run(two_overs(5.0), live.dec)
    live.decode_log.close()
    lines = (tmp_path / "cw_20261026_231339_217.txt").read_text(encoding="utf-8").splitlines()
    rows = [ln.split(";") for ln in lines]      # sekunde;zeichen;vertrauen (#18)
    assert all(len(r) == 3 for r in rows)
    times = [float(r[0]) for r in rows]
    tokens = [r[1] for r in rows]
    assert all(len(r[0].split(".")[1]) == 2 for r in rows)      # 2 Nachkommastellen
    assert times == sorted(times) and times[0] > 0.5
    assert "".join(tokens).replace("¶", "|").startswith("CQ TEST DE DL1ABC K")
    assert tokens.count("¶") == 1 and " " in tokens
    assert "\n\n" in texts                                         # Leerzeile im Fenster

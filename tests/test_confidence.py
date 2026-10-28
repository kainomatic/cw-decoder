# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""Vertrauen je Zeichen (ADR-0023, #18).

Das Vertrauen ist reine Metadaten: Die Zeichenausgabe muss mit und ohne
Berechnung identisch sein. Sauberes Signal -> nichts unsicher; Jitter ->
unsichere Zeichen; '*' -> 0; erstes Zeichen nach reset_tempo niedriger.
"""
import os
import sys

import numpy as np
import pytest

from cwdecoder import decode_wav
from cwdecoder.decoder import CWDecoder, UNSURE_CONF, mark_unsure
from cwdecoder.gen import render, write_wav
from cwdecoder.live import DecodeLog, LiveDecoder
from cwdecoder.timing import TimingDecoder

sys.path.insert(0, os.path.dirname(__file__))
import run_matrix  # noqa: E402

FS = 8000
TEXT = "CQ TEST DE OZ1HGT OZ1HGT K"


def decode(sig, block=512):
    dec = CWDecoder(FS)
    for i in range(0, len(sig), block):
        dec.process(sig[i:i + block])
    dec.flush()
    return dec


def char_confs(dec):
    return [c for c in dec.confs if c is not None]


def neutralize(monkeypatch):
    """Vertrauensberechnung abschalten (konstant 1)."""
    monkeypatch.setattr(TimingDecoder, "confidence", lambda self, marks, ch: 1.0)
    monkeypatch.setattr(CWDecoder, "char_confidence", lambda self: 1.0)


def test_sauberes_signal_nichts_unsicher():
    for seed in range(3):
        dec = decode(render(TEXT, fs=FS, wpm=25, snr_db=30, seed=seed))
        assert dec.get_text().strip() == TEXT
        confs = char_confs(dec)
        assert len(confs) == len(TEXT.replace(" ", ""))
        assert min(confs) >= UNSURE_CONF, confs
        assert dec.get_text_marked() == dec.get_text()


@pytest.mark.parametrize("kw", [dict(jitter=0.25), dict(jitter=0.2, weight=0.75)])
def test_jitter_gibt_unsichere_zeichen_text_unveraendert(kw, monkeypatch):
    unsure_total = 0
    for seed in range(3):
        sig = render(TEXT, fs=FS, wpm=25, snr_db=30, seed=seed, **kw)
        dec = decode(sig)
        unsure_total += sum(c < UNSURE_CONF for c in char_confs(dec))
        with monkeypatch.context() as m:
            neutralize(m)
            plain = decode(sig)
        assert dec.get_text() == plain.get_text()
        assert dec.get_text_marked().upper() == dec.get_text()
    assert unsure_total > 0


def test_unbekanntes_symbol_hat_null():
    td = TimingDecoder()
    assert td.confidence([60.0] * 7, "*") == 0.0
    got = []
    td = TimingDecoder(on_char=lambda ch: got.append((ch, td.last_conf)))
    for _ in range(7):              # sieben Punkte: kein Zeichen der Tabelle
        td.mark(60.0)
        td.gap(60.0)
    td.force_flush()
    assert got == [("*", 0.0)]


def test_erstes_zeichen_nach_reset_tempo_niedriger():
    got = []
    td = TimingDecoder(on_char=lambda ch: got.append(td.last_conf))
    dit = 48.0                      # 25 WPM, sauber

    def send(code):
        for k, el in enumerate(code):
            td.mark(dit if el == "." else 3 * dit)
            if k < len(code) - 1:
                td.gap(dit)
        td.gap(3 * dit)

    rounds = []
    for _ in range(2):
        start = len(got)
        for code in ("-.-.", "--.-", "-", ".", "...", "-"):     # CQ TEST
            send(code)
        td.force_flush()
        rounds.append(got[start:])
        td.reset_tempo()
    for confs in rounds:
        # erstes Zeichen mit Abschlag, ab dem dritten (8 Töne gehört) keiner mehr
        assert all(confs[0] < c for c in confs[2:]), confs
        assert confs[0] >= UNSURE_CONF        # sauber gegeben: nicht grau


def test_snr_abschlag():
    dec = CWDecoder(FS)
    dec.timing.last_conf = 1.0
    dec.thresh.snr_db = 30.0
    assert dec.char_confidence() == pytest.approx(1.0)
    dec.thresh.snr_db = dec.cfg.conf_snr_low_db
    assert dec.char_confidence() == pytest.approx(dec.cfg.conf_snr_min)


def test_last_conf_vor_on_char_und_callback():
    seen = []
    dec = None

    def on_char(ch):
        seen.append(("char", ch, dec.last_conf))

    dec = CWDecoder(FS, on_char=on_char,
                    on_char_conf=lambda ch, c: seen.append(("conf", ch, c)))
    sig = render("TEST", fs=FS, wpm=25, snr_db=30, seed=1)
    for i in range(0, len(sig), 160):
        dec.process(sig[i:i + 160])
    dec.flush()
    chars = [s for s in seen if s[0] == "char"]
    confs = [s for s in seen if s[0] == "conf"]
    assert "".join(c[1] for c in chars) == "TEST"
    assert [c[1:] for c in chars] == [c[1:] for c in confs]


def test_mark_unsure():
    assert mark_unsure(list("OZ1HGT"), [1, 1, 0.2, 0.3, 0.9, 1]) == "OZ1hGT"
    assert mark_unsure(["C", " ", "<BT>"], [0.1, None, 0.2]) == "c <bt>"


def test_decode_wav_schreibt_unsichere_klein(tmp_path, capsys):
    clean = tmp_path / "sauber.wav"
    write_wav(str(clean), render(TEXT, fs=FS, wpm=25, snr_db=30, seed=1), FS)
    decode_wav.main([str(clean), "--expect", TEXT])
    out = capsys.readouterr().out
    line = next(ln for ln in out.splitlines() if ln.startswith("Text:"))
    assert line[5:].strip() == TEXT
    shaky = tmp_path / "jitter.wav"
    write_wav(str(shaky), render(TEXT, fs=FS, wpm=25, snr_db=30, seed=2, jitter=0.25), FS)
    decode_wav.main([str(shaky), "--expect", TEXT])
    out = capsys.readouterr().out
    line = next(ln for ln in out.splitlines() if ln.startswith("Text:"))
    assert any(ch.islower() for ch in line[5:]), line
    # --expect vergleicht ohne Groß/klein
    assert "Übereinstimmung" in out


def test_decodier_log_dritte_spalte(tmp_path):
    path = tmp_path / "cw_x.txt"
    live = LiveDecoder(FS, on_text=lambda s: None)
    live.decode_log = DecodeLog(str(path))
    sig = render("CQ DE DL1ABC", fs=FS, wpm=25, snr_db=30, seed=3)
    for i in range(0, len(sig), 160):
        live.dec.process(sig[i:i + 160])
    live.dec.flush()
    live.decode_log.close()
    rows = [ln.split(";") for ln in path.read_text(encoding="utf-8").splitlines()]
    assert all(len(r) == 3 for r in rows)
    chars = [r for r in rows if r[1].strip()]
    assert "".join(r[1] for r in chars) == "CQDEDL1ABC"
    for _t, _ch, conf in chars:
        assert len(conf.split(".")[1]) == 2 and 0.0 <= float(conf) <= 1.0
    assert all(r[2] == "" for r in rows if not r[1].strip())


N_MATRIX = 20


@pytest.mark.decoder
def test_matrix_text_mit_und_ohne_vertrauen_identisch(monkeypatch):
    """20 Fälle der Matrix (Seed 1000), gleichmäßig über alle Kategorien:
    gleicher Text ohne Berechnung (#28; vorher alle 110)."""
    cases = run_matrix.build_cases(10, 1000)
    idx = np.linspace(0, len(cases) - 1, N_MATRIX).astype(int)
    cases = [cases[i] for i in idx]
    assert {c[0] for c in cases} == {c[0] for c in run_matrix.build_cases(1, 1000)}
    sigs = [render(text, fs=FS, seed=seed, **kw) for _c, _n, text, kw, seed in cases]
    with_conf = [decode(s).get_text() for s in sigs]
    neutralize(monkeypatch)
    without = [decode(s).get_text() for s in sigs]
    diff = [(cases[i][1], a, b) for i, (a, b) in enumerate(zip(with_conf, without)) if a != b]
    assert not diff, diff
    assert len(with_conf) == N_MATRIX
    assert np.mean([len(t) for t in with_conf]) > 10

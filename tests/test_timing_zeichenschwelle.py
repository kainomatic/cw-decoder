# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""Adaptive Zeichenschwelle und Trennung ungültiger Symbole (ADR-0025, #21)."""
import pytest

from cwdecoder.decode_wav import decode_signal
from cwdecoder.decoder import DecoderConfig
from cwdecoder.gen import render
from cwdecoder.timing import TimingConfig, TimingDecoder

TEXT = "CQ CQ DE DL1ABC DL1ABC VHX 4HX PSE K"
# Anfang ("DE" kann vor dem Einmessen noch zu "B" verschmelzen) ausgenommen
TAIL = "DL1ABC DL1ABC VHX 4HX PSE K"

# Tastung der 864-Hz-Station in cw_20261027_194831 ab 31,7 s (Ton, Pause,
# Ton, ...): Elementpausen 0,7 Punkte, Zeichenpausen 1,2-2,4 Punkte
STATION_864 = [99, 61, 89, 62, 90, 63, 83, 77, 243, 122, 93, 62, 90, 59, 95, 57, 95,
               187, 242, 67, 86, 63, 90, 63, 240, 217, 90, 68, 90, 63, 87, 69, 88,
               63, 252, 111, 91, 63, 94, 59, 89, 64, 89, 215, 242, 66, 90, 63, 87,
               64, 242]


def _decode(cfg, wpm=25, char_gap=3.0, seed=1, snr_db=20):
    sig = render(TEXT, fs=8000, wpm=wpm, snr_db=snr_db, char_gap=char_gap, seed=seed)
    dec, _ = decode_signal(sig, 8000, block=512, cfg=cfg)
    return dec.get_text()


def _feed(t, seq):
    for k, d in enumerate(seq):
        (t.mark if k % 2 == 0 else t.gap)(float(d))
    t.force_flush()


@pytest.mark.parametrize("char_gap", [1.5, 2.0])
@pytest.mark.parametrize("wpm", [15, 25])
def test_enge_zeichenabstaende_werden_getrennt(char_gap, wpm):
    assert TAIL in _decode(DecoderConfig(), wpm=wpm, char_gap=char_gap)


def test_ohne_adaptive_schwelle_verschmelzen_die_zeichen():
    cfg = DecoderConfig()
    cfg.timing.char_thr_adaptive = False
    cfg.timing.char_split = False
    assert "*" in _decode(cfg, char_gap=2.0)


@pytest.mark.parametrize("char_gap", [3.0, 4.0])
def test_normale_abstaende_bleiben_unveraendert(char_gap):
    assert _decode(DecoderConfig(), char_gap=char_gap).split() == TEXT.split()


def test_station_864_liefert_4hx():
    out = []
    t = TimingDecoder(on_char=out.append)
    _feed(t, STATION_864)
    assert "".join(out) == "4HX4HX"


def test_trennung_ungueltiger_symbole_allein():
    # feste Zeichenschwelle: ohne Trennung wird V+H ein Symbol ('*')
    seq = STATION_864
    out = []
    t = TimingDecoder(TimingConfig(char_thr_adaptive=False), on_char=out.append)
    _feed(t, seq)
    assert "*" not in "".join(out) and "HX" in "".join(out)
    out.clear()
    t = TimingDecoder(TimingConfig(char_thr_adaptive=False, char_split=False),
                      on_char=out.append)
    _feed(t, seq)
    assert "*" in "".join(out)


def test_trennung_nur_wenn_beide_teile_gueltig():
    t = TimingDecoder()
    t.dit_ms = 60.0
    # 9 Punkte mit einer langen Pause in der Mitte: "....." + "...." wäre
    # gültig (5H), aber 3 + 6 Punkte nicht; die längste Pause entscheidet
    marks = [60.0] * 9
    gaps = [60.0, 60.0, 130.0, 60.0, 60.0, 60.0, 60.0, 60.0]
    parts = t._split_invalid(marks, gaps)
    assert parts == [marks]           # S + ...... (ungültig) -> keine Trennung
    gaps = [60.0, 60.0, 60.0, 60.0, 130.0, 60.0, 60.0, 60.0]
    assert t._split_invalid(marks, gaps) == [marks[:5], marks[5:]]


def test_wortschwelle_nie_unter_zeichenschwelle():
    t = TimingDecoder()
    _feed(t, STATION_864)
    t.word_thr_ms = 1.0
    assert t._word_threshold() >= t._char_threshold()


def test_zu_wenige_pausen_feste_schwelle():
    t = TimingDecoder()
    for d in (60, 60, 60, 180, 60):
        t.mark(60.0)
        t.gap(float(d))
    assert t._char_thr_ms is None
    assert t._char_threshold() == pytest.approx(t.cfg.char_thr * t.dit_ms)


def _confs(cfg, seq):
    out = []
    t = TimingDecoder(cfg)
    t.on_char = lambda ch: out.append((ch, t.last_conf))
    for _ in range(10):                  # Tempo einmessen (60 ms Punkt)
        t.mark(60.0)
        t.gap(180.0)
    out.clear()
    _feed(t, seq)
    return out


def test_geteilte_zeichen_haben_gedeckeltes_vertrauen():
    # "....." + "...." mit längerer Pause dazwischen (ungültig -> 5 H),
    # danach ein normales T
    seq = [60, 60] * 4 + [60, 130] + [60, 60] * 3 + [60, 400, 180, 400]
    cfg = TimingConfig(char_thr_adaptive=False)
    out = _confs(cfg, seq)
    assert [ch for ch, _ in out] == ["5", "H", "T"]
    assert all(c <= cfg.char_split_conf for _, c in out[:2])
    assert out[2][1] > cfg.char_split_conf
    # das normale Zeichen ist vom Deckel unberührt
    ref = _confs(TimingConfig(char_thr_adaptive=False, char_split=False), seq)
    assert ref[-1] == out[-1]

# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""Rufzeichen ohne Wortgrenzen (ADR-0019, #10)."""
import pytest

from cwdecoder.callsign import CallsignSpotter, calls_in_word


def spot(text):
    got = []
    sp = CallsignSpotter(on_call=got.append)
    for ch in text:
        sp.feed(ch)
    sp.flush()
    return got, sp


@pytest.mark.parametrize("word,calls", [
    ("DL1ABC", ["DL1ABC"]),             # normales Wort
    ("DEDJ7PR", ["DJ7PR"]),             # DE davor angeklebt
    ("DEIK2ULV", ["IK2ULV"]),
    ("IK2ULVDEOY1CT", ["IK2ULV", "OY1CT"]),
    ("CQDEDL1ABC", ["DL1ABC"]),
    ("DL1DEF", ["DL1DEF"]),             # DE im Suffix zerlegt das Rufzeichen nicht
    ("1CTDEDJ7PRKM", []),               # Suffix-Ende unklar: lieber nichts
    ("DJ7PRRFB", []),
    ("RSTRST579", []),
])
def test_calls_in_word(word, calls):
    assert calls_in_word(word) == calls


def test_zusammengeklebt_wird_gemeldet():
    got, _ = spot("CQ CQ DEDJ7PR K ")
    assert got == ["DJ7PR"]


def test_bekanntes_rufzeichen_im_strom_wird_mitgezaehlt():
    got, sp = spot("DJ7PR K OY1CT DEDJ7PRRFB OY 1 CT DE DJ7PRKM ")
    assert got == ["DJ7PR", "OY1CT"]          # jedes nur einmal gemeldet (30 s)
    assert sp.recent["DJ7PR"][1] == 3          # DJ7PR, DEDJ7PRRFB, DJ7PRKM
    assert sp.recent["OY1CT"][1] == 2          # OY1CT und zerrissen "OY 1 CT"


def test_zerrissenes_neues_rufzeichen_wird_nicht_geraten():
    got, _ = spot("OY 1 CT K ")
    assert got == []


def test_kein_doppelzaehlen_desselben_vorkommens():
    _, sp = spot("DL1ABC DE DL1ABC K TU ")
    assert sp.recent["DL1ABC"][1] == 2


def test_prosign_ist_grenze():
    # Prosigns kommen als eigenes Zeichen, z. B. "<BT>"
    got = []
    sp = CallsignSpotter(on_call=got.append)
    for ch in ["<BT>", "I", "K", "2", "U", "L", "V", "D", "E", "O", "Y", "*", "T", " "]:
        sp.feed(ch)
    assert got == ["IK2ULV"]

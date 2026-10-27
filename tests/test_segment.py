# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""Wörterbuch-Segmentierung zusammengeklebter Wörter (ADR-0026, #23)."""
import os
import sys

import numpy as np
import pytest

from cwdecoder import scp, testtext
from cwdecoder.segment import SEP, Segmenter, WordBuffer, default, load_words

sys.path.insert(0, os.path.dirname(__file__))
import run_matrix  # noqa: E402


@pytest.fixture(scope="module")
def seg():
    return default()


@pytest.mark.parametrize("word,expect", [
    ("TNXFERFBCALL", "TNX FER FB CALL"),
    ("RST5995NN5NN", "RST 599 5NN 5NN"),
    ("GETUESUR569569BK", "GE TU ES UR 569 569 BK"),
    ("DEIN3TWX", "DE IN3TWX"),
    ("IK2ULVDEOY1CT", "IK2ULV DE OY1CT"),
    ("3TU73TUOY1CT", "3 TU 73 TU OY1CT"),
    ("CQDELA8IG", "CQ DE LA8IG"),
    # Prosigns und '*' trennen Stücke, die einzeln zerlegt werden
    ("<BT>TNXFERFBCALL<BT>URRST5995NN5NNUFB*BHIRE",
     "<BT>TNX FER FB CALL<BT>UR RST 599 5NN 5NN UFB*BHIRE"),
    # unsichere Zeichen (klein) bleiben klein
    ("tnxFERFBcall", "tnx FER FB call"),
])
def test_beispiele(seg, word, expect):
    assert seg.segment_word(word, " ") == expect


@pytest.mark.parametrize("word", [
    "DJ7PRRFB",        # Rufzeichenform mit langem Suffix: Spotter findet DJ7PR
    "DJ7PRKM",
    "CUAGN", "DIPOLE", "DRANGEDAL", "STEFAN", "KLAUS", "HAMBURG", "MADRID",
    "PARIS", "LONDON", "CLOUDY", "SUNNY",
    "DL1ABC", "DL/OK1XYZ", "OK1XYZ/P", "5NN", "599", "14075", "001",
    "TEST", "QRZ?",
    "LOUD5NNBKBKFBDRCAEN",     # zwei unbekannte Reste: lieber ganz lassen
])
def test_bleibt_ganz(seg, word):
    assert seg.segment_word(word, " ") == word


def _matrix_words(base_seed):
    for _cat, _name, text, _kw, _seed in run_matrix.build_cases(10, base_seed):
        yield from text.split()


@pytest.mark.parametrize("base_seed", [1000, 5000, 7777])
def test_matrix_texte_unveraendert(seg, base_seed):
    """In den 110 Soll-Texten der Testmatrix ändert die Zerlegung kein Wort."""
    words = list(_matrix_words(base_seed))
    assert len(words) > 500
    changed = [(w, seg.segment_word(w, " ")) for w in words if seg.segment_word(w, " ") != w]
    assert not changed, changed


def test_viele_testtexte_unveraendert(seg):
    rng = np.random.default_rng(42)
    words = [w for _ in range(300) for w in testtext.random_text(rng).split()]
    changed = [w for w in words if seg.segment_word(w, " ") != w]
    assert len(set(words)) >= 20
    assert not changed, changed


def test_zufallsgruppen_fast_nie(seg):
    """Fünfergruppen bleiben ganz (Rest: zufällig echte Floskeln wie DRRIG)."""
    rng = np.random.default_rng(1)
    groups = [testtext.random_block(rng, 1) for _ in range(5000)]
    changed = [g for g in groups if seg.segment_word(g, " ") != g]
    assert len(changed) <= 10, changed      # ≤ 0,2 %


def test_scp_zaehlt_doppelt():
    """Ein SCP-bekanntes Rufzeichen zählt als zwei bekannte Teile und trägt
    so auch einen unbekannten Rest; kurze Rufzeichen zählen nur mit SCP."""
    words = load_words()
    with_scp = Segmenter(words, scp=scp.ScpDb({"DL4KCA", "K1AR"}))
    without = Segmenter(words, scp=None)
    assert with_scp.segment_word("ZZDL4KCA", " ") == "ZZ DL4KCA"
    assert without.segment_word("ZZDL4KCA", " ") == "ZZDL4KCA"
    assert with_scp.segment_word("TUK1AR", " ") == "TU K1AR"
    assert without.segment_word("TUK1AR", " ") == "TUK1AR"


def test_word_cuts_im_strom():
    s = Segmenter(load_words(), scp=None)
    # Strom des Spotters: Prosign als ein Zeichen '|'
    assert s.word_cuts("|TNXFERFB") == [4, 7]


def test_segment_text_mit_trennpunkt(seg):
    text = "CQ  DEIN3TWX K\n\nTNXFB TNXF"
    assert seg.segment_text(text) == f"CQ  DE{SEP}IN3TWX K\n\nTNX{SEP}FB TNXF"


def test_wordbuffer():
    out = []
    b = WordBuffer(out.append, " ")
    for i, ch in enumerate("TNXFB"):
        b.add(ch, 10 + i)
    b.cut([13])
    b.end(" ")
    b.add("<BT>", 15)
    b.end("\n\n")
    b.end()
    assert out == ["TNX FB ", "<BT>\n\n"]


def test_wordbuffer_trenner_nie_am_wortanfang():
    out = []
    b = WordBuffer(out.append, "·")
    b.add("A", 0)
    b.cut([0])
    b.end(" ")
    assert out == ["A "]

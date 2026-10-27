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


# -- Super Check Partial und Zerlegung (ADR-0026, #23) --------------------
from cwdecoder.scp import ScpDb  # noqa: E402


def spot_scp(text, known, segment=False):
    got, spans, cuts = [], [], []
    sp = CallsignSpotter(on_call=got.append, scp=ScpDb(known), segment=segment,
                         on_span=lambda c, a, b: spans.append((c, a, b)),
                         on_segment=cuts.extend)
    for ch in text:
        sp.feed(ch)
    sp.flush()
    return got, spans, cuts


def test_zusammensetzen_mit_scp():
    got, spans, _ = spot_scp("CQ DE IK2J E T K ", {"IK2JET"})
    assert got == ["IK2JET"]
    # Markierung über die ganze Spanne IK2J·E·T (Strom ohne Leerzeichen)
    assert spans == [("IK2JET", 4, 10)]


def test_zusammensetzen_ein_wort_mit_zwei_buchstaben():
    got, _, _ = spot_scp("DE OY1C T K ", {"OY1CT"})
    assert got == ["OY1CT"]
    got, _, _ = spot_scp("DE IK2J ET K ", {"IK2JET"})
    assert got == ["IK2JET"]


def test_ohne_scp_treffer_wie_bisher():
    got, _, _ = spot_scp("CQ DE IK2J E T K ", {"DL1ABC"})
    assert got == ["IK2J"]
    got, _ = spot("CQ DE IK2J E T K ")            # ganz ohne SCP
    assert got == ["IK2J"]


def test_kein_zusammensetzen_mit_k():
    # DL1AB K: DL1ABK steht nicht in SCP -> DL1AB bleibt
    got, _, _ = spot_scp("DE DL1AB K ", {"DL1ABC"})
    assert got == ["DL1AB"]


def test_bekanntes_wartet_nicht():
    got = []
    sp = CallsignSpotter(on_call=got.append, scp=ScpDb({"DL1ABC"}))
    for ch in "DE DL1ABC ":
        sp.feed(ch)
    assert "DL1ABC" in got                      # schon am Wortende, ohne flush


def test_wartendes_kommt_beim_naechsten_langen_wort():
    got = []
    sp = CallsignSpotter(on_call=got.append, scp=ScpDb(set()))
    for ch in "DE QQ1QQ ":
        sp.feed(ch)
    assert got == []                            # wartet auf ein Folgewort
    for ch in "QQ":
        sp.feed(ch)
    assert got == []                            # könnte noch dazugehören
    sp.feed("1")
    assert got == ["QQ1QQ"]                     # Ziffer: kein Rest des Rufzeichens


def test_ganz_gehoert_setzt_spaeter_zusammen():
    """Steht das Rufzeichen nicht in SCP, aber war es einmal ganz da, wird
    es danach auch aus Teilen zusammengesetzt (IK2JET, 194453)."""
    got, spans, _ = spot_scp("DE IK2J E T K DE IK2JET K DE IK2J E T K ", set())
    assert got == ["IK2J", "IK2JET"]
    assert [c for c, _a, _b in spans] == ["IK2J", "IK2JET", "IK2JET"]


def test_zerlegung_meldet_trennstellen_und_rufzeichen():
    got, spans, cuts = spot_scp("TNXFERFBCALL TUESDL4KCA ", {"DL4KCA"}, segment=True)
    assert cuts == [3, 6, 8, 14, 16]
    assert got == ["DL4KCA"]
    assert ("DL4KCA", 16, 22) in spans


def test_zerlegung_unbekanntes_rufzeichen_zaehlt_nicht():
    got, _, cuts = spot_scp("TUESQQ1QQQ ", set(), segment=True)
    assert cuts == [2, 4]                       # Anzeige getrennt
    assert got == []                            # aber kein Spot ohne SCP

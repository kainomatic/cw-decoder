# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""Morse-Tabelle und Prosigns."""
import pytest

from cwdecoder.morse import PROSIGNS, decode_symbol, encode_text


@pytest.mark.parametrize("code,sign", [
    (".-.-.", "<AR>"), ("...-.-", "<SK>"), ("-...-", "<BT>"), ("-.--.", "<KN>"),
    (".-...", "<AS>"), ("-...-.-", "<BK>"),
])
def test_prosigns(code, sign):
    assert decode_symbol(code) == sign


def test_bk_hin_und_zurueck():
    # <BK> = BT und K ohne Pause (#20)
    assert encode_text("<BK>") == ["-...-.-"]
    assert "".join(decode_symbol(c) for c in encode_text("TU <BK>") if c != " ") == "TU<BK>"


def test_prosign_codes_eindeutig():
    assert len(set(PROSIGNS)) == len(PROSIGNS)


def test_unbekannt_ist_stern():
    assert decode_symbol("........-") == "*"

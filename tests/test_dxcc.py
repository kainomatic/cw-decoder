# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""Rufzeichen -> DXCC-Entität aus der mitgelieferten cty.dat (ADR-0021, #11).

Erwartete Namen, Zonen und Präfixe stammen aus cwdecoder/data/cty.dat
(CTY-3633); wird die Datei aktualisiert, können sich Zonen einzelner
Sonderfälle ändern."""
import json
import re
import struct

import pytest

from cwdecoder import dxcc
from cwdecoder.paths import data_path


@pytest.mark.parametrize("call, name, prefix, continent, short, iso", [
    ("OY1CT", "Faroe Islands", "OY", "EU", "Färöer", "fo"),
    ("IK2ULV", "Italy", "I", "EU", "Italien", "it"),
    ("DJ7PR", "Fed. Rep. of Germany", "DL", "EU", "Deutschland", "de"),
    ("4X1AB", "Israel", "4X", "AS", "Israel", "il"),
    ("9A2BC", "Croatia", "9A", "EU", "Kroatien", "hr"),
    ("VP8XYZ", "Falkland Islands", "VP8", "SA", "Falklandinseln", "fk"),
    ("KH6AB", "Hawaii", "KH6", "OC", "Hawaii", "us"),
    ("KL7AB", "Alaska", "KL", "NA", "Alaska", "us"),
    ("VE3ABC", "Canada", "VE", "NA", "Kanada", "ca"),
    ("JA1ABC", "Japan", "JA", "AS", "Japan", "jp"),
    ("ZS6ABC", "South Africa", "ZS", "AF", "Südafrika", "za"),
    ("PY2ABC", "Brazil", "PY", "SA", "Brasilien", "br"),
    ("UA9ABC", "Asiatic Russia", "UA9", "AS", "Asiat. Russland", "ru"),
    ("UA3ABC", "European Russia", "UA", "EU", "Eur. Russland", "ru"),
    ("DL/OK1XYZ", "Fed. Rep. of Germany", "DL", "EU", "Deutschland", "de"),
    ("OK1XYZ/DL", "Fed. Rep. of Germany", "DL", "EU", "Deutschland", "de"),
    ("OK1XYZ/P", "Czech Republic", "OK", "EU", "Tschechien", "cz"),
    ("ok1xyz/qrp", "Czech Republic", "OK", "EU", "Tschechien", "cz"),
    ("KH6/W1AW", "Hawaii", "KH6", "OC", "Hawaii", "us"),
])
def test_lookup_kontinente(call, name, prefix, continent, short, iso):
    e = dxcc.lookup(call)
    assert e is not None, call
    assert (e.name, e.prefix, e.continent, e.short, e.iso) == (
        name, prefix, continent, short, iso)


def test_zonen_aus_hauptzeile_und_ueberschreibung():
    e = dxcc.lookup("DJ7PR")
    assert (e.cq, e.itu) == (14, 28)
    # Präfix mit Zonen-Überschreibung: UA9 ist Asiat. Russland, CQ 17 / ITU 30
    e = dxcc.lookup("UA9ABC")
    assert (e.cq, e.itu) == (17, 30)


def test_seefunk_ohne_land():
    assert dxcc.lookup("W1AW/MM") is None
    assert dxcc.lookup("DL1ABC/MM") is None


def test_exakter_eintrag_vor_praefix():
    """=DP0GVN(38)[67] steht bei Antarktis; DP0… ist sonst Deutschland."""
    e = dxcc.lookup("DP0GVN")
    assert (e.name, e.prefix, e.cq, e.itu, e.iso) == ("Antarctica", "CE9", 38, 67, None)
    assert dxcc.lookup("DP0ABC").prefix == "DL"


def test_exakter_eintrag_mit_schraegstrich():
    assert dxcc.lookup("3Y/LB5SH").name == "Bouvet"


def test_ziffern_zusatz_ersetzt_rufzeichengebiet():
    """EA6SX ist Balearen; EA6SX/5 ist Spanien (EA5SX)."""
    assert dxcc.lookup("EA6SX").prefix == "EA6"
    assert dxcc.lookup("EA6SX/5").prefix == "EA"
    assert dxcc.lookup("W1AW/6").prefix == "K"


def test_laengster_praefix_gewinnt():
    assert dxcc.lookup("KH6XYZ").prefix == "KH6"       # nicht K
    assert dxcc.lookup("VK9XY").prefix == "VK9X"       # nicht VK
    assert dxcc.lookup("EA8AB").prefix == "EA8"        # nicht EA


def test_unbekannt_und_leer():
    assert dxcc.lookup("") is None
    assert dxcc.lookup("   ") is None
    assert dxcc.lookup("QQ1A") is None                 # Q-Präfix gibt es nicht


def test_describe_und_kurzname():
    e = dxcc.lookup("DJ7PR")
    assert dxcc.describe(e) == "Deutschland (DL, EU, CQ 14, ITU 28)"
    assert dxcc.format_lookup("dj7pr") == "DJ7PR: Deutschland (DL, EU, CQ 14, ITU 28)"
    assert dxcc.format_lookup("W1AW/MM") == "W1AW/MM: unbekannt"
    e = dxcc.lookup("UA9ABC")
    assert dxcc.short_name(e, 14) == "Asiat. Russla…"
    assert len(dxcc.short_name(e, 14)) == 14
    assert dxcc.short_name(e, 16) == "Asiat. Russland"


def test_cty_version():
    assert re.fullmatch(r"CTY-\d{4} \(\d{4}-\d{2}-\d{2}\)", dxcc.cty_version())
    # VERSION-Pseudorufzeichen der Datei findet eine Entität
    assert dxcc.lookup("VERSION") is not None


def test_ladezeit_unter_100_ms():
    dxcc._data = None
    try:
        assert dxcc.load() < 100.0
    finally:
        dxcc._data = None


def test_fallback_ohne_tabelle(monkeypatch):
    """Fehlt dxcc_table.json, gibt es englische Namen und keine Flaggen."""
    monkeypatch.setattr(dxcc, "_data", None)

    def kaputt():
        raise OSError("weg")
    monkeypatch.setattr(dxcc, "load_table", kaputt)
    e = dxcc.lookup("OY1CT")
    assert (e.short, e.iso) == ("Faroe Islands", None)
    monkeypatch.setattr(dxcc, "_data", None)


# -- Tabelle und Flaggen ------------------------------------------------------
def _table():
    return json.loads(data_path("dxcc_table.json").read_text(encoding="utf-8"))


def test_jede_entitaet_hat_tabelleneintrag():
    ents = dxcc.entities()
    table = _table()
    assert sorted(ents) == sorted(table), (
        f"fehlt: {sorted(set(ents) - set(table))}, zu viel: {sorted(set(table) - set(ents))}")
    for key, v in table.items():
        assert v["name"] and len(v["name"]) <= 16, key
        assert v["iso"] is None or re.fullmatch(r"[a-z]{2}(-[a-z]{3})?", v["iso"]), key


def _png_size(path):
    head = path.read_bytes()[:24]
    assert head[:8] == b"\x89PNG\r\n\x1a\n", path
    return struct.unpack(">II", head[16:24])


def test_flagge_fuer_jeden_iso_code():
    isos = {v["iso"] for v in _table().values() if v["iso"]}
    flags = data_path("flags")
    total = 0
    for iso in isos:
        path = flags / f"{iso}.png"
        assert path.is_file(), iso
        assert _png_size(path) == (24, 16), iso
        total += path.stat().st_size
    assert total < 300 * 1024
    # keine verwaisten Bilder
    assert {p.stem for p in flags.glob("*.png")} == isos


def test_terminal_ausgabe_mit_land():
    from cwdecoder.live import call_with_country
    assert call_with_country("DJ7PR") == "DJ7PR – Deutschland"
    assert call_with_country("QQ1A") == "QQ1A"

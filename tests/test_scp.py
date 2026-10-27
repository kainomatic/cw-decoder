# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""Super Check Partial (ADR-0026, #23).

Erwartete Treffer stammen aus cwdecoder/data/master.scp (Release
2026.10.23); nach tools/update_scp.py können einzelne Rufzeichen fehlen.
"""
import os
import time

import pytest

from cwdecoder import app_main, scp
from cwdecoder.paths import data_path

ROOT = os.path.join(os.path.dirname(__file__), "..")


@pytest.mark.parametrize("call", ["OY1CT", "DJ7PR", "IN3TWX", "IK2ULV", "DL4KCA", "ES3YJ",
                                  "oy1ct", "DJ7PR/P", "DL/OY1CT"])
def test_bekannt(call):
    assert scp.is_known(call)


@pytest.mark.parametrize("call", ["IK2J", "QQ1QQQ", "", "5NN"])
def test_unbekannt(call):
    assert not scp.is_known(call)


def test_aehnlich_ein_edit():
    db = scp.ScpDb({"IZ4BPF", "OY1CT", "OY1CW", "DL1ABC"})
    assert db.near("Z4BPF") == ["IZ4BPF"]           # Einfügen vorn
    assert db.near("OY1CTX") == ["OY1CT"]           # Löschen
    assert db.near("OY1CQ") == ["OY1CT", "OY1CW"]   # Ersetzen, zwei Treffer
    assert db.near("OY1CT") == ["OY1CW"]            # sich selbst nicht
    assert db.near("XX9XX") == []


def test_aehnlich_reihenfolge_und_grenze():
    calls = {f"DL1AB{c}" for c in "CDEFGHIJKLMNOPQ"} | {"XL1ABC"}
    db = scp.ScpDb(calls)
    got = db.near("DL1ABZ")
    assert len(got) == scp.NEAR_MAX
    assert all(c.startswith("DL1AB") for c in got)  # längster gemeinsamer Anfang zuerst


def test_aehnlich_echte_daten():
    assert "LA8IM" in scp.near("LA8IG")


def test_ladezeit_und_umfang():
    with open(data_path(scp.SCP_FILE), encoding="ascii") as f:
        text = f.read()
    t0 = time.perf_counter()
    db = scp.parse_scp(text)
    ms = (time.perf_counter() - t0) * 1000.0
    assert len(db) > 40000
    assert db.version.count(".") == 2
    assert ms < 150, f"Parsen dauert {ms:.0f} ms"
    assert scp.load() < 1000       # inkl. Datei lesen; gecacht danach 0 Aufwand


def test_format_check():
    assert scp.format_check("oy1ct") == "OY1CT: bekannt"
    assert scp.format_check("QQ1QQQ") == "QQ1QQQ: unbekannt"
    assert scp.format_check("LA8IG").startswith("LA8IG: ähnlich: ")


def test_cli(capsys):
    """CWDecoder.exe --scp OY1CT (Bundle-Smoke-Test im Release-Workflow)."""
    assert app_main.main(["--scp", "OY1CT", "QQ1QQQ"]) == 0
    assert capsys.readouterr().out.splitlines() == ["OY1CT: bekannt", "QQ1QQQ: unbekannt"]


def test_fehlende_datei_kostet_nur_scp(monkeypatch, tmp_path):
    d = scp._Default()
    monkeypatch.setattr(scp, "db", lambda: (_ for _ in ()).throw(OSError("fehlt")))
    assert d.is_known("OY1CT") is False
    assert d.near("OY1CT") == []


def test_bundle_dateien():
    """Spec kopiert cwdecoder/data ins Bundle; der Release-Workflow prüft
    master.scp und qso_words.txt im fertigen Bundle."""
    for f in ("master.scp", "qso_words.txt"):
        assert data_path(f).is_file(), f
    with open(os.path.join(ROOT, "cwdecoder.spec"), encoding="utf-8") as f:
        assert '("cwdecoder/data", "cwdecoder/data")' in f.read()
    with open(os.path.join(ROOT, ".github", "workflows", "release.yml"), encoding="utf-8") as f:
        wf = f.read()
    assert '"master.scp", "qso_words.txt"' in wf
    assert '"--scp","OY1CT"' in wf


def test_nicht_aus_gui_start_importiert():
    import ast
    with open(os.path.join(ROOT, "cwdecoder", "gui_start.py"), encoding="utf-8") as f:
        tree = ast.parse(f.read())
    names = {getattr(n, "module", None) or "" for n in ast.walk(tree)
             if isinstance(n, (ast.Import, ast.ImportFrom))}
    names |= {a.name for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))
              for a in n.names}
    assert not any("scp" in n or "segment" in n for n in names)

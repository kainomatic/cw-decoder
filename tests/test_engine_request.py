# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""Anforderungsdatei der zweiten an die erste Instanz (#30, ADR-0030)."""
import json
import time

from cwdecoder import engine_request as er


def test_schreiben_und_abholen(tmp_path):
    p = tmp_path / er.REQUEST_FILE
    er.write_request(p, 7367, "Fldigi CW Engine 1")
    assert er.take_request(p) == (7367, "Fldigi CW Engine 1")
    assert not p.exists()                   # einmal abgeholt, dann weg
    assert er.take_request(p) is None
    assert list(tmp_path.iterdir()) == []   # keine .tmp-Reste


def test_veraltete_anforderung_verfaellt(tmp_path):
    p = tmp_path / er.REQUEST_FILE
    er.write_request(p, 7367, "T")
    assert er.take_request(p, now=time.time() + er.MAX_AGE_S + 1) is None
    assert not p.exists()


def test_kaputte_anforderung_wird_verworfen(tmp_path):
    p = tmp_path / er.REQUEST_FILE
    for text in ("kein json", json.dumps({"port": 7367}),
                 json.dumps({"port": 80, "title": "T", "time": time.time()})):
        p.write_text(text, encoding="utf-8")
        assert er.take_request(p) is None
        assert not p.exists()


def test_pfad_neben_dem_lock(app_env):
    from cwdecoder.instance_lock import get_lock_path
    assert er.request_path().parent == get_lock_path().parent

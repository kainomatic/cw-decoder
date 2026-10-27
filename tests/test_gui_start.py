# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""Leichter Start: Zweitinstanz, Zeitmessung, keine schweren Imports (ADR-0020)."""
import os
import subprocess
import sys

from cwdecoder import gui_start

ROOT = os.path.join(os.path.dirname(__file__), "..")


def test_zweite_instanz_holt_fenster_nach_vorn():
    fronted, notices = [], []
    res = gui_start.handle_second_instance(
        4711, find=lambda pid: (99, "CW Decoder v0.1.0 BETA") if pid == 4711 else None,
        front=lambda hwnd: fronted.append(hwnd) or True, notice=lambda: notices.append(1))
    assert res == "front" and fronted == [99] and notices == []


def test_zweite_instanz_ohne_fenster_zeigt_hinweis():
    notices = []
    res = gui_start.handle_second_instance(4711, find=lambda pid: None,
                                           front=lambda hwnd: True,
                                           notice=lambda: notices.append(1))
    assert res == "notice" and notices == [1]


def test_start_timer_misst_ab_prozessstart(caplog):
    import logging
    caplog.set_level(logging.INFO, logger="cwdecoder.start")
    t = gui_start.StartTimer(t_start=0.0)
    total = t.phase("Lock erworben")
    assert total > 1e9      # seit 1970 – also wirklich ab dem übergebenen Start
    assert "Startphase: Lock erworben" in caplog.text


def test_prozess_startzeit_plausibel():
    import time
    t = gui_start.process_start_epoch()
    if sys.platform == "win32":
        assert t is not None and time.time() - 3600 < t <= time.time()


def test_gui_start_importiert_keine_schweren_module():
    """Bis zum Lock dürfen numpy/scipy/sounddevice nicht geladen sein."""
    code = ("import sys; sys.path.insert(0, %r); import cwdecoder.gui_start; "
            "heavy = [m for m in ('numpy', 'scipy', 'sounddevice', 'cwdecoder.gui', "
            "'cwdecoder.dxcc') "
            "if m in sys.modules]; print(heavy)") % ROOT
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                         timeout=60).stdout.strip()
    assert out == "[]"

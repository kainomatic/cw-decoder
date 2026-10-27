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


class _BusyLock:
    other_pid = 4711

    def acquire(self):
        return False

    def release(self):
        pass


def _second_instance(monkeypatch, app_env, listening):
    """gui_start.main als Zweitinstanz mit den Argumenten von N1MM."""
    seen = {"front": 0, "notice": [], "gui": False}
    monkeypatch.setattr("cwdecoder.instance_lock.InstanceLock", lambda *a, **k: _BusyLock())
    monkeypatch.setattr(gui_start, "handle_second_instance",
                        lambda pid: seen.__setitem__("front", pid) or "front")
    monkeypatch.setattr(gui_start, "engine_listening", lambda port, timeout=0.5: listening)
    monkeypatch.setattr(gui_start, "show_starting_notice",
                        lambda ms=0, text="": seen["notice"].append(text))
    monkeypatch.setattr(gui_start, "show_splash",
                        lambda: seen.__setitem__("gui", True))
    gui_start.main(["--n1mm-engine", "--xmlrpc-server-port", "7367", "-ti",
                    "Fldigi CW Engine 1"])
    return seen


def test_n1mm_engine_startet_keine_zweite_instanz(monkeypatch, app_env):
    """N1MM startet CWDecoder.exe, während der CW Decoder schon läuft: die
    zweite holt die erste nach vorn und endet (ADR-0020, ADR-0022)."""
    seen = _second_instance(monkeypatch, app_env, listening=True)
    assert seen["front"] == 4711 and not seen["gui"] and seen["notice"] == []


def test_n1mm_engine_hinweis_wenn_erste_ohne_engine(monkeypatch, app_env):
    seen = _second_instance(monkeypatch, app_env, listening=False)
    assert not seen["gui"]
    assert len(seen["notice"]) == 1 and "Port 7367" in seen["notice"][0]


def test_engine_listening_erkennt_offenen_port():
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    assert not gui_start.engine_listening(port, timeout=0.2)
    s.listen(1)
    try:
        assert gui_start.engine_listening(port, timeout=0.5)
    finally:
        s.close()

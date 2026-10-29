# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""N1MM ruft den CW Reader, während der CW Decoder ohne Engine läuft (#30).

Die zweite Instanz bittet per Anforderungsdatei, die erste schaltet die
Engine nur für diesen Lauf ein (ADR-0030). Haken und config.json bleiben
unverändert, auch nach „Übergabe…“ → Schließen und nach dem Beenden.
"""
import gc
import json
import os
import socket
import sys
import threading
import time

import pytest

from conftest import requires_display

pytestmark = [requires_display, pytest.mark.gui]

TITLE = "Fldigi CW Engine 1"
N1MM_KEYS = ("n1mm_enabled", "n1mm_engine", "n1mm_spot", "n1mm_type",
             "n1mm_clipboard", "n1mm_wipe", "n1mm_rpc_port")


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _wait(app, cond, timeout=3.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        app.update()
        if cond():
            return True
        time.sleep(0.02)
    return cond()


@pytest.fixture
def make_app(app_env, monkeypatch):
    """App mit gespeicherter Config (n1mm_* frei wählbar); räumt auf."""
    sys.path.insert(0, os.path.dirname(__file__))
    import gui_smoke
    monkeypatch.setitem(sys.modules, "sounddevice", gui_smoke.make_fake_sounddevice(48000))
    from cwdecoder import config
    from cwdecoder.gui import App
    apps = []
    path = config.get_config_path()

    def make(engine_port=None, engine_title=None, **n1mm):
        cfg = dict(config.defaults(), **{"n1mm_spot": False, **n1mm})
        config.save(cfg, path)
        a = App(cfg=config.load(path), config_path=path, engine_port=engine_port,
                engine_title=engine_title)
        a.engine_request_file = app_env / "engine-request.json"
        a.update()
        apps.append(a)
        return a

    make.path = path
    make.quit = lambda a: (a._quit(), apps.remove(a))
    make.saved = lambda: {k: json.loads(path.read_text(encoding="utf-8"))[k]
                          for k in N1MM_KEYS}
    yield make
    for a in apps:
        a._quit()
    del apps[:]
    gc.collect()


def test_zweite_instanz_schaltet_engine_der_ersten_ein(make_app):
    """Ende-zu-Ende ohne N1MM: zweite Instanz (eigener Thread, kein tk)
    schreibt die Anforderung und wartet; die erste holt sie in _poll ab.
    Kein Dialog, Ende vor 5 s, danach Engine auf N1MMs Port."""
    from cwdecoder import gui, gui_start
    app = make_app(n1mm_enabled=False, n1mm_engine=False, n1mm_type=True)
    before = make_app.saved()
    port = _free_port()
    assert not gui_start.engine_listening(port, timeout=0.2)
    res = {}

    def second():
        t0 = time.monotonic()
        res["r"] = gui_start.request_engine_of_first(port, TITLE, app.engine_request_file)
        res["s"] = time.monotonic() - t0

    th = threading.Thread(target=second)
    th.start()
    assert _wait(app, lambda: not th.is_alive(), timeout=8.0)
    assert res["r"] == "started" and res["s"] < 5.0, res
    assert gui_start.engine_listening(port)
    assert app.n1mm.engine is not None and app.n1mm.rpc_port == port
    assert app.engine_win is not None and app.engine_win.title() == TITLE
    # nur der Weg Engine: Anbindung ist aus, Eintippen bleibt aus
    assert app.n1mm.use_type is False and app.n1mm.spots is None
    assert app.n1mm_var.get() is False and app.engine_var.get() is False
    assert gui._MSG_ENGINE_FORCED in app.status.get()
    assert app.shown_errors == []
    assert not app.engine_request_file.exists()
    # Übergabe… öffnen und schließen, dann beenden: nichts gespeichert
    app.open_n1mm_settings().close()
    app.update()
    assert make_app.saved() == before
    make_app.quit(app)
    assert make_app.saved() == before


def test_anbindung_an_uebrige_wege_bleiben(make_app):
    app = make_app(n1mm_enabled=True, n1mm_engine=False, n1mm_type=True)
    assert app.n1mm is not None and app.n1mm.engine is None and app.n1mm.use_type
    before = make_app.saved()
    port = _free_port()
    app.request_engine(port, TITLE)
    assert app.n1mm.engine is not None and app.n1mm.rpc_port == port
    assert app.n1mm.use_type is True            # wie eingestellt
    assert app.engine_var.get() is False        # Haken unverändert
    app.open_n1mm_settings().close()
    assert make_app.saved() == before


def test_anderer_haken_speichert_nur_sich_selbst(make_app):
    """Punkt 4: Bisher schrieb jeder Haken alle Wege, auch Werte nur für
    diesen Lauf (Start durch N1MM, Anforderung). Jetzt nur den geänderten."""
    port = _free_port()
    app = make_app(engine_port=port, engine_title=TITLE,
                   n1mm_enabled=False, n1mm_engine=False, n1mm_wipe=True)
    assert app.n1mm.engine is not None          # Start durch N1MM: Engine läuft
    assert app.n1mm_var.get() is False and app.engine_var.get() is False
    app.wipe_var.set(False)
    app._n1mm_changed()
    saved = make_app.saved()
    assert saved["n1mm_wipe"] is False
    assert saved["n1mm_engine"] is False and saved["n1mm_enabled"] is False
    assert saved["n1mm_rpc_port"] == 7367
    assert app.n1mm.engine is not None          # Engine läuft weiter


def test_engine_haken_beendet_den_sonderfall(make_app):
    app = make_app(n1mm_enabled=True, n1mm_engine=False)
    app.request_engine(_free_port(), TITLE)
    assert app.engine_forced and app.n1mm.engine is not None
    app.engine_var.set(True)                    # Nutzer will die Engine dauerhaft
    app._n1mm_changed()
    assert not app.engine_forced and make_app.saved()["n1mm_engine"] is True
    app.engine_var.set(False)                   # … und dann doch nicht
    app._n1mm_changed()
    assert app.n1mm.engine is None and make_app.saved()["n1mm_engine"] is False


def test_port_belegt_meldet_die_erste(make_app, monkeypatch):
    """Kommt die Engine nicht hoch, zeigt die erste den Grund über die
    Fehleranzeige; die zweite endet nach der Wartezeit ohne Dialog."""
    from cwdecoder import gui_start
    app = make_app(n1mm_enabled=False, n1mm_engine=False)
    reported = []
    monkeypatch.setattr(app, "report_error", lambda exc, ctx=None: reported.append(exc))
    busy = socket.socket()
    busy.bind(("127.0.0.1", 0))
    port = busy.getsockname()[1]
    try:
        app.request_engine(port, TITLE)
        assert app.n1mm.engine is None
        assert reported and "Port" in str(reported[0])
        res = gui_start.request_engine_of_first(port, TITLE, app.engine_request_file,
                                                wait_s=0.5)
        assert res == "timeout"
    finally:
        busy.close()


def test_engine_lief_schon_nichts_aendert_sich(make_app):
    port = _free_port()
    app = make_app(n1mm_enabled=True, n1mm_engine=True, n1mm_rpc_port=port)
    eng = app.n1mm.engine
    assert eng is not None
    app.request_engine(port, TITLE)
    assert app.n1mm.engine is eng and not app.engine_forced

# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""GUI: Fenstertitel, Einstellungen, Menü, Rauchtest."""
import json
import os
import subprocess
import sys

import pytest

from conftest import requires_display

ROOT = os.path.join(os.path.dirname(__file__), "..")


def test_window_title():
    pytest.importorskip("tkinter", reason="tkinter fehlt")
    from cwdecoder.__version__ import __version__
    from cwdecoder.gui import window_title
    assert window_title("stable") == f"CW Decoder v{__version__}"
    assert window_title("beta") == f"CW Decoder v{__version__} BETA"
    assert window_title("stable", "1.2.3") == "CW Decoder v1.2.3"


def test_gui_texts_are_constants():
    """Alle Tooltip-, Label- und Meldungstexte als Modulkonstanten."""
    pytest.importorskip("tkinter", reason="tkinter fehlt")
    from cwdecoder import gui
    names = [n for n in vars(gui) if n.startswith(("_LBL_", "_MSG_", "_TT_"))]
    assert len([n for n in names if n.startswith("_TT_")]) >= 10
    assert all(isinstance(getattr(gui, n), str) for n in names)


@pytest.fixture
def app(app_env, monkeypatch):
    sys.path.insert(0, os.path.dirname(__file__))
    import gui_smoke
    monkeypatch.setitem(sys.modules, "sounddevice", gui_smoke.make_fake_sounddevice(48000))
    from cwdecoder import config
    from cwdecoder.gui import App
    path = config.get_config_path()
    config.save(dict(config.defaults(), record_default=True, fixed_freq=650.0), path)
    a = App(cfg=config.load(path), config_path=path)
    a.update()
    yield a
    a._quit()


@requires_display
@pytest.mark.gui
def test_app_reads_and_writes_config(app):
    from cwdecoder import config
    assert app.rec_var.get() is True
    assert app.auto_var.get() is False and app.fixed_freq == 650.0
    assert app.dev_var.get().endswith("Fake USB Audio")
    app.auto_var.set(True)
    app._auto_changed()
    app.wipe_var.set(False)
    app._n1mm_changed()
    app._device_changed()
    saved = json.loads(config.get_config_path().read_text(encoding="utf-8"))
    assert saved["fixed_freq"] is None
    assert saved["n1mm_wipe"] is False
    assert saved["device_name"] == "Fake USB Audio"


@requires_display
@pytest.mark.gui
def test_cli_override_is_not_saved(app_env, monkeypatch):
    sys.path.insert(0, os.path.dirname(__file__))
    import gui_smoke
    monkeypatch.setitem(sys.modules, "sounddevice", gui_smoke.make_fake_sounddevice(48000))
    from cwdecoder import config
    from cwdecoder.gui import App
    path = config.get_config_path()
    a = App(n1mm=False, cfg=dict(config.defaults(), n1mm_enabled=True), config_path=path)
    try:
        assert a.n1mm_var.get() is False
        assert not path.exists()            # Start allein speichert nichts
    finally:
        a._quit()


@requires_display
@pytest.mark.gui
def test_menu_entries(app):
    labels = []
    for i in range(app.menubar.index("end") + 1):
        if app.menubar.type(i) != "cascade":
            continue
        sub = app.nametowidget(app.menubar.entrycget(i, "menu"))
        labels.append(app.menubar.entrycget(i, "label"))
        for k in range(sub.index("end") + 1):
            if sub.type(k) == "command":
                labels.append(sub.entrycget(k, "label"))
    for want in ("Datei", "Aufnahmeordner öffnen", "Beenden", "Hilfe", "Nach Updates suchen",
                 "Log-Ordner öffnen", "Fehler melden…", "Über CW Decoder"):
        assert want in labels


@requires_display
@pytest.mark.gui
def test_about_and_error_report_dialogs(app):
    dlg = app.show_about()
    app.update()
    dlg.destroy()
    rep = app.open_error_report()
    app.update()
    assert "Fehlerbericht" in rep.report_text and "Fake USB Audio" in rep.report_text
    rep.top.destroy()


@requires_display
@pytest.mark.gui
@pytest.mark.slow
def test_gui_smoke():
    """Bestehender GUI-Rauchtest, im eigenen Prozess (mehrere Tk-Fenster,
    ausgetauschtes sounddevice-Modul)."""
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tests", "gui_smoke.py")],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=600)
    assert r.returncode == 0, r.stdout + r.stderr

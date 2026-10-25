# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""Self-Update in der GUI (ADR-0013): Auto-Check, manueller Check, Dialog,
"Später", Opt-out, Installation. Kein Netz: Prüfung und Download sind Attrappen."""
import json
import os
import sys
import time

import pytest

from conftest import requires_display
from cwdecoder.updater import AssetInfo, UpdateCheckResult, UpdateError, UpdateStatus

pytestmark = [requires_display, pytest.mark.gui]

AVAILABLE = UpdateCheckResult(
    UpdateStatus.UPDATE_AVAILABLE, new_version="9.9.9",
    asset=AssetInfo("CWDecoder-Setup-v9.9.9.exe",
                    "https://github.com/kainomatic/cw-decoder/releases/download/v9.9.9/x.exe",
                    3_000_000),
    release_url="https://github.com/kainomatic/cw-decoder/releases/tag/v9.9.9")
CURRENT = UpdateCheckResult(UpdateStatus.UP_TO_DATE)
FAILED = UpdateCheckResult(UpdateStatus.ERROR, error_message="Keine Verbindung zu GitHub (x).")


def pump(app, cond, timeout=5.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        app.update()
        if cond():
            return True
        time.sleep(0.01)
    return False


@pytest.fixture
def app(app_env, monkeypatch):
    sys.path.insert(0, os.path.dirname(__file__))
    import gui_smoke
    monkeypatch.setitem(sys.modules, "sounddevice", gui_smoke.make_fake_sounddevice(48000))
    from cwdecoder import config
    from cwdecoder.gui import App
    path = config.get_config_path()
    a = App(cfg=config.defaults(), config_path=path)
    a.check_calls = []
    a.launched = []

    def fake_launch(installer, exit_fn):
        a.launched.append((installer, exit_fn))

    a.launch_installer = fake_launch
    a.update()
    yield a
    if a.update_dialog is not None:
        a.update_dialog.close()
    a._quit()


def use_result(app, result):
    def check(version, channel):
        app.check_calls.append((version, channel))
        return result
    app.check_for_update = check


def help_labels(app):
    m = app.help_menu
    return [m.entrycget(i, "label") for i in range(m.index("end") + 1)
            if m.type(i) == "command"]


def test_auto_check_shows_dialog_and_later_sets_hint(app, monkeypatch):
    from cwdecoder import gui
    monkeypatch.setattr(gui, "UPDATE_CHECK_DELAY_MS", 1)
    use_result(app, AVAILABLE)
    app.schedule_update_check()
    assert pump(app, lambda: app.update_dialog is not None)
    from cwdecoder.__version__ import CHANNEL, __version__
    assert app.check_calls == [(__version__, CHANNEL)]
    app.update_dialog.later()
    assert app.update_dialog is None
    assert "⬆ Update auf v9.9.9 verfügbar" in help_labels(app)
    # Hinweis öffnet den Dialog wieder
    app.help_menu.invoke(0)
    assert app.update_dialog is not None


def test_auto_check_respects_config(app, monkeypatch):
    from cwdecoder import gui
    monkeypatch.setattr(gui, "UPDATE_CHECK_DELAY_MS", 1)
    use_result(app, AVAILABLE)
    app.cfg["update_check"] = False
    app.schedule_update_check()
    pump(app, lambda: False, timeout=0.3)
    assert app.check_calls == [] and app.update_dialog is None


def test_auto_check_error_only_logged(app):
    use_result(app, FAILED)
    app.start_update_check(manual=False)
    assert pump(app, lambda: not app.update_checking)
    assert app.shown_errors == [] and app.update_dialog is None


def test_manual_check_up_to_date(app):
    use_result(app, CURRENT)
    app.start_update_check(manual=True)
    assert pump(app, lambda: not app.update_checking)
    dialogs = [w for w in app.winfo_children() if w.winfo_class() == "Toplevel"]
    assert dialogs, "Dialog 'aktuell' fehlt"
    texts = [c.cget("text") for d in dialogs for f in d.winfo_children()
             for c in f.winfo_children() if c.winfo_class() == "TLabel"]
    assert any("ist aktuell" in t for t in texts)


def test_manual_check_error_dialog(app):
    use_result(app, FAILED)
    app.check_updates_manual()
    assert pump(app, lambda: not app.update_checking)
    assert [e.title for e in app.shown_errors] == ["Update nicht möglich"]
    assert "Keine Verbindung" in app.shown_errors[0].detail


def test_opt_out_writes_config(app):
    from cwdecoder import config
    dlg = app.show_update_dialog(AVAILABLE)
    dlg.opt_out_var.set(True)
    dlg.later()
    saved = json.loads(config.get_config_path().read_text(encoding="utf-8"))
    assert saved["update_check"] is False
    assert app.cfg["update_check"] is False


def test_download_and_install(app, tmp_path):
    from cwdecoder.instance_lock import InstanceLock
    lock = InstanceLock(tmp_path / "x.lock")
    assert lock.acquire()
    app.instance_lock = lock
    installer = tmp_path / "setup.exe"

    def fake_download(asset, on_progress=None):
        on_progress(1_000_000, asset.size)
        on_progress(asset.size, asset.size)
        installer.write_bytes(b"MZ")
        return installer

    dlg = app.show_update_dialog(AVAILABLE)
    dlg.download = fake_download
    dlg.start_download()
    assert pump(app, lambda: app.launched)
    assert app.launched[0][0] == installer
    assert app.launched[0][1] == app._quit
    assert not lock.owned and not (tmp_path / "x.lock").exists()
    assert app.update_dialog is None and dlg.closed


def test_download_error_shown_in_dialog(app):
    def failing(asset, on_progress=None):
        raise UpdateError("Die Setup-Datei ist unvollständig")

    dlg = app.show_update_dialog(AVAILABLE)
    dlg.download = failing
    dlg.start_download()
    assert pump(app, lambda: "unvollständig" in dlg.info_var.get())
    assert str(dlg.btn_install.cget("state")) == "normal"
    assert app.launched == []


def test_update_dialog_has_tooltips(app):
    from cwdecoder import gui_update
    names = [n for n in vars(gui_update) if n.startswith(("_LBL_", "_MSG_", "_TT_"))]
    assert len([n for n in names if n.startswith("_TT_")]) >= 4

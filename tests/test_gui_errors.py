# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""Fehlerzuordnung (ADR-0007)."""
import errno

import pytest

from conftest import requires_display
from cwdecoder.config import ConfigError
from cwdecoder.gui_errors import classify_error
from cwdecoder.live import AudioDeviceError
from cwdecoder.n1mm import EntryWindowNotFoundError, PortInUseError
from cwdecoder.updater import UpdateError


class PortAudioError(Exception):
    """Nachbau von sounddevice.PortAudioError (gleicher Klassenname)."""


@pytest.mark.parametrize("exc, title", [
    (AudioDeviceError("Invalid sample rate"), "Soundkarte nicht verfügbar"),
    (PortAudioError("Device unavailable"), "Soundkarte nicht verfügbar"),
    (PortInUseError("UDP-Port 12060 belegt"), "Port belegt"),
    (OSError(errno.EADDRINUSE, "Address already in use"), "Port belegt"),
    (EntryWindowNotFoundError("Entry Window nicht gefunden"), "N1MM-Fenster nicht gefunden"),
    (ConfigError("kein gültiges JSON"), "Einstellungen ungültig"),
    (UpdateError("Keine Verbindung zu GitHub"), "Update nicht möglich"),
])
def test_expected_errors(exc, title):
    info = classify_error(exc)
    assert info.title == title
    assert info.expected is True
    assert info.message and info.status
    assert "Traceback" not in (info.detail or "")
    assert str(exc) in (info.detail or "")


def test_windows_addr_in_use():
    exc = OSError("Normalerweise darf jede Socketadresse nur einmal verwendet werden")
    exc.winerror = 10048
    assert classify_error(exc).title == "Port belegt"


def test_other_oserror_is_unexpected():
    assert classify_error(OSError(errno.ENOENT, "fehlt")).expected is False


def test_unexpected_has_traceback():
    try:
        raise ValueError("kaputt")
    except ValueError as e:
        info = classify_error(e)
    assert info.title == "Unerwarteter Fehler"
    assert info.expected is False
    assert "ValueError: kaputt" in info.message
    assert "Traceback" in info.detail and "kaputt" in info.detail
    assert "Fehler melden" in info.message


@requires_display
@pytest.mark.gui
def test_show_error_dialog_with_details():
    import tkinter as tk
    from cwdecoder.gui_errors import show_error
    root = tk.Tk()
    try:
        dlg = show_error(root, "Titel", "Meldung", "Zeile 1\nZeile 2")
        root.update()
        assert dlg.winfo_exists() and dlg.title() == "Titel"
        dlg.destroy()
        dlg2 = show_error(root, "Ohne", "Meldung")
        root.update()
        dlg2.destroy()
    finally:
        root.destroy()

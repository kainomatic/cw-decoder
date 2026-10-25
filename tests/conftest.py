# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""Gemeinsame Fixtures für pytest.

app_env          biegt App-Ordner, Nutzerordner und Dokumente auf ein
                 Temp-Verzeichnis um, damit kein Test in echte Ordner schreibt.
requires_display Marker: Test überspringen, wenn kein Display vorhanden ist.
"""
import functools
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@functools.lru_cache(maxsize=1)
def display_available() -> bool:
    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        root.update_idletasks()
        root.destroy()
        return True
    except Exception:  # noqa: BLE001 - kein tkinter oder kein Display
        return False


requires_display = pytest.mark.skipif("not config._cw_display",
                                      reason="kein Display für tkinter")


def pytest_configure(config):
    config._cw_display = display_available()


@pytest.fixture
def app_env(tmp_path, monkeypatch):
    """Alle Ablageorte zeigen in tmp_path. Liefert tmp_path."""
    from cwdecoder import paths
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(paths.Path, "home", classmethod(lambda cls: home))
    monkeypatch.setattr(paths, "_known_documents_dir", lambda: None)
    return tmp_path

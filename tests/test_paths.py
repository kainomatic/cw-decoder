# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""Ablageorte (ADR-0003)."""
from pathlib import Path

from cwdecoder import paths


def test_app_dir_windows_stable_and_beta(app_env, monkeypatch):
    monkeypatch.setattr(paths, "_is_windows", lambda: True)
    stable = paths.get_app_dir("stable")
    beta = paths.get_app_dir("beta")
    assert stable == app_env / "appdata" / "CWDecoder"
    assert beta == app_env / "appdata" / "CWDecoder-Beta"
    assert stable.is_dir() and beta.is_dir()


def test_app_dir_linux_uses_xdg(app_env, monkeypatch):
    monkeypatch.setattr(paths, "_is_windows", lambda: False)
    assert paths.get_app_dir("stable") == app_env / "xdg" / "CWDecoder"


def test_app_dir_linux_fallback_config(app_env, monkeypatch):
    monkeypatch.setattr(paths, "_is_windows", lambda: False)
    monkeypatch.delenv("XDG_CONFIG_HOME")
    assert paths.get_app_dir("stable") == app_env / "home" / ".config" / "CWDecoder"


def test_log_dir_below_app_dir(app_env, monkeypatch):
    monkeypatch.setattr(paths, "_is_windows", lambda: True)
    d = paths.get_log_dir()
    assert d.parent == paths.get_app_dir() and d.name == "logs" and d.is_dir()


def test_recordings_dir_windows_fallback_userprofile(app_env, monkeypatch):
    monkeypatch.setattr(paths, "_is_windows", lambda: True)
    d = paths.get_recordings_dir()
    assert d == app_env / "home" / "Documents" / "CW Decoder" / "Aufnahmen"
    assert d.is_dir()


def test_recordings_dir_windows_known_folder(app_env, monkeypatch, tmp_path):
    docs = tmp_path / "OneDrive" / "Dokumente"
    monkeypatch.setattr(paths, "_is_windows", lambda: True)
    monkeypatch.setattr(paths, "_known_documents_dir", lambda: docs)
    assert paths.get_recordings_dir() == docs / "CW Decoder" / "Aufnahmen"


def test_recordings_dir_linux_home(app_env, monkeypatch):
    monkeypatch.setattr(paths, "_is_windows", lambda: False)
    assert paths.get_recordings_dir() == app_env / "home" / "CW Decoder" / "Aufnahmen"


def test_recordings_not_in_repo_testdata(app_env):
    repo_testdata = Path(paths.__file__).resolve().parent.parent / "testdata"
    assert repo_testdata not in paths.get_recordings_dir().parents


def test_data_path_entwicklung_und_bundle(monkeypatch, tmp_path):
    """Mitgelieferte Daten: neben dem Paket bzw. unter sys._MEIPASS (ADR-0021)."""
    import sys
    from cwdecoder import paths
    assert paths.data_path("cty.dat").is_file()
    assert paths.data_path("flags", "de.png").is_file()
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert paths.data_path("cty.dat") == tmp_path / "cwdecoder" / "data" / "cty.dat"

# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""Einstieg der EXE (cwdecoder/app_main.py, ADR-0011)."""
import io
import sys

import pytest

from cwdecoder import app_main
from cwdecoder.__version__ import CHANNEL, __version__


def test_version(capsys):
    assert app_main.main(["--version"]) == 0
    assert capsys.readouterr().out.strip() == f"CW Decoder {__version__} ({CHANNEL})"


def test_decode(tmp_path, capsys):
    from scipy.io import wavfile
    from cwdecoder.gen import render
    wav = tmp_path / "t.wav"
    x = render("CQ TEST DE DL1ABC", fs=8000, wpm=25, snr_db=20, seed=3)
    wavfile.write(wav, 8000, (x * 32767 * 0.5).astype("int16"))
    assert app_main.main(["--decode", str(wav), "--expect", "CQ TEST DE DL1ABC"]) == 0
    out = capsys.readouterr().out
    assert "CQ TEST DE DL1ABC" in out and "Übereinstimmung" in out


def test_without_args_starts_gui(monkeypatch):
    pytest.importorskip("tkinter")
    calls = []
    monkeypatch.setattr("cwdecoder.gui_start.main", lambda argv: calls.append(argv))
    app_main.main([])
    app_main.main(["--n1mm"])
    assert calls == [[], ["--n1mm"]]


def test_unknown_args_rejected():
    with pytest.raises(SystemExit):
        app_main.main(["--gibtsnicht"])


def test_ensure_output_falls_back_to_file(app_env, monkeypatch):
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    monkeypatch.setattr(app_main, "_attach_parent_console", lambda: False)
    path = app_main.ensure_output()
    try:
        assert path is not None and path.name == "cli-ausgabe.txt"
        print("hallo")
        sys.stdout.flush()
        assert path.read_text(encoding="utf-8").strip() == "hallo"
    finally:
        sys.stdout.close()


def test_ensure_output_keeps_streams(monkeypatch):
    monkeypatch.setattr(sys, "stdout", io.StringIO())
    monkeypatch.setattr(sys, "stderr", io.StringIO())
    assert app_main.ensure_output() is None


def test_decode_missing_file_returns_error(tmp_path, capsys):
    """Kein unbehandelter Fehler: die Fenster-EXE würde sonst mit einem
    Dialog blockieren (CI hängt)."""
    assert app_main.main(["--decode", str(tmp_path / "fehlt.wav")]) == 1
    assert "Fehler:" in capsys.readouterr().err

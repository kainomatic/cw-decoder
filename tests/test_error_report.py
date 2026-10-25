# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""Fehlerbericht (ADR-0008): Inhalt, Bereinigung, URL — ohne Netz."""
import socket
import urllib.parse
from datetime import datetime
from pathlib import Path

import pytest

from cwdecoder import error_report as er


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Jeder Versuch, eine Verbindung aufzubauen, lässt den Test scheitern."""
    def forbidden(*_a, **_k):
        raise AssertionError("Netzzugriff im Test")
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)


@pytest.fixture
def log_file(tmp_path):
    p = tmp_path / "cwdecoder.log"
    p.write_text("\n".join(f"2026-10-26 12:00:00 INFO     cwdecoder: Zeile {i}"
                           for i in range(300)) + "\n", encoding="utf-8")
    return p


def test_report_contains_basics(log_file):
    text = er.build_error_report("0.1.0", "stable", log_file, "3: USB Audio CODEC, 48000 Hz",
                                 now=datetime(2026, 10, 26, 12, 0, 0))
    assert "0.1.0 (stable)" in text
    assert "3: USB Audio CODEC, 48000 Hz" in text
    assert "Python:" in text and "System:" in text
    assert "2026-10-26 12:00:00" in text
    # genau die letzten 200 Zeilen
    assert "Zeile 299" in text and "Zeile 100" in text and "Zeile 99\n" not in text
    assert text.count("cwdecoder: Zeile") == 200


def test_missing_and_empty_log(tmp_path):
    assert "kein Log" in er.build_error_report("0.1.0", "beta", tmp_path / "fehlt.log", "-")
    empty = tmp_path / "leer.log"
    empty.write_text("", encoding="utf-8")
    assert "leer" in er.build_error_report("0.1.0", "beta", empty, "-")


def test_sanitize_home_secrets_and_urls(tmp_path, monkeypatch):
    home = tmp_path / "Benutzer" / "Max Muster"
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setattr(er.Path, "home", classmethod(lambda cls: home))
    log = tmp_path / "x.log"
    log.write_text(
        f"INFO Aufnahme: {home}\\Documents\\CW Decoder\\Aufnahmen\\cw.wav\n"
        f"INFO Pfad klein: {str(home).lower()}\\x\n"
        "WARNING api_key=geheim123\n"
        "INFO Password: hunter2\n"
        "INFO Abruf https://nutzer:pw@example.org/pfad\n",
        encoding="utf-8")
    text = er.build_error_report("0.1.0", "stable", log, "-")
    assert "Max Muster" not in text and "max muster" not in text
    assert "~\\Documents\\CW Decoder" in text
    assert "geheim123" not in text and "hunter2" not in text
    assert "nutzer:pw" not in text and "https://[entfernt]@example.org/pfad" in text
    assert text.count("[Zeile entfernt") == 2


def test_issue_url_roundtrip():
    url, truncated = er.build_issue_url("Titel ä", "Text\nmit Umlaut ö & =",
                                        repo_url="https://github.com/kainomatic/cw-decoder")
    assert not truncated
    assert url.startswith("https://github.com/kainomatic/cw-decoder/issues/new?")
    q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    assert q["title"] == ["Titel ä"] and q["body"] == ["Text\nmit Umlaut ö & ="]


def test_issue_url_truncates_old_log_lines(log_file):
    body = er.build_error_report("0.1.0", "stable", log_file, "-", n_lines=300)
    url, truncated = er.build_issue_url("T", body, max_len=3000)
    assert truncated and len(url) <= 3000
    sent = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["body"][0]
    assert "Version:" in sent                   # Kopf bleibt
    assert "Zeile 299" in sent                  # neueste Zeilen bleiben
    assert "Zeile 0\n" not in sent              # älteste fliegen raus
    assert "gekürzt" in sent


def test_issue_url_truncates_without_log_marker():
    url, truncated = er.build_issue_url("T", "x" * 20000, max_len=2000)
    assert truncated and len(url) <= 2000


def test_open_in_browser_only_calls_webbrowser(monkeypatch):
    opened = []
    monkeypatch.setattr(er.webbrowser, "open", lambda u: opened.append(u) or True)
    assert er.open_in_browser("https://example.org") is True
    assert opened == ["https://example.org"]


def test_save_report(tmp_path):
    p = er.save_report("Bericht ü", tmp_path / "sub" / er.default_report_name(
        datetime(2026, 1, 2, 3, 4, 5)))
    assert p.name == "cw-decoder-fehlerbericht-20260102-030405.txt"
    assert Path(p).read_text(encoding="utf-8") == "Bericht ü"

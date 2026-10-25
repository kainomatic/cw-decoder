# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""Diagnose-Log (ADR-0004)."""
import logging
import sys
import threading
from logging.handlers import RotatingFileHandler

import pytest

from cwdecoder import logging_setup as ls


@pytest.fixture(autouse=True)
def clean_logger():
    ls.shutdown_logging()
    yield
    ls.shutdown_logging()
    logging.getLogger(ls.LOGGER_NAME).setLevel(logging.NOTSET)


def _handlers():
    return [h for h in logging.getLogger(ls.LOGGER_NAME).handlers
            if isinstance(h, RotatingFileHandler)]


def test_creates_log_file_with_rotation(tmp_path, monkeypatch):
    monkeypatch.delenv(ls.ENV_DEBUG, raising=False)
    d = ls.setup_logging(tmp_path / "logs")
    assert d == tmp_path / "logs"
    (h,) = _handlers()
    assert h.maxBytes == 1024 * 1024 and h.backupCount == 5
    assert logging.getLogger(ls.LOGGER_NAME).level == logging.INFO
    logging.getLogger("cwdecoder.test").info("Hallo Log")
    logging.getLogger("cwdecoder.test").debug("nicht sichtbar")
    h.flush()
    text = (d / "cwdecoder.log").read_text(encoding="utf-8")
    assert "Hallo Log" in text and "nicht sichtbar" not in text
    assert "cwdecoder.test" in text


def test_idempotent(tmp_path):
    d1 = ls.setup_logging(tmp_path)
    d2 = ls.setup_logging(tmp_path / "anderswo")
    assert d1 == d2 == tmp_path
    assert len(_handlers()) == 1


def test_env_debug(tmp_path, monkeypatch):
    monkeypatch.setenv(ls.ENV_DEBUG, "1")
    ls.setup_logging(tmp_path)
    assert logging.getLogger(ls.LOGGER_NAME).level == logging.DEBUG


@pytest.mark.parametrize("value, expected", [
    (None, False), ("", False), ("0", False), (" 0 ", False),
    ("1", True), ("yes", True),
])
def test_debug_requested(value, expected):
    assert ls.debug_requested(value) is expected


def test_default_dir_is_app_log_dir(app_env):
    d = ls.setup_logging()
    assert d.name == "logs" and str(app_env) in str(d)


def test_startup_line(tmp_path):
    from cwdecoder.__version__ import CHANNEL, __version__
    ls.setup_logging(tmp_path)
    ls.log_startup("Test")
    _handlers()[0].flush()
    text = (tmp_path / "cwdecoder.log").read_text(encoding="utf-8")
    assert f"Version {__version__}" in text and f"Kanal {CHANNEL}" in text


def test_exception_hooks_log_and_chain(tmp_path, monkeypatch):
    seen = []
    monkeypatch.setattr(sys, "excepthook", lambda *a: seen.append("sys"))
    monkeypatch.setattr(threading, "excepthook", lambda a: seen.append("thread"))
    ls.setup_logging(tmp_path)
    ls.install_exception_hooks()
    try:
        raise ValueError("Testfehler Hauptthread")
    except ValueError:
        sys.excepthook(*sys.exc_info())

    def boom():
        raise RuntimeError("Testfehler Thread")
    t = threading.Thread(target=boom, name="testthread")
    t.start()
    t.join()
    _handlers()[0].flush()
    text = (tmp_path / "cwdecoder.log").read_text(encoding="utf-8")
    assert "Testfehler Hauptthread" in text and "Traceback" in text
    assert "Testfehler Thread" in text and "testthread" in text
    assert seen == ["sys", "thread"]


def test_package_has_null_handler():
    import cwdecoder  # noqa: F401
    assert any(isinstance(h, logging.NullHandler)
               for h in logging.getLogger(ls.LOGGER_NAME).handlers)

# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""Diagnose-Log (ADR-0004).

setup_logging() einmal beim Programmstart aufrufen, vor allem anderen.
Konfiguriert den Logger "cwdecoder" mit einem RotatingFileHandler auf
<app_dir>/logs/cwdecoder.log (1 MB, 5 Backups). Module loggen über
logging.getLogger(__name__) und landen damit automatisch dort.

Level INFO; Umgebungsvariable CWDECODER_DEBUG=1 hebt auf DEBUG.
Nie loggen: Audiodaten (Samples, Blöcke).
"""
import logging
import os
import sys
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOGGER_NAME = "cwdecoder"
LOG_FILE = "cwdecoder.log"
MAX_BYTES = 1024 * 1024
BACKUP_COUNT = 5
ENV_DEBUG = "CWDECODER_DEBUG"
_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"
_DATEFMT = "%Y-%m-%d %H:%M:%S"


def debug_requested(env_value) -> bool:
    """True, wenn CWDECODER_DEBUG gesetzt und nicht leer/"0" ist."""
    return env_value is not None and env_value.strip() not in ("", "0")


def get_log_path(log_dir=None) -> Path:
    if log_dir is None:
        from .paths import get_log_dir
        log_dir = get_log_dir()
    return Path(log_dir) / LOG_FILE


def _file_handler(logger):
    for h in logger.handlers:
        if isinstance(h, RotatingFileHandler):
            return h
    return None


def setup_logging(log_dir=None, debug: bool = False) -> Path:
    """Richtet das Diagnose-Log ein und liefert den Log-Ordner.

    Idempotent: ein zweiter Aufruf fügt keinen weiteren Handler hinzu.
    log_dir None = Standard-Log-Ordner (paths.get_log_dir()).
    """
    logger = logging.getLogger(LOGGER_NAME)
    existing = _file_handler(logger)
    if existing is not None:
        return Path(existing.baseFilename).parent

    log_path = get_log_path(log_dir)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    level = logging.DEBUG if (debug or debug_requested(os.environ.get(ENV_DEBUG))) else logging.INFO

    handler = RotatingFileHandler(log_path, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT,
                                  encoding="utf-8")
    handler.setFormatter(logging.Formatter(_FORMAT, datefmt=_DATEFMT))
    handler.setLevel(level)
    logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False
    return log_path.parent


def shutdown_logging() -> None:
    """Datei-Handler schließen und entfernen (Tests, Programmende)."""
    logger = logging.getLogger(LOGGER_NAME)
    for h in list(logger.handlers):
        if isinstance(h, RotatingFileHandler):
            logger.removeHandler(h)
            h.close()


def install_exception_hooks() -> None:
    """Unbehandelte Ausnahmen (Hauptthread und andere Threads) ins Log
    schreiben. Die bisherigen Hooks laufen danach weiter (z. B. Ausgabe
    auf stderr im Terminal)."""
    log = logging.getLogger(LOGGER_NAME)
    prev_sys = sys.excepthook
    prev_thread = threading.excepthook

    def sys_hook(exc_type, exc, tb):
        if not issubclass(exc_type, KeyboardInterrupt):
            log.critical("Unbehandelte Ausnahme", exc_info=(exc_type, exc, tb))
        prev_sys(exc_type, exc, tb)

    def thread_hook(args):
        if args.exc_type is not SystemExit:
            name = args.thread.name if args.thread else "?"
            log.critical("Unbehandelte Ausnahme im Thread %s", name,
                         exc_info=(args.exc_type, args.exc_value, args.exc_traceback))
        prev_thread(args)

    sys.excepthook = sys_hook
    threading.excepthook = thread_hook


def log_startup(program: str) -> None:
    """Startzeile mit Version, Kanal, Python und Betriebssystem."""
    import platform
    from .__version__ import CHANNEL, __version__
    logging.getLogger(LOGGER_NAME).info(
        "%s gestartet: Version %s, Kanal %s, Python %s, %s",
        program, __version__, CHANNEL, platform.python_version(), platform.platform())

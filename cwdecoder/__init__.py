# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
import sys


def utf8_console():
    """stdout/stderr auf UTF-8 umstellen, damit Umlaute und ± in der
    Windows-Konsole (sonst cp1252/cp850) nicht verstümmelt werden."""
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


# Ohne setup_logging() (Tests, Bibliotheksnutzung) keine Ausgaben über den
# logging-Rückfall auf stderr; setup_logging() hängt den Datei-Handler an.
import logging as _logging  # noqa: E402

_logging.getLogger("cwdecoder").addHandler(_logging.NullHandler())

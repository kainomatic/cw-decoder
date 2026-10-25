import sys


def utf8_console():
    """stdout/stderr auf UTF-8 umstellen, damit Umlaute und ± in der
    Windows-Konsole (sonst cp1252/cp850) nicht verstümmelt werden."""
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

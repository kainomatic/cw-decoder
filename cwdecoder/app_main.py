# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""Einstieg der installierten EXE (CWDecoder.exe, ADR-0011).

    CWDecoder.exe                         Oberfläche
    CWDecoder.exe --n1mm                  Oberfläche, N1MM-Anbindung an
    CWDecoder.exe --decode datei.wav      WAV offline decodieren
                  [--expect TEXT] [--freq HZ] [--trace]
    CWDecoder.exe --list-devices          Audiogeräte auflisten
    CWDecoder.exe --version               Version und Kanal

Die EXE ist ein Fensterprogramm ohne eigene Konsole. Für die
Kommandozeilen-Modi hängt sie sich an die Konsole des Aufrufers; gibt es
keine (Start per Doppelklick o. ä.), landet die Ausgabe in
<App-Ordner>\\logs\\cli-ausgabe.txt. Umgeleitete Ausgabe (> datei) geht direkt.
"""
import argparse
import sys

from .__version__ import APP_NAME, CHANNEL, __version__

CLI_OUTPUT_FILE = "cli-ausgabe.txt"
_CLI_FLAGS = ("--decode", "--list-devices", "--version", "-h", "--help")


def _attach_parent_console() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        return bool(ctypes.windll.kernel32.AttachConsole(-1))   # ATTACH_PARENT_PROCESS
    except Exception:  # noqa: BLE001 - dann eben Datei
        return False


def ensure_output():
    """stdout/stderr bereitstellen, falls die EXE ohne Konsole läuft.

    Liefert den Pfad der Ausgabedatei oder None (Konsole/Umleitung)."""
    if sys.stdout is not None and sys.stderr is not None:
        return None
    if _attach_parent_console():
        try:
            stream = open("CONOUT$", "w", encoding="utf-8", errors="replace")  # noqa: SIM115
        except OSError:
            stream = None
        if stream is not None:
            sys.stdout = sys.stdout or stream
            sys.stderr = sys.stderr or stream
            print()     # Zeilenumbruch nach dem bereits gezeigten Prompt
            return None
    from .paths import get_log_dir
    path = get_log_dir() / CLI_OUTPUT_FILE
    stream = open(path, "w", encoding="utf-8", errors="replace")  # noqa: SIM115
    sys.stdout = sys.stdout or stream
    sys.stderr = sys.stderr or stream
    return path


def version_text() -> str:
    return f"{APP_NAME} {__version__} ({CHANNEL})"


def build_parser():
    p = argparse.ArgumentParser(prog="CWDecoder", description=f"{APP_NAME} {__version__}")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--decode", metavar="WAV", help="WAV-Datei offline decodieren")
    mode.add_argument("--list-devices", action="store_true", help="Audiogeräte auflisten")
    mode.add_argument("--version", action="store_true", help="Version anzeigen")
    p.add_argument("--n1mm", action="store_true", default=None,
                   help="Oberfläche: N1MM-Anbindung für diesen Lauf einschalten")
    return p


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if any(a.split("=")[0] in _CLI_FLAGS for a in argv):
        ensure_output()
    p = build_parser()
    a, rest = p.parse_known_args(argv)
    if a.version:
        print(version_text())
        return 0
    if a.list_devices:
        from . import utf8_console
        from .live import list_devices
        utf8_console()
        list_devices()
        return 0
    if a.decode:
        from .decode_wav import main as decode_main
        decode_main([a.decode] + rest)
        return 0
    if rest:
        p.error(f"unbekannte Argumente: {' '.join(rest)}")
    from .gui import main as gui_main
    gui_main(["--n1mm"] if a.n1mm else [])
    return 0

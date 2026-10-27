# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""Einstieg der installierten EXE (CWDecoder.exe, ADR-0011).

    CWDecoder.exe                         Oberfläche
    CWDecoder.exe --n1mm                  Oberfläche, N1MM-Anbindung an
    CWDecoder.exe --n1mm-engine           dazu Engine für N1MMs CW Reader
    CWDecoder.exe --xmlrpc-server-port N --wo --config-dir X -ti TITEL
                                          so startet N1MMs CW Reader seine
                                          „fldigi“-Engine; wirkt wie
                                          --n1mm-engine (ADR-0022)
    CWDecoder.exe --decode datei.wav      WAV offline decodieren
                  [--expect TEXT] [--freq HZ] [--trace]
    CWDecoder.exe --list-devices          Audiogeräte auflisten
    CWDecoder.exe --version               Version und Kanal
    CWDecoder.exe --dxcc RUFZEICHEN ...   Land zum Rufzeichen (cty.dat)
    CWDecoder.exe --scp RUFZEICHEN ...    in Super Check Partial? (bekannt /
                                          ähnlich: … / unbekannt)

Die EXE ist ein Fensterprogramm ohne eigene Konsole. Für die
Kommandozeilen-Modi hängt sie sich an die Konsole des Aufrufers; gibt es
keine (Start per Doppelklick o. ä.), landet die Ausgabe in
<App-Ordner>\\logs\\cli-ausgabe.txt. Umgeleitete Ausgabe (> datei) geht direkt.
"""
import argparse
import sys

from .__version__ import APP_NAME, CHANNEL, __version__

CLI_OUTPUT_FILE = "cli-ausgabe.txt"
_CLI_FLAGS = ("--decode", "--list-devices", "--version", "--dxcc", "--scp", "-h", "--help")


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
    mode.add_argument("--dxcc", metavar="RUFZEICHEN", nargs="+",
                      help="Land (DXCC-Entität) zu Rufzeichen anzeigen")
    mode.add_argument("--scp", metavar="RUFZEICHEN", nargs="+",
                      help="Rufzeichen in Super Check Partial nachschlagen")
    p.add_argument("--n1mm", action="store_true", default=None,
                   help="Oberfläche: N1MM-Anbindung für diesen Lauf einschalten")
    p.add_argument("--n1mm-engine", action="store_true",
                   help="Oberfläche mit Engine für N1MMs CW Reader (fldigi-Schnittstelle)")
    # Argumente, mit denen N1MM seine fldigi-Engine startet (Mitschnitt #3)
    p.add_argument("--xmlrpc-server-port", type=int, help=argparse.SUPPRESS)
    p.add_argument("-ti", "-title", dest="engine_title", help=argparse.SUPPRESS)
    return p


def engine_args(a):
    """Argumente für gui_start, wenn N1MM uns als Engine startet; sonst None."""
    if not (a.n1mm_engine or a.xmlrpc_server_port is not None or a.engine_title):
        return None
    args = ["--n1mm-engine"]
    if a.xmlrpc_server_port is not None:
        args += ["--xmlrpc-server-port", str(a.xmlrpc_server_port)]
    if a.engine_title:
        args += ["-ti", a.engine_title]
    return args


def _run_cli(a, rest) -> int:
    if a.version:
        print(version_text())
    elif a.dxcc:
        from . import utf8_console
        from .dxcc import format_lookup
        utf8_console()
        for call in a.dxcc + rest:
            print(format_lookup(call))
    elif a.scp:
        from . import utf8_console
        from .scp import format_check
        utf8_console()
        for call in a.scp + rest:
            print(format_check(call))
    elif a.list_devices:
        from . import utf8_console
        from .live import list_devices
        utf8_console()
        list_devices()
    else:
        from .decode_wav import main as decode_main
        decode_main([a.decode] + rest)
    return 0


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if any(a.split("=")[0] in _CLI_FLAGS for a in argv):
        ensure_output()
    p = build_parser()
    a, rest = p.parse_known_args(argv)
    if a.version or a.list_devices or a.decode or a.dxcc or a.scp:
        try:
            return _run_cli(a, rest)
        except Exception as e:  # noqa: BLE001 - sonst blockiert ein Fehlerfenster der EXE
            import traceback
            traceback.print_exc()
            print(f"Fehler: {e}", file=sys.stderr)
            return 1
    engine = engine_args(a)
    if rest and engine is None:
        p.error(f"unbekannte Argumente: {' '.join(rest)}")
    # leichter Start: Lock und Startfenster vor numpy/scipy (ADR-0020)
    from .gui_start import main as gui_main
    if engine is not None:
        # übrige fldigi-Argumente (--wo, --config-dir …) werden ignoriert
        gui_main(engine)
    else:
        gui_main(["--n1mm"] if a.n1mm else [])
    return 0

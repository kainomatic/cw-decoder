# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""Start der Oberfläche (ADR-0020): erst das Leichte, dann das Schwere.

Reihenfolge:
1. Logging, Startzeile, Zeitmessung ab Prozessstart.
2. Instanz-Lock. Läuft schon eine Instanz, holt diese zweite das Fenster
   der ersten nach vorn und beendet sich. Hat die erste noch kein Fenster
   (lädt noch), erscheint 5 s lang „CW Decoder startet gerade …".
   Startet N1MMs CW Reader uns als Engine (--n1mm-engine) und bietet die
   laufende Instanz die Engine nicht an, bittet die zweite die erste per
   Anforderungsdatei, sie für diesen Lauf einzuschalten, wartet bis 5 s
   auf den Port und endet ohne Dialog (ADR-0030).
3. Startfenster „CW Decoder startet …" (tkinter ist schnell).
4. Erst jetzt die schweren Imports (numpy, scipy, sounddevice über
   `cwdecoder.gui`), dann das Hauptfenster. Es ersetzt das Startfenster.

Jede Phase landet mit Zeit seit Prozessstart im Log („Startphase: …").
Dieses Modul importiert bewusst nur Standardbibliothek und leichte
Module des Pakets.
"""
import logging
import os
import socket
import sys
import time

from .__version__ import APP_NAME

log = logging.getLogger("cwdecoder.start")

# -- Texte -------------------------------------------------------------------
_MSG_SPLASH = "CW Decoder startet …"
_MSG_STARTING_TITLE = "CW Decoder"
_MSG_STARTING = "CW Decoder startet gerade, bitte einen Moment warten."
STARTING_NOTICE_MS = 5000
ENGINE_DEFAULT_PORT = 7367      # wie fldigi_rpc.DEFAULT_PORT (ohne dessen Imports)
ENGINE_DEFAULT_TITLE = "Fldigi CW Engine 1"   # wie fldigi_rpc.DEFAULT_TITLE
ENGINE_WAIT_S = 5.0             # so lange wartet die zweite Instanz auf den Port
ENGINE_WAIT_STEP_S = 0.2

_FILETIME_EPOCH = 116444736000000000   # 1601-01-01 -> 1970-01-01 in 100 ns


def process_start_epoch():
    """Startzeit dieses Prozesses (Unix-Sekunden) oder None."""
    from .instance_lock import process_info
    info = process_info(os.getpid())
    if info and info[0]:
        return (info[0] - _FILETIME_EPOCH) / 1e7
    return None


class StartTimer:
    """Zeit seit Prozessstart (inkl. Entpacken/Laden der EXE) je Phase loggen."""

    def __init__(self, t_start=None):
        self.t_start = t_start if t_start is not None else time.time()
        self.t_last = time.time()

    def phase(self, name: str) -> float:
        now = time.time()
        total, step = now - self.t_start, now - self.t_last
        self.t_last = now
        log.info("Startphase: %s nach %.2f s (+%.2f s)", name, total, step)
        return total


def find_app_window(pid: int):
    """Hauptfenster der Instanz mit dieser PID (Titel beginnt mit APP_NAME)."""
    from .n1mm import windows_of_pid
    for hwnd, title in windows_of_pid(pid):
        if title.startswith(APP_NAME):
            return hwnd, title
    return None


def handle_second_instance(other_pid, find=find_app_window, front=None, notice=None) -> str:
    """Zweite Instanz: erste nach vorn holen oder kurz „startet gerade" zeigen.

    Liefert "front" (Fenster gefunden) oder "notice" (noch kein Fenster)."""
    win = find(other_pid) if other_pid else None
    if win:
        if front is None:
            from .n1mm import bring_to_front as front
        ok = front(win[0])
        log.info("Zweite Instanz: Fenster der ersten (PID %s) nach vorn geholt: %s",
                 other_pid, "ok" if ok else "Fokussperre")
        return "front"
    log.info("Zweite Instanz: erste (PID %s) hat noch kein Fenster", other_pid)
    (notice or show_starting_notice)()
    return "notice"


def engine_listening(port: int, timeout: float = 0.5) -> bool:
    """Nimmt auf 127.0.0.1:port jemand Verbindungen an (Engine der ersten Instanz)?"""
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout):
            return True
    except OSError:
        return False


def request_engine_of_first(port: int, title: str, request_file, listening=None,
                            wait_s: float = ENGINE_WAIT_S, sleep=time.sleep,
                            clock=time.monotonic) -> str:
    """Zweite Instanz, von N1MM als Engine gestartet. Bietet die erste die
    Engine nicht an, bittet sie per Anforderungsdatei darum und wartet bis
    `wait_s` auf den Port. Nie ein Dialog: N1MM wartet auf diesen Prozess.

    Liefert "running" (lief schon), "started" (nach der Bitte erreichbar)
    oder "timeout" (die erste zeigt den Grund, z. B. Port belegt)."""
    from .engine_request import write_request
    listening = listening or engine_listening
    if listening(port):
        log.info("Zweite Instanz: Engine der ersten auf Port %d erreichbar", port)
        return "running"
    log.info("Zweite Instanz: erste bietet die Engine auf Port %d nicht an, "
             "bitte sie darum (Titel %r)", port, title)
    try:
        write_request(request_file, port, title)
    except OSError as e:
        log.error("Zweite Instanz: Engine-Anforderung nicht geschrieben: %s", e)
        return "timeout"
    t0 = clock()
    while clock() - t0 < wait_s:
        sleep(ENGINE_WAIT_STEP_S)
        if listening(port):
            log.info("Zweite Instanz: Engine der ersten nach %.1f s auf Port %d erreichbar",
                     clock() - t0, port)
            return "started"
    log.warning("Zweite Instanz: Engine der ersten nach %.1f s nicht erreichbar "
                "(Port %d); die erste zeigt den Grund", wait_s, port)
    return "timeout"


def show_starting_notice(ms: int = STARTING_NOTICE_MS, text: str = _MSG_STARTING):
    """Kleines Fenster ohne Knopf, schließt sich nach `ms` selbst."""
    import tkinter as tk
    root = tk.Tk()
    root.title(_MSG_STARTING_TITLE)
    root.resizable(False, False)
    tk.Label(root, text=text, padx=24, pady=18, wraplength=420, justify="left").pack()
    _center(root)
    try:
        root.attributes("-topmost", True)
    except tk.TclError:
        pass
    root.after(ms, root.destroy)
    root.mainloop()


def show_splash():
    """Startfenster ohne Rahmen, zentriert; None, wenn tk nicht will."""
    try:
        import tkinter as tk
        root = tk.Tk()
        root.overrideredirect(True)
        frm = tk.Frame(root, bg="#101418", padx=28, pady=20,
                       highlightthickness=1, highlightbackground="#4fd1c5")
        frm.pack()
        tk.Label(frm, text=_MSG_SPLASH, fg="#e6edf3", bg="#101418",
                 font=("Segoe UI", 13)).pack()
        _center(root)
        root.update()
        return root
    except Exception as e:  # noqa: BLE001 - ohne Startfenster geht es auch
        log.warning("Startfenster nicht möglich: %s", e)
        return None


def close_splash(splash):
    if splash is not None:
        try:
            splash.destroy()
        except Exception:  # noqa: BLE001
            pass


def _center(root):
    root.update_idletasks()
    w, h = root.winfo_reqwidth(), root.winfo_reqheight()
    x = (root.winfo_screenwidth() - w) // 2
    y = (root.winfo_screenheight() - h) // 3
    root.geometry(f"+{x}+{y}")


def main(argv=None):
    from . import utf8_console
    utf8_console()
    from .logging_setup import install_exception_hooks, log_startup, setup_logging
    setup_logging()
    install_exception_hooks()
    timer = StartTimer(process_start_epoch())
    log_startup("GUI")
    timer.phase("Logging bereit")
    import argparse
    p = argparse.ArgumentParser(description="CW Decoder – Oberfläche")
    p.add_argument("--n1mm", action="store_true", default=None,
                   help="N1MM-Anbindung für diesen Lauf einschalten (UDP 12060, Telnet 7373)")
    p.add_argument("--n1mm-engine", action="store_true",
                   help="zusätzlich Engine für N1MMs CW Reader (fldigi-Schnittstelle)")
    p.add_argument("--xmlrpc-server-port", type=int, help="Port der Engine (von N1MM)")
    p.add_argument("-ti", "-title", dest="engine_title", help="Fenstertitel (von N1MM)")
    a = p.parse_args(argv)
    engine = a.n1mm_engine or a.xmlrpc_server_port is not None or bool(a.engine_title)
    if engine:
        log.info("Start als Engine für N1MMs CW Reader: Port %s, Titel %r",
                 a.xmlrpc_server_port, a.engine_title)

    from .instance_lock import InstanceLock
    lock = InstanceLock()
    if not lock.acquire():
        if engine:
            # kein Hinweisfenster: N1MM wartet auf diesen Prozess (#30)
            handle_second_instance(lock.other_pid, notice=lambda: None)
            from .engine_request import REQUEST_FILE
            request_engine_of_first(a.xmlrpc_server_port or ENGINE_DEFAULT_PORT,
                                    a.engine_title or ENGINE_DEFAULT_TITLE,
                                    lock.path.parent / REQUEST_FILE)
        else:
            handle_second_instance(lock.other_pid)
        log.info("Zweite Instanz beendet sich")
        return
    timer.phase("Lock erworben")
    splash = show_splash()
    timer.phase("Startfenster sichtbar")
    try:
        t0 = time.time()
        from . import gui    # numpy, scipy, sounddevice
        log.info("Startphase: schwere Imports %.2f s", time.time() - t0)
        timer.phase("Imports fertig")
        if engine:
            gui.run_app(n1mm=a.n1mm, lock=lock, splash=splash, timer=timer,
                        engine_port=a.xmlrpc_server_port or ENGINE_DEFAULT_PORT,
                        engine_title=a.engine_title)
        else:
            gui.run_app(n1mm=a.n1mm, lock=lock, splash=splash, timer=timer)
    finally:
        close_splash(splash)
        lock.release()
        log.info("GUI beendet")


if __name__ == "__main__":
    sys.exit(main())

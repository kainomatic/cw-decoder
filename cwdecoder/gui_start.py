# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""Start der Oberfläche (ADR-0020): erst das Leichte, dann das Schwere.

Reihenfolge:
1. Logging, Startzeile, Zeitmessung ab Prozessstart.
2. Instanz-Lock. Läuft schon eine Instanz, holt diese zweite das Fenster
   der ersten nach vorn und beendet sich. Hat die erste noch kein Fenster
   (lädt noch), erscheint 5 s lang „CW Decoder startet gerade …".
3. Startfenster „CW Decoder startet …" (tkinter ist schnell).
4. Erst jetzt die schweren Imports (numpy, scipy, sounddevice über
   `cwdecoder.gui`), dann das Hauptfenster. Es ersetzt das Startfenster.

Jede Phase landet mit Zeit seit Prozessstart im Log („Startphase: …").
Dieses Modul importiert bewusst nur Standardbibliothek und leichte
Module des Pakets.
"""
import logging
import os
import sys
import time

from .__version__ import APP_NAME

log = logging.getLogger("cwdecoder.start")

# -- Texte -------------------------------------------------------------------
_MSG_SPLASH = "CW Decoder startet …"
_MSG_STARTING_TITLE = "CW Decoder"
_MSG_STARTING = "CW Decoder startet gerade, bitte einen Moment warten."
STARTING_NOTICE_MS = 5000

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


def show_starting_notice(ms: int = STARTING_NOTICE_MS):
    """Kleines Fenster ohne Knopf, schließt sich nach `ms` selbst."""
    import tkinter as tk
    root = tk.Tk()
    root.title(_MSG_STARTING_TITLE)
    root.resizable(False, False)
    tk.Label(root, text=_MSG_STARTING, padx=24, pady=18).pack()
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
    a = p.parse_args(argv)

    from .instance_lock import InstanceLock
    lock = InstanceLock()
    if not lock.acquire():
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
        gui.run_app(n1mm=a.n1mm, lock=lock, splash=splash, timer=timer)
    finally:
        close_splash(splash)
        lock.release()
        log.info("GUI beendet")


if __name__ == "__main__":
    sys.exit(main())

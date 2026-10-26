# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""Nur eine laufende GUI je Kanal (ADR-0010, gehärtet in ADR-0020).

InstanceLock schreibt in <App-Ordner>/cwdecoder.lock drei Zeilen:
PID, Startzeit des Prozesses (Windows-FILETIME) und Programmname. Eine
vorhandene Lockdatei gilt nur dann als „andere Instanz läuft", wenn

- der Prozess mit dieser PID noch läuft,
- sein Programm `CWDecoder.exe` ist (bzw. im Entwicklungsbetrieb
  `python*.exe`/`pythonw*.exe`) und
- seine Startzeit zur gespeicherten passt.

Sonst ist der Lock veraltet (Absturz, vom Installer beendet, PID von einem
anderen Programm wiederverwendet) und wird ohne Meldung übernommen.

    lock = InstanceLock(path)
    if not lock.acquire(): ...andere Instanz nach vorn holen, Ende...
    try: ...
    finally: lock.release()
"""
import logging
import os
import sys
from pathlib import Path

log = logging.getLogger(__name__)

LOCK_FILE = "cwdecoder.lock"
APP_EXE = "cwdecoder.exe"


def _kernel32():
    import ctypes
    from ctypes import wintypes
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.OpenProcess.restype = wintypes.HANDLE
    k.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    k.CloseHandle.argtypes = [wintypes.HANDLE]
    k.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    k.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD,
                                             wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    k.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    return k


def process_info(pid: int):
    """(Startzeit, Programmpfad) eines laufenden Prozesses, sonst None.

    Startzeit und Pfad sind None, wenn sie nicht lesbar sind (z. B. fremder
    Benutzer). Außerhalb von Windows nur die Lebend-Prüfung.
    """
    if pid <= 0:
        return None
    if sys.platform != "win32":
        return (None, None) if _pid_alive_posix(pid) else None
    import ctypes
    from ctypes import wintypes
    k = _kernel32()
    handle = k.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        # 5 = Zugriff verweigert: Prozess existiert, ist aber nicht prüfbar
        return (None, None) if ctypes.get_last_error() == 5 else None
    try:
        code = wintypes.DWORD()
        if k.GetExitCodeProcess(handle, ctypes.byref(code)) and code.value != 259:
            return None  # beendet (STILL_ACTIVE = 259)
        start = None
        times = [wintypes.FILETIME() for _ in range(4)]
        if k.GetProcessTimes(handle, *[ctypes.byref(t) for t in times]):
            start = (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime
        exe = None
        size = wintypes.DWORD(1024)
        buf = ctypes.create_unicode_buffer(1024)
        if k.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            exe = buf.value
        return start, exe
    finally:
        k.CloseHandle(handle)


def _pid_alive_posix(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def pid_alive(pid: int) -> bool:
    """Läuft ein Prozess mit dieser PID?"""
    # Bewusst nicht os.kill(pid, 0) unter Windows: Signal 0 ist dort
    # CTRL_C_EVENT und würde die Konsole des Prozesses unterbrechen.
    return process_info(pid) is not None


def is_our_program(exe) -> bool:
    """Gehört der Programmpfad zum CW Decoder (EXE oder Python im Dev-Betrieb)?"""
    if not exe:
        return False
    name = os.path.basename(exe).lower()
    return name == APP_EXE or (name.startswith("python") and name.endswith(".exe"))


def get_lock_path() -> Path:
    from .paths import get_app_dir
    return get_app_dir() / LOCK_FILE


def own_identity():
    """(PID, Startzeit, Programmname) dieses Prozesses für die Lockdatei."""
    info = process_info(os.getpid()) or (None, None)
    exe = info[1] or sys.executable or ""
    return os.getpid(), info[0], os.path.basename(exe)


def parse_lock(text: str):
    """(PID, Startzeit, Programmname) aus dem Inhalt; fehlende Teile None.

    Alte Lockdateien enthalten nur die PID."""
    lines = [ln.strip() for ln in text.splitlines()]
    try:
        pid = int(lines[0])
    except (IndexError, ValueError):
        return None, None, None
    start = None
    if len(lines) > 1 and lines[1].isdigit():
        start = int(lines[1])
    exe = lines[2] if len(lines) > 2 and lines[2] else None
    return pid, start, exe


def lock_holder_running(pid, start, exe, info_fn=process_info) -> bool:
    """Läuft die Instanz aus der Lockdatei wirklich noch?"""
    if pid is None or pid == os.getpid():
        return False
    info = info_fn(pid)
    if info is None:
        return False
    run_start, run_exe = info
    if run_exe is not None and not is_our_program(run_exe):
        return False        # PID gehört inzwischen einem anderen Programm
    if start is not None and run_start is not None and start != run_start:
        return False        # gleiche PID, aber ein neuerer Prozess
    if exe and run_exe and os.path.basename(run_exe).lower() != exe.lower():
        return False
    return True


class InstanceLock:
    def __init__(self, path=None, info_fn=process_info):
        self.path = Path(path) if path is not None else get_lock_path()
        self.owned = False
        self.other_pid = None   # PID der laufenden anderen Instanz
        self._info_fn = info_fn

    def _read(self):
        try:
            return parse_lock(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            return None, None, None

    def acquire(self) -> bool:
        """True = Lock gehört jetzt uns; False = andere Instanz läuft."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        for _ in range(3):
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                pid, start, exe = self._read()
                if lock_holder_running(pid, start, exe, self._info_fn):
                    self.other_pid = pid
                    log.info("Andere Instanz läuft bereits (PID %d)", pid)
                    return False
                log.info("Veralteter Lock (PID %s) wird übernommen", pid)
                try:
                    self.path.unlink()
                except FileNotFoundError:
                    pass
                except OSError as e:
                    log.error("Veralteter Lock nicht löschbar: %s", e)
                    return False
                continue
            pid, start, exe = own_identity()
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(f"{pid}\n{start if start is not None else ''}\n{exe}\n")
            self.owned = True
            return True
        return False

    def release(self) -> None:
        """Lock freigeben, aber nur den eigenen."""
        if not self.owned:
            return
        self.owned = False
        if self._read()[0] == os.getpid():
            try:
                self.path.unlink()
            except OSError as e:
                log.warning("Lock nicht gelöscht: %s", e)

    def __enter__(self):
        return self.acquire()

    def __exit__(self, *exc):
        self.release()

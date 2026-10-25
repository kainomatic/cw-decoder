# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""Nur eine laufende GUI je Kanal (ADR-0010).

InstanceLock schreibt die eigene PID in <App-Ordner>/cwdecoder.lock.
Läuft der Prozess aus einer vorhandenen Lockdatei noch, schlägt acquire()
fehl; ist er beendet (Absturz, Stromausfall), gilt der Lock als veraltet und
wird übernommen.

    lock = InstanceLock(path)
    if not lock.acquire(): ...Hinweis, Ende...
    try: ...
    finally: lock.release()
"""
import logging
import os
import sys
from pathlib import Path

log = logging.getLogger(__name__)

LOCK_FILE = "cwdecoder.lock"


def pid_alive(pid: int) -> bool:
    """Läuft ein Prozess mit dieser PID?"""
    if pid <= 0:
        return False
    if sys.platform == "win32":
        # Bewusst nicht os.kill(pid, 0): unter Windows ist Signal 0
        # CTRL_C_EVENT und würde die Konsole des Prozesses unterbrechen.
        import ctypes
        from ctypes import wintypes
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.restype = wintypes.HANDLE
        handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            # 5 = Zugriff verweigert: Prozess existiert, gehört aber jemand anderem
            return ctypes.get_last_error() == 5
        try:
            code = wintypes.DWORD()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                return True
            return code.value == 259  # STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def get_lock_path() -> Path:
    from .paths import get_app_dir
    return get_app_dir() / LOCK_FILE


class InstanceLock:
    def __init__(self, path=None):
        self.path = Path(path) if path is not None else get_lock_path()
        self.owned = False
        self.other_pid = None   # PID der laufenden anderen Instanz

    def _read_pid(self):
        try:
            return int(self.path.read_text(encoding="ascii").strip())
        except (OSError, ValueError):
            return None

    def acquire(self) -> bool:
        """True = Lock gehört jetzt uns; False = andere Instanz läuft."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        for _ in range(3):
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                pid = self._read_pid()
                if pid is not None and pid != os.getpid() and pid_alive(pid):
                    self.other_pid = pid
                    log.info("Andere Instanz läuft bereits (PID %d)", pid)
                    return False
                log.warning("Veralteter Lock (PID %s) wird übernommen", pid)
                try:
                    self.path.unlink()
                except FileNotFoundError:
                    pass
                except OSError as e:
                    log.error("Veralteter Lock nicht löschbar: %s", e)
                    return False
                continue
            with os.fdopen(fd, "w", encoding="ascii") as f:
                f.write(str(os.getpid()))
            self.owned = True
            return True
        return False

    def release(self) -> None:
        """Lock freigeben, aber nur den eigenen."""
        if not self.owned:
            return
        self.owned = False
        if self._read_pid() == os.getpid():
            try:
                self.path.unlink()
            except OSError as e:
                log.warning("Lock nicht gelöscht: %s", e)

    def __enter__(self):
        return self.acquire()

    def __exit__(self, *exc):
        self.release()

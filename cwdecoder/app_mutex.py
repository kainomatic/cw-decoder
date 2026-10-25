# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""Benannter Windows-Mutex, an dem der Installer eine laufende Instanz
erkennt (Inno Setup AppMutex, ADR-0012/ADR-0013).

    handle = create_app_mutex()   # beim Start, Handle bis Prozessende halten
    handle.close()                # vor dem Start des Update-Installers

Nicht fatal: Außerhalb von Windows oder bei einem Fehler gibt es None und
eine Zeile im Log. Ergänzt das PID-Lockfile (ADR-0010), ersetzt es nicht.
"""
import logging
import sys

from .__version__ import CHANNEL

log = logging.getLogger(__name__)

MUTEX_NAMES = {"stable": "CWDecoder-Stable", "beta": "CWDecoder-Beta"}


def mutex_name(channel=CHANNEL) -> str:
    return MUTEX_NAMES["beta" if channel == "beta" else "stable"]


def _kernel32():
    import ctypes
    from ctypes import wintypes
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.CreateMutexW.restype = wintypes.HANDLE
    k.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
    k.OpenMutexW.restype = wintypes.HANDLE
    k.OpenMutexW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
    k.CloseHandle.argtypes = [wintypes.HANDLE]
    return k


class AppMutex:
    def __init__(self, name, handle):
        self.name = name
        self.handle = handle

    def close(self):
        if self.handle:
            _kernel32().CloseHandle(self.handle)
            log.debug("AppMutex freigegeben: %s", self.name)
            self.handle = None


def create_app_mutex(channel=CHANNEL):
    """Mutex anlegen; AppMutex oder None."""
    name = mutex_name(channel)
    if sys.platform != "win32":
        return None
    try:
        handle = _kernel32().CreateMutexW(None, False, name)
    except Exception as e:  # noqa: BLE001 - nicht fatal
        log.warning("AppMutex %s nicht angelegt: %s", name, e)
        return None
    if not handle:
        import ctypes
        log.warning("AppMutex %s nicht angelegt (Fehler %d)", name, ctypes.get_last_error())
        return None
    log.debug("AppMutex angelegt: %s", name)
    return AppMutex(name, handle)


def mutex_exists(name) -> bool:
    """Gibt es den Mutex gerade (z. B. weil eine Instanz läuft)? Für Tests."""
    if sys.platform != "win32":
        return False
    k = _kernel32()
    h = k.OpenMutexW(0x00100000, False, name)   # SYNCHRONIZE
    if not h:
        return False
    k.CloseHandle(h)
    return True

# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
r"""Ablageorte des Programms (ADR-0003).

get_app_dir()         Config, Log, Lockfile; Windows: %APPDATA%\CWDecoder
                      (Beta: CWDecoder-Beta), sonst ~/.config/CWDecoder.
get_log_dir()         <app_dir>/logs
get_recordings_dir()  WAV-Aufnahmen; Windows: Dokumente\CW Decoder\Aufnahmen,
                      sonst ~/CW Decoder/Aufnahmen. Bewusst ein sichtbarer
                      Ordner: Nutzer schicken Aufnahmen zur Analyse weiter.
open_folder(path)     Ordner im Explorer bzw. Dateimanager öffnen.

Alle get_*-Funktionen legen den Ordner an.
"""
import os
import subprocess
import sys
from pathlib import Path

from .__version__ import CHANNEL

APP_FOLDER = "CWDecoder"
RECORDINGS_PARENT = "CW Decoder"
RECORDINGS_FOLDER = "Aufnahmen"


def _is_windows() -> bool:
    return sys.platform == "win32"


def _app_folder_name(channel: str = CHANNEL) -> str:
    return APP_FOLDER + ("-Beta" if channel == "beta" else "")


def _known_documents_dir():
    """Echter Dokumente-Ordner per SHGetKnownFolderPath (berücksichtigt
    Umleitung, z. B. auf OneDrive). None, wenn das nicht klappt."""
    if not _is_windows():
        return None
    try:
        import ctypes
        from ctypes import wintypes
        import uuid

        class GUID(ctypes.Structure):
            _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                        ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8)]

        u = uuid.UUID("{FDD39AD0-238F-46AF-ADB4-6C85480369C7}")  # FOLDERID_Documents
        guid = GUID(u.fields[0], u.fields[1], u.fields[2],
                    (ctypes.c_ubyte * 8).from_buffer_copy(u.bytes[8:]))
        out = ctypes.c_wchar_p()
        shell32 = ctypes.windll.shell32
        if shell32.SHGetKnownFolderPath(ctypes.byref(guid), 0, None, ctypes.byref(out)) != 0:
            return None
        try:
            return Path(out.value) if out.value else None
        finally:
            ctypes.windll.ole32.CoTaskMemFree(out)
    except Exception:  # noqa: BLE001 - Fallback statt Absturz
        return None


def get_app_dir(channel: str = CHANNEL) -> Path:
    if _is_windows():
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    d = base / _app_folder_name(channel)
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_log_dir() -> Path:
    d = get_app_dir() / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_recordings_dir() -> Path:
    if _is_windows():
        docs = _known_documents_dir()
        if docs is None:
            home = Path(os.environ.get("USERPROFILE") or Path.home())
            docs = home / "Documents"
        d = docs / RECORDINGS_PARENT / RECORDINGS_FOLDER
    else:
        d = Path.home() / RECORDINGS_PARENT / RECORDINGS_FOLDER
    d.mkdir(parents=True, exist_ok=True)
    return d


def open_folder(path) -> None:
    """Ordner im Explorer bzw. Dateimanager öffnen. Wirft OSError bei Fehler."""
    path = str(path)
    if _is_windows():
        os.startfile(path)  # noqa: S606 - nur lokaler Ordner
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])

# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""Anbindung an N1MM Logger+.

Vier Bausteine:

1. RadioInfoListener
   Empfängt die UDP-Broadcasts von N1MM (Config > Configure Ports > Broadcast
   Data, Standard-Port 12060) und kennt damit Frequenz, Mode und eigenes
   Rufzeichen. Wird für die Anzeige und für sinnvolle Spots gebraucht.

2. EntryWindowTyper  (Windows)
   Schreibt ein Rufzeichen per Tastatur-Emulation in das N1MM Entry Window.
   N1MM hat laut Doku keine UDP-Schnittstelle zum Setzen des Rufzeichens
   (eingehend werden nur Spektrumdaten und QSY-Befehle auf Port 13064
   akzeptiert), deshalb der Weg über das Fenster. Optional wird vorher mit
   Alt+W (Wipe) das Feld geleert.

3. SpotServer
   Ein Mini-"DX-Cluster" per Telnet, mit dem sich N1MM verbindet (Telnet-
   Fenster, Adresse 127.0.0.1 Port 7373). Erkannte Rufzeichen werden als
   Skimmer-Spots auf der aktuellen Frequenz gesendet und erscheinen in der
   Bandmap; ein Klick darauf in N1MM übernimmt Rufzeichen und Frequenz.
   Das ist der "saubere" Weg, der ohne Fenster-Fokus auskommt.

4. FldigiRpcServer (cwdecoder/fldigi_rpc.py, ADR-0022)
   Engine hinter N1MMs Fenster "CW Reader" über die nachgebildete
   fldigi-Schnittstelle (eigener Name, #13). N1MM zeigt
   unseren Text und übernimmt angeklickte Rufzeichen selbst ins Entry
   Window. Standardweg; braucht bei uns keinen Klick.

N1MMBridge bündelt alles. Welche Wege ein Klick auf ein Rufzeichen auslöst,
ist einzeln schaltbar (engine, spot, type_call, clipboard).
"""
import logging
import re
import socket
import sys
import threading
import time
import xml.etree.ElementTree as ET

log = logging.getLogger(__name__)


class PortInUseError(OSError):
    """UDP- oder Telnet-Port ist schon belegt (Decoder doppelt gestartet?)."""


class EnginePortInUseError(PortInUseError):
    """XML-RPC-Port der CW-Reader-Engine belegt (läuft fldigi?)."""


class EntryWindowNotFoundError(RuntimeError):
    """N1MM-Fenster bzw. Entry Window nicht gefunden."""


class SpotNotSentError(RuntimeError):
    """Skimmer-Spot nicht gesendet: kein Telnet-Client oder keine Frequenz."""


# --------------------------------------------------------------------------
class RadioState:
    """Letzter Stand eines Radios aus den RadioInfo-Paketen."""

    def __init__(self, nr: int):
        self.nr = nr
        self.freq_khz = None
        self.mode = None
        self.entry_hwnd = None      # EntryWindowHwnd: Entry Window dieses Radios
        self.last_rx = 0.0


def _int_or_none(text: str):
    """Zahl aus einem RadioInfo-Feld (dezimal, auch 0x…); leer/ungültig -> None."""
    text = (text or "").strip()
    if not text:
        return None
    try:
        return int(text, 0) if text.lower().startswith("0x") else int(text)
    except ValueError:
        return None


class RadioInfoListener(threading.Thread):
    """RadioInfo-Broadcasts von N1MM (UDP 12060).

    Bei SO2R/SO2V schickt N1MM ein Paket je Radio (alle 10 s und bei jeder
    Änderung). Die Werte stehen deshalb je RadioNr in self.radios; „das
    Radio“ für Anzeige, Spot-Frequenz und Eintippen ist das Fokus-Radio
    (FocusRadioNr, grüner Punkt in N1MM), ohne das Feld Radio 1 (#31)."""

    def __init__(self, port: int = 12060, on_update=None):
        super().__init__(daemon=True)
        self.port = port
        self.on_update = on_update or (lambda info: None)
        self.radios = {}            # RadioNr -> RadioState
        self.focus_nr = None        # FocusRadioNr aus dem jüngsten Paket
        self.focus_entry = None     # FocusEntry: Entry Window mit dem Fokus
        self.mycall = None
        self.last_rx = 0.0
        self.sock = None
        self.error = None
        self._stop_evt = threading.Event()

    def bind(self) -> bool:
        """Port sofort binden (ohne SO_REUSEADDR: ein belegter Port soll
        auffallen statt still geteilt zu werden). False -> self.error."""
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        try:
            s.bind(("", self.port))
        except OSError as e:
            s.close()
            self.error = (f"UDP-Port {self.port} belegt – Decoder doppelt gestartet "
                          f"oder anderes Programm empfängt N1MM-Broadcasts?")
            log.warning("%s (%s)", self.error, e)
            return False
        self.sock = s
        return True

    def run(self):
        if self.sock is None and not self.bind():
            return
        s = self.sock
        while not self._stop_evt.is_set():
            try:
                data, _ = s.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError:
                break
            self._parse(data)
        s.close()

    def _parse(self, data: bytes):
        try:
            root = ET.fromstring(data.decode("utf-8", errors="replace"))
        except ET.ParseError:
            return
        if root.tag != "RadioInfo":
            return
        g = lambda tag: (root.findtext(tag) or "").strip()  # noqa: E731
        nr = _int_or_none(g("RadioNr")) or 1
        st = self.radios.get(nr)
        if st is None:
            st = self.radios[nr] = RadioState(nr)
        freq = _int_or_none(g("Freq"))
        if freq is not None:
            # N1MM sendet Freq in 10-Hz-Schritten (z. B. 1402500 = 14025.00 kHz)
            st.freq_khz = freq / 100.0
        st.mode = g("Mode") or st.mode
        st.entry_hwnd = _int_or_none(g("EntryWindowHwnd")) or st.entry_hwnd
        now = time.time()
        st.last_rx = now
        self.focus_nr = _int_or_none(g("FocusRadioNr")) or self.focus_nr
        self.focus_entry = _int_or_none(g("FocusEntry")) or self.focus_entry
        self.mycall = g("OpCall") or g("mycall") or self.mycall
        self.last_rx = now
        self.on_update(self)

    # -- das Radio (Fokus-Radio) ------------------------------------------
    @property
    def radio_nr(self) -> int:
        """Nummer des Fokus-Radios (ohne FocusRadioNr: 1)."""
        return self.focus_nr or 1

    @property
    def focus(self):
        """RadioState des Fokus-Radios oder None (noch kein Paket von ihm)."""
        return self.radios.get(self.radio_nr)

    @property
    def freq_khz(self):
        st = self.focus
        return st.freq_khz if st else None

    @property
    def mode(self):
        st = self.focus
        return st.mode if st else None

    @property
    def multi(self) -> bool:
        """Mehr als ein Radio meldet sich (SO2R/SO2V)."""
        return len(self.radios) > 1

    def entry_candidates(self):
        """Fenster-Handles fürs Eintippen, beste zuerst: EntryWindowHwnd des
        Fokus-Radios, dann FocusEntry."""
        st = self.focus
        out = []
        for h in ((st.entry_hwnd if st else None), self.focus_entry):
            if h and h not in out:
                out.append(h)
        return out

    def stop(self):
        self._stop_evt.set()
        if self.sock is not None:
            self.sock.close()   # Port sofort freigeben, weckt recvfrom auf
        if self.is_alive() and threading.current_thread() is not self:
            self.join(timeout=1.0)

    @property
    def connected(self) -> bool:
        return time.time() - self.last_rx < 30


# --------------------------------------------------------------------------
# Titel des N1MM+ Entry Window laut Doku/Screenshots auf n1mmwp.hamdocs.com:
#   "14053.63 CW Elecraft K3 VFO A"        (Frequenz kHz, Mode, Radio, VFO)
#   "21050.00+0.00 CW Elecraft K3 VFO A"   (mit RIT-Anteil)
#   "14200.00 USB Manual - VFO A"          (ohne CAT)
# Das zweite Entry Window (SO2V) hat "B" statt "A". Bei SO2R enden die Titel
# auf "Radio 1"/"Radio 2", oft mit Leerzeichen am Ende (Shack-Test #31):
#   "7040.32 CW Manual Radio 1 ", "21300.00 USB Manual Radio 2 "
# Die Bandmap heißt ähnlich ("Elecraft K3 VFO A", "Manual Radio 1",
# "Available Radio 1 …"), beginnt aber nicht mit einer Frequenz.
ENTRY_TITLE_RE = re.compile(
    r"^\s*\d{1,6}\.\d{1,3}(?:[+-]\d+(?:\.\d+)?)?\s+\S+.*"
    r"\b(?:VFO\s*([AB])|Radio\s*([12]))\s*$", re.I)


def _slot(which) -> int:
    """VFO A / Radio 1 -> 1, VFO B / Radio 2 -> 2."""
    return 2 if str(which).strip().upper() in ("B", "2") else 1


def pick_entry_window(windows, vfo="A", title_hint: str = ""):
    """Wählt aus [(hwnd, titel), ...] das Entry Window.

    1. Titel passt auf ENTRY_TITLE_RE, bevorzugt das gewünschte Fenster
       (vfo: "A"/"B" oder Radio 1/2; A und 1 sind das erste Entry Window)
    2. Fallback: Titel enthält title_hint (falls gesetzt)
    Sonst None – lieber nichts tippen als ins falsche Fenster.
    """
    want = _slot(vfo)
    matches = []
    for hwnd, title in windows:
        m = ENTRY_TITLE_RE.match(title or "")
        if m:
            slot = _slot(m.group(1) or m.group(2))
            matches.append((slot != want, hwnd, title))
    if matches:
        matches.sort(key=lambda t: t[0])    # gewünschter VFO zuerst, sonst stabil
        return matches[0][1], matches[0][2]
    if title_hint:
        for hwnd, title in windows:
            if title_hint.lower() in (title or "").lower():
                return hwnd, title
    return None


def _win32():
    """user32/kernel32 mit Signaturen (wichtig unter 64 Bit: HWND/HANDLE
    dürfen nicht auf c_int abgeschnitten werden)."""
    import ctypes
    from ctypes import wintypes
    u, k = ctypes.windll.user32, ctypes.windll.kernel32
    if getattr(u, "_cw_sig", False):
        return u, k
    u.IsWindowVisible.argtypes = [wintypes.HWND]
    u.IsWindow.argtypes = [wintypes.HWND]
    u.IsChild.argtypes = [wintypes.HWND, wintypes.HWND]
    u.GetGUIThreadInfo.argtypes = [wintypes.DWORD, ctypes.c_void_p]
    u.SendMessageTimeoutW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM,
                                      ctypes.c_void_p, wintypes.UINT, wintypes.UINT,
                                      ctypes.POINTER(ctypes.c_size_t)]
    u.SendMessageTimeoutW.restype = ctypes.c_ssize_t
    u.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    u.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    u.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    u.GetWindowThreadProcessId.restype = wintypes.DWORD
    u.GetForegroundWindow.restype = wintypes.HWND
    u.SetForegroundWindow.argtypes = [wintypes.HWND]
    u.BringWindowToTop.argtypes = [wintypes.HWND]
    u.IsIconic.argtypes = [wintypes.HWND]
    u.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    u.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
    k.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    k.OpenProcess.restype = wintypes.HANDLE
    k.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD,
                                             wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    k.CloseHandle.argtypes = [wintypes.HANDLE]
    k.GetCurrentThreadId.restype = wintypes.DWORD
    u._cw_sig = True
    return u, k


def _window_title(hwnd) -> str:
    import ctypes
    user32, _k = _win32()
    length = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value


def _exe_of_window(hwnd) -> str:
    """Programmpfad des Prozesses, dem das Fenster gehört ("" wenn unbekannt)."""
    import ctypes
    from ctypes import wintypes
    user32, kernel32 = _win32()
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    h = kernel32.OpenProcess(0x1000, False, pid.value)  # PROCESS_QUERY_LIMITED_INFORMATION
    exe = ""
    if h:
        size = wintypes.DWORD(1024)
        pbuf = ctypes.create_unicode_buffer(1024)
        if kernel32.QueryFullProcessImageNameW(h, 0, pbuf, ctypes.byref(size)):
            exe = pbuf.value
        kernel32.CloseHandle(h)
    return exe


def windows_of_pid(pid: int):
    """Sichtbare Top-Level-Fenster eines Prozesses: [(hwnd, titel)]."""
    if not sys.platform.startswith("win"):
        return []
    import ctypes
    from ctypes import wintypes
    user32, _kernel32 = _win32()
    found = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def enum_cb(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        owner = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value != pid:
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        found.append((hwnd, buf.value))
        return True

    user32.EnumWindows(enum_cb, 0)
    return found


def bring_to_front(hwnd, wait_s: float = 0.25) -> bool:
    """Fenster in den Vordergrund holen und prüfen, ob es geklappt hat.

    Windows erlaubt SetForegroundWindow nur dem Vordergrund-Prozess
    (Fokussperre). Darum der Reihe nach:
      1. einfach versuchen
      2. AttachThreadInput an den Thread des aktuellen Vordergrundfensters
      3. ALT antippen (gilt dann als letzte Eingabe dieses Prozesses)
    Erfolg nur, wenn GetForegroundWindow danach wirklich hwnd ist.
    """
    user32, kernel32 = _win32()

    def is_front():
        t_end = time.monotonic() + wait_s
        while True:
            if user32.GetForegroundWindow() == hwnd:
                return True
            if time.monotonic() >= t_end:
                return False
            time.sleep(0.02)

    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
    user32.SetForegroundWindow(hwnd)
    if is_front():
        log.info("Vordergrund: direkt")
        return True

    fg = user32.GetForegroundWindow()
    fg_tid = user32.GetWindowThreadProcessId(fg, None) if fg else 0
    my_tid = kernel32.GetCurrentThreadId()
    attached = bool(fg_tid and fg_tid != my_tid
                    and user32.AttachThreadInput(my_tid, fg_tid, True))
    try:
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
    finally:
        if attached:
            user32.AttachThreadInput(my_tid, fg_tid, False)
    if is_front():
        log.info("Vordergrund: per AttachThreadInput")
        return True

    VK_MENU, KEYUP = 0x12, 0x0002
    send_inputs([(VK_MENU, 0, 0), (VK_MENU, 0, KEYUP)])
    user32.SetForegroundWindow(hwnd)
    ok = is_front()
    log.info("Vordergrund: per ALT-Trick %s", "ok" if ok else "FEHLGESCHLAGEN")
    return ok


FOCUS_WAIT_S = 0.5      # so lange warten, bis N1MM den Tastaturfokus gesetzt hat
WIPE_WAIT_S = 0.4       # so lange darf Wipe bzw. das Leeren dauern


def scan_code(vk: int) -> int:
    """Scan-Code zur virtuellen Taste (MapVirtualKeyW); 0 außerhalb von Windows."""
    if not sys.platform.startswith("win"):
        return 0
    import ctypes
    return int(ctypes.windll.user32.MapVirtualKeyW(vk, 0)) & 0xFFFF


def focus_in_window(hwnd):
    """Fenster mit dem Tastaturfokus im GUI-Thread von hwnd, wenn es hwnd
    selbst oder ein Kind davon ist; sonst None (GetGUIThreadInfo)."""
    if not sys.platform.startswith("win"):
        return None
    import ctypes
    from ctypes import wintypes

    class GUITHREADINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("flags", wintypes.DWORD),
                    ("hwndActive", wintypes.HWND), ("hwndFocus", wintypes.HWND),
                    ("hwndCapture", wintypes.HWND), ("hwndMenuOwner", wintypes.HWND),
                    ("hwndMoveSize", wintypes.HWND), ("hwndCaret", wintypes.HWND),
                    ("rcCaret", wintypes.RECT)]

    user32, _k = _win32()
    tid = user32.GetWindowThreadProcessId(hwnd, None)
    info = GUITHREADINFO(cbSize=ctypes.sizeof(GUITHREADINFO))
    if not tid or not user32.GetGUIThreadInfo(tid, ctypes.byref(info)):
        return None
    focus = info.hwndFocus
    if focus and (focus == hwnd or user32.IsChild(hwnd, focus)):
        return focus
    return None


def window_text(hwnd) -> str:
    """Text eines (fremden) Steuerelements per WM_GETTEXT, 0,5 s Frist."""
    import ctypes
    from ctypes import wintypes
    user32, _k = _win32()
    res = ctypes.c_size_t()
    if not user32.SendMessageTimeoutW(hwnd, 0x000E, 0, None, 0x0002, 500, ctypes.byref(res)):
        return None
    n = res.value
    buf = ctypes.create_unicode_buffer(n + 1)
    if not user32.SendMessageTimeoutW(hwnd, 0x000D, n + 1, buf, 0x0002, 500, ctypes.byref(res)):
        return None
    return buf.value


def send_inputs(inputs):
    import ctypes
    from ctypes import wintypes
    PUL = ctypes.POINTER(ctypes.c_ulong)

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                    ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                    ("dwExtraInfo", PUL)]

    class INPUT(ctypes.Structure):
        class _I(ctypes.Union):
            _fields_ = [("ki", KEYBDINPUT), ("pad", ctypes.c_byte * 32)]
        _anonymous_ = ("i",)
        _fields_ = [("type", wintypes.DWORD), ("i", _I)]

    arr = (INPUT * len(inputs))()
    for n, (vk, scan, flags) in enumerate(inputs):
        arr[n].type = 1  # INPUT_KEYBOARD
        arr[n].ki = KEYBDINPUT(vk, scan, flags, 0, None)
    ctypes.windll.user32.SendInput(len(inputs), arr, ctypes.sizeof(INPUT))


def copy_to_clipboard(text: str) -> bool:
    """Text als Unicode in die Windows-Zwischenablage legen (ctypes, kein Tk
    nötig; bleibt auch nach Programmende erhalten)."""
    if not sys.platform.startswith("win"):
        return False
    import ctypes
    from ctypes import wintypes
    u, k = ctypes.windll.user32, ctypes.windll.kernel32
    u.OpenClipboard.argtypes = [wintypes.HWND]
    u.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    u.SetClipboardData.restype = wintypes.HANDLE
    k.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    k.GlobalAlloc.restype = ctypes.c_void_p
    k.GlobalLock.argtypes = [ctypes.c_void_p]
    k.GlobalLock.restype = ctypes.c_void_p
    k.GlobalUnlock.argtypes = [ctypes.c_void_p]
    k.GlobalFree.argtypes = [ctypes.c_void_p]
    CF_UNICODETEXT, GMEM_MOVEABLE = 13, 0x0002
    data = (text + "\0").encode("utf-16-le")
    for _ in range(10):             # Zwischenablage kann kurz von anderen belegt sein
        if u.OpenClipboard(None):
            break
        time.sleep(0.02)
    else:
        return False
    try:
        u.EmptyClipboard()
        h = k.GlobalAlloc(GMEM_MOVEABLE, len(data))
        if not h:
            return False
        p = k.GlobalLock(h)
        ctypes.memmove(p, data, len(data))
        k.GlobalUnlock(h)
        if not u.SetClipboardData(CF_UNICODETEXT, h):
            k.GlobalFree(h)         # gehört nur bei Erfolg dem System
            return False
        return True
    finally:
        u.CloseClipboard()


class EntryWindowTyper:
    """Tippt Text in das N1MM Entry Window (nur Windows, via ctypes/user32)."""

    def __init__(self, process_hint: str = "N1MMLogger", title_hint: str = "",
                 wipe: bool = True, vfo: str = "A"):
        self.process_hint = process_hint.lower()   # Teil des Exe-Namens (N1MMLogger.net.exe)
        self.title_hint = title_hint                # Fallback, falls der Titel anders aussieht
        self.vfo = vfo
        self.wipe = wipe
        self.available = sys.platform.startswith("win")
        self.last_titles = []                       # zuletzt gefundene Fenster des Prozesses
        self.last_error = None                      # Ausnahme des letzten Fehlschlags

    # -- Fenstersuche ------------------------------------------------------
    def process_windows(self):
        """Alle sichtbaren Top-Level-Fenster des N1MM-Prozesses: [(hwnd, titel)]."""
        if not self.available:
            return []
        import ctypes
        import os
        from ctypes import wintypes
        user32, _kernel32 = _win32()
        found = []

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def enum_cb(hwnd, _):
            if not user32.IsWindowVisible(hwnd):
                return True
            if self.process_hint in os.path.basename(_exe_of_window(hwnd)).lower():
                found.append((hwnd, _window_title(hwnd)))
            return True

        user32.EnumWindows(enum_cb, 0)
        return found

    def window_ok(self, hwnd) -> bool:
        """Handle aus dem Broadcast noch brauchbar: Fenster existiert und
        gehört zum N1MM-Prozess (Handles werden nach dem Schließen neu
        vergeben)."""
        if not (self.available and hwnd):
            return False
        import os
        user32, _k = _win32()
        if not user32.IsWindow(hwnd):
            return False
        return self.process_hint in os.path.basename(_exe_of_window(hwnd)).lower()

    def find_window(self, candidates=(), slot=None):
        """Entry Window: erst die Handles aus dem Broadcast (Fokus-Radio,
        dann FocusEntry), sonst Titelsuche mit Vorzug für `slot` (1/2,
        ohne Angabe self.vfo)."""
        for hwnd in candidates:
            if self.window_ok(hwnd):
                title = _window_title(hwnd)
                log.info("Entry Window per Handle %s: %r", hwnd, title)
                return hwnd, title
            log.info("Handle %s aus dem Broadcast ungültig, nächster Weg", hwnd)
        wins = self.process_windows()
        self.last_titles = [t for _, t in wins]
        log.info("%d Fenster von '%s': %s", len(wins), self.process_hint,
                 ", ".join(repr(t) for t in self.last_titles))
        win = pick_entry_window(wins, self.vfo if slot is None else slot, self.title_hint)
        if win:
            log.info("Entry Window per Titel: %r", win[1])
        return win

    # -- Tippen --------------------------------------------------------------
    def type_call(self, call: str, candidates=(), slot=None):
        """Rufzeichen ins Entry Window tippen. Liefert (ok, Meldung);
        bei Fehlschlag steht die Ursache zusätzlich in self.last_error.
        Wipe (Alt+W) geht an dasselbe Fenster wie das Rufzeichen."""
        self.last_error = None
        win = self.find_window(candidates, slot)
        if not win:
            if self.last_titles:
                msg = (f"Entry Window nicht erkannt ({len(self.last_titles)} N1MM-Fenster, "
                       f"Titel im Log)")
            else:
                msg = "Entry Window nicht gefunden (läuft N1MM?)"
            log.warning(msg)
            self.last_error = EntryWindowNotFoundError(msg)
            return False, msg
        hwnd, title = win
        if not self._bring_to_front(hwnd):
            msg = "N1MM ließ sich nicht in den Vordergrund holen (Windows-Fokussperre)"
            log.warning(msg)
            return False, msg
        # Erst tippen, wenn N1MM den Tastaturfokus wirklich in diesem Fenster
        # hat; sonst gehen Alt+W oder Buchstaben verloren (#31, Shack-Test).
        field = self._wait(lambda: self._focus_in(hwnd), FOCUS_WAIT_S)
        if not field:
            log.info("Tastaturfokus nach %.1f s nicht im Entry Window, tippe trotzdem",
                     FOCUS_WAIT_S)
        self._clear_field(hwnd)
        self._type_text(call)
        got = self._wait(lambda: self._field_text(self._focus_in(hwnd)) == call, WIPE_WAIT_S)
        if got:
            log.info("Rufzeichenfeld danach: %r", call)
        else:
            log.warning("Rufzeichenfeld danach: %r statt %r",
                        self._field_text(self._focus_in(hwnd)), call)
        return True, "ins Entry Window getippt"

    def _clear_field(self, hwnd):
        """Vor dem Tippen: Wipe (Alt+W, leert das ganze Entry Window und
        setzt den Fokus ins Rufzeichenfeld), dann prüfen. Steht danach noch
        etwas im Feld mit dem Fokus (Alt+W kam nicht an) oder ist Wipe aus,
        wird nur dieses Feld geleert: Pos1, Umschalt+Ende, Entf."""
        if self.wipe:
            self._key_combo_alt("W")
            if self._wait(lambda: self._field_empty(hwnd), WIPE_WAIT_S):
                log.info("Wipe: Rufzeichenfeld leer")
                return
            log.warning("Wipe (Alt+W) hat das Rufzeichenfeld nicht geleert, leere es selbst")
        elif self._field_empty(hwnd):
            return
        self._select_line_and_delete()
        if self._wait(lambda: self._field_empty(hwnd), WIPE_WAIT_S):
            log.info("Rufzeichenfeld selbst geleert")
        else:
            log.warning("Rufzeichenfeld ließ sich nicht leeren: %r",
                        self._field_text(self._focus_in(hwnd)))

    @staticmethod
    def _wait(cond, timeout: float, step: float = 0.02):
        """cond() bis timeout erfüllt? Liefert das letzte Ergebnis."""
        t_end = time.monotonic() + timeout
        while True:
            res = cond()
            if res or time.monotonic() >= t_end:
                return res
            time.sleep(step)

    def _field_empty(self, hwnd) -> bool:
        field = self._focus_in(hwnd)
        return bool(field) and self._field_text(field) == ""

    def _focus_in(self, hwnd):
        """Fensterhandle mit dem Tastaturfokus, wenn es im Fenster hwnd liegt."""
        return focus_in_window(hwnd)

    @staticmethod
    def _field_text(field):
        return window_text(field) if field else None

    def _bring_to_front(self, hwnd, wait_s: float = 0.25) -> bool:
        return bring_to_front(hwnd, wait_s)

    @staticmethod
    def _send_inputs(inputs):
        send_inputs(inputs)

    def _type_text(self, text: str):
        KEYEVENTF_UNICODE, KEYEVENTF_KEYUP = 0x0004, 0x0002
        seq = []
        for ch in text:
            seq.append((0, ord(ch), KEYEVENTF_UNICODE))
            seq.append((0, ord(ch), KEYEVENTF_UNICODE | KEYEVENTF_KEYUP))
        self._send_inputs(seq)

    def _key_combo_alt(self, letter: str):
        """Alt+Buchstabe mit Scan-Codes wie von einer echten Tastatur."""
        VK_MENU, KEYUP = 0x12, 0x0002
        vk = ord(letter.upper())
        alt, key = scan_code(VK_MENU), scan_code(vk)
        self._send_inputs([(VK_MENU, alt, 0), (vk, key, 0), (vk, key, KEYUP),
                           (VK_MENU, alt, KEYUP)])

    def _select_line_and_delete(self):
        """Pos1, Umschalt+Ende, Entf: leert das Feld mit dem Fokus."""
        KEYUP, EXT = 0x0002, 0x0001
        VK_SHIFT, VK_HOME, VK_END, VK_DELETE = 0x10, 0x24, 0x23, 0x2E
        seq = []
        for vk, flags in ((VK_HOME, EXT), (VK_SHIFT, 0), (VK_END, EXT)):
            seq.append((vk, scan_code(vk), flags))
            if vk != VK_SHIFT:
                seq.append((vk, scan_code(vk), flags | KEYUP))
        seq.append((VK_SHIFT, scan_code(VK_SHIFT), KEYUP))
        seq += [(VK_DELETE, scan_code(VK_DELETE), EXT),
                (VK_DELETE, scan_code(VK_DELETE), EXT | KEYUP)]
        self._send_inputs(seq)


# --------------------------------------------------------------------------
class SpotServer(threading.Thread):
    """Minimaler Telnet-Cluster. N1MM: Telnet-Fenster -> 127.0.0.1:7373."""

    def __init__(self, port: int = 7373, spotter_call: str = "CWDEC"):
        super().__init__(daemon=True)
        self.port = port
        self.spotter_call = spotter_call
        self.clients = []       # eingeloggte Clients (bekommen Spots)
        self._conns = set()     # alle offenen Verbindungen, auch beim Login
        self.srv = None
        self.error = None
        self._lock = threading.Lock()
        self._stop_evt = threading.Event()

    def bind(self) -> bool:
        """Port sofort binden (ohne SO_REUSEADDR). False -> self.error."""
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            srv.bind(("127.0.0.1", self.port))
        except OSError as e:
            srv.close()
            self.error = f"Telnet-Port {self.port} belegt – Decoder doppelt gestartet?"
            log.warning("%s (%s)", self.error, e)
            return False
        srv.listen(2)
        srv.settimeout(0.5)
        self.srv = srv
        return True

    def run(self):
        if self.srv is None and not self.bind():
            return
        srv = self.srv
        while not self._stop_evt.is_set():
            try:
                conn, _ = srv.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            threading.Thread(target=self._serve_client, args=(conn,), daemon=True).start()
        srv.close()

    def _serve_client(self, conn):
        with self._lock:
            if self._stop_evt.is_set():
                conn.close()
                return
            self._conns.add(conn)
        try:
            # Spots gehen ab dem Verbindungsaufbau raus: N1MM sendet ohne
            # „Automatically Logon" kein Rufzeichen und wartet nur (#3)
            with self._lock:
                conn.sendall(b"login: ")
                self.clients.append(conn)
            data, greeted = b"", False
            # Verbindung offen halten; die erste Zeile gilt als Login, der Rest
            # wird ignoriert
            while not self._stop_evt.is_set():
                chunk = conn.recv(256)
                if not chunk:
                    break
                if greeted:
                    continue
                data += chunk
                if b"\n" in data:
                    greeted = True
                    call = data.decode(errors="replace").strip().upper() or "N1MM"
                    with self._lock:
                        conn.sendall(f"Hello {call}, this is the CW decoder spot feed.\r\n"
                                     f"{call} de {self.spotter_call} >\r\n".encode())
        except OSError:
            pass
        finally:
            with self._lock:
                if conn in self.clients:
                    self.clients.remove(conn)
                self._conns.discard(conn)
            conn.close()

    def spot(self, call: str, freq_khz: float, snr_db: float = 20, wpm: float = 25,
             comment: str = "CQ"):
        if not freq_khz:
            return False
        t = time.strftime("%H%MZ", time.gmtime())
        line = (f"DX de {self.spotter_call}-#:{freq_khz:9.1f}  {call:<12} CW {int(snr_db):3d} dB "
                f"{int(wpm):3d} WPM {comment:<4} {t}\r\n")
        sent = False
        with self._lock:
            for c in list(self.clients):
                try:
                    c.sendall(line.encode())
                    sent = True
                except OSError:
                    self.clients.remove(c)
        return sent

    def stop(self):
        self._stop_evt.set()
        if self.srv is not None:
            self.srv.close()    # Port sofort freigeben, weckt accept auf
        # alle Clients trennen; shutdown weckt die blockierenden recv() auf
        with self._lock:
            conns = list(self._conns)
            self.clients.clear()
            self._conns.clear()
        for c in conns:
            try:
                c.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            c.close()
        if self.is_alive() and threading.current_thread() is not self:
            self.join(timeout=1.0)


# --------------------------------------------------------------------------
_MSG_TYPED_FALLBACK = "in der Zwischenablage – Strg+V in N1MM"
_MSG_CLIPBOARD = "in der Zwischenablage"
_MSG_SPOTTED = "als Spot auf {freq:.1f} kHz gesendet"
_MSG_NO_SPOT_FREQ = "kein Spot: Frequenz von N1MM unbekannt (Broadcast Radio, UDP 12060)"
_MSG_NO_SPOT_CLIENT = "kein Spot: kein Telnet-Client verbunden (127.0.0.1:{port})"
_MSG_ENGINE_ONLY = "im CW Reader von N1MM anklicken"
_MSG_NO_WAY = "kein Übergabeweg gewählt"


class N1MMBridge:
    """Bündelt die Anbindung an N1MM.

    Immer: Frequenz von N1MM lesen (RadioInfo, UDP). Wählbar:
      engine     Engine für N1MMs CW Reader (XML-RPC wie fldigi, Standard an)
      spot       Skimmer-Spot über den Telnet-Cluster (Standard an)
      type_call  Rufzeichen ins Entry Window tippen (Standard aus)
      clipboard  Rufzeichen in die Zwischenablage (Standard aus; beim
                 Tippen auch Rückfallweg, wenn das Tippen scheitert)
    Ein Klick auf ein Rufzeichen (send_call) löst spot/type_call/clipboard
    aus; den Engine-Weg bedient N1MM selbst (Klick im CW Reader)."""

    def __init__(self, udp_port: int = 12060, spot_port: int = 7373,
                 rpc_port: int = None, engine: bool = True, spot: bool = True,
                 type_call: bool = False, clipboard: bool = False, wipe: bool = True,
                 engine_title: str = None):
        from .fldigi_rpc import DEFAULT_PORT, DEFAULT_TITLE
        self.spot_port = spot_port
        self.rpc_port = int(rpc_port or DEFAULT_PORT)
        self.engine_title = engine_title or DEFAULT_TITLE
        self._errors = {}       # Baustein -> Klartext (z. B. Port belegt)
        # Ausnahme, wenn die letzte Übergabe N1MM auf keinem Weg erreicht hat
        self.last_failure = None
        self.carrier_hz = None  # Tonfrequenz für modem.get_carrier (setzt die GUI)
        self.radio = RadioInfoListener(udp_port)
        if self.radio.bind():
            self.radio.start()
        else:
            self._errors["radio"] = self.radio.error
        self.typer = EntryWindowTyper(wipe=wipe)
        self.spots = None
        self.engine = None
        self.use_type = self.use_clipboard = False
        # Ausnahmen der Bausteine, die beim Start nicht liefen (Port belegt)
        self.start_failures = [PortInUseError(self.radio.error)] if self.radio.error else []
        self.start_failures += self.configure(engine=engine, spot=spot, type_call=type_call,
                                              clipboard=clipboard, wipe=wipe)

    @property
    def errors(self):
        """Klartext-Meldungen für die GUI (z. B. Port belegt)."""
        return list(self._errors.values())

    def configure(self, engine=None, spot=None, type_call=None, clipboard=None,
                  wipe=None, rpc_port=None):
        """Wege ein-/ausschalten (None = unverändert). Liefert die Ausnahmen
        der Bausteine, die sich nicht starten ließen (Port belegt)."""
        failed = []
        if type_call is not None:
            self.use_type = bool(type_call)
        if clipboard is not None:
            self.use_clipboard = bool(clipboard)
        if wipe is not None:
            self.typer.wipe = bool(wipe)
        if spot is not None:
            if spot and self.spots is None:
                srv = SpotServer(self.spot_port)
                if srv.bind():
                    srv.start()
                    self.spots = srv
                    self._errors.pop("spot", None)
                else:
                    self._errors["spot"] = srv.error
                    failed.append(PortInUseError(srv.error))
            elif not spot:
                self._errors.pop("spot", None)
                if self.spots is not None:
                    self.spots.stop()
                    self.spots = None
        if rpc_port is not None and int(rpc_port) != self.rpc_port:
            was_on = self.engine is not None or "engine" in self._errors
            self._stop_engine()
            self.rpc_port = int(rpc_port)
            if engine is None:
                engine = was_on
        if engine is not None:
            if engine and self.engine is None:
                exc = self._start_engine()
                if exc is not None:
                    failed.append(exc)
            elif not engine:
                self._stop_engine()
        return failed

    def _start_engine(self):
        from .fldigi_rpc import FldigiRpcServer
        srv = FldigiRpcServer(port=self.rpc_port, carrier=lambda: self.carrier_hz,
                              frequency=self._freq_hz)
        if not srv.bind():
            self._errors["engine"] = srv.error
            return EnginePortInUseError(srv.error)
        srv.start()
        self.engine = srv
        self._errors.pop("engine", None)
        return None

    def _stop_engine(self):
        self._errors.pop("engine", None)
        if self.engine is not None:
            self.engine.stop()
            self.engine = None

    def _freq_hz(self):
        r = self.radio
        return r.freq_khz * 1000.0 if (r.freq_khz and r.connected) else None

    @property
    def freq_khz(self):
        """Frequenz für Spots: RadioInfo, sonst die von N1MM an die Engine gemeldete."""
        if self.radio.freq_khz and self.radio.connected:
            return self.radio.freq_khz
        if self.engine is not None and self.engine.n1mm_freq_hz:
            return self.engine.n1mm_freq_hz / 1000.0
        return self.radio.freq_khz

    def feed_text(self, text: str):
        """Decodierten Text an die Engine geben (nur aus dem tk-Thread)."""
        if self.engine is not None:
            self.engine.feed(text)

    def send_call(self, call: str, snr_db: float = 20, wpm: float = 25) -> str:
        """Rufzeichen auf den gewählten Klick-Wegen an N1MM geben.

        Liefert eine Statusmeldung. Scheitern alle gewählten Wege, steht die
        Ursache in self.last_failure."""
        msgs = []
        tried = ok = typed = False
        failure = None
        self.last_failure = None
        if self.use_type and self.typer.available:
            tried = True
            # Entry Window des Fokus-Radios (#31); ohne Broadcast Titelsuche
            r = self.radio
            if r.connected:
                typed, msg = self.typer.type_call(call, r.entry_candidates(), r.radio_nr)
            else:
                typed, msg = self.typer.type_call(call)
            msgs.append(msg)
            ok = typed
            if not typed:
                failure = self.typer.last_error or EntryWindowNotFoundError(msg)
        if self.use_clipboard and not typed:
            tried = True
            if copy_to_clipboard(call):
                ok = True
                msgs.append(_MSG_TYPED_FALLBACK if self.use_type else _MSG_CLIPBOARD)
        if self.spots is not None:
            tried = True
            freq = self.freq_khz
            if not freq:
                msg = _MSG_NO_SPOT_FREQ
            elif self.spots.spot(call, freq, snr_db, wpm):
                msg = _MSG_SPOTTED.format(freq=freq)
                ok = True
            else:
                msg = _MSG_NO_SPOT_CLIENT.format(port=self.spot_port)
            msgs.append(msg)
            if failure is None:
                failure = SpotNotSentError(msg)
        if not tried:
            msgs.append(_MSG_ENGINE_ONLY if self.engine is not None else _MSG_NO_WAY)
        elif not ok:
            self.last_failure = failure or EntryWindowNotFoundError(msgs[-1])
        result = f"{call}: " + ", ".join(msgs)
        log.info("Übergabe an N1MM: %s", result)
        return result

    def stop(self):
        self.radio.stop()
        if self.spots:
            self.spots.stop()
            self.spots = None
        self._stop_engine()

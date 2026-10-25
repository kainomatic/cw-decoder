# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""Anbindung an N1MM Logger+.

Drei Bausteine:

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


class EntryWindowNotFoundError(RuntimeError):
    """N1MM-Fenster bzw. Entry Window nicht gefunden."""


# --------------------------------------------------------------------------
class RadioInfoListener(threading.Thread):
    def __init__(self, port: int = 12060, on_update=None):
        super().__init__(daemon=True)
        self.port = port
        self.on_update = on_update or (lambda info: None)
        self.freq_khz = None
        self.mode = None
        self.mycall = None
        self.radio_nr = 1
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
        try:
            # N1MM sendet Freq in 10-Hz-Schritten (z. B. 1402500 = 14025.00 kHz)
            self.freq_khz = int(g("Freq")) / 100.0
        except ValueError:
            pass
        self.mode = g("Mode") or self.mode
        self.mycall = g("OpCall") or g("mycall") or self.mycall
        try:
            self.radio_nr = int(g("RadioNr") or 1)
        except ValueError:
            pass
        self.last_rx = time.time()
        self.on_update(self)

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
# Das zweite Entry Window (SO2V/SO2R) hat "B" statt "A". Die Bandmap heißt
# ähnlich ("Elecraft K3 VFO A"), beginnt aber nicht mit einer Frequenz.
ENTRY_TITLE_RE = re.compile(
    r"^\s*\d{1,6}\.\d{1,3}(?:[+-]\d+(?:\.\d+)?)?\s+\S+.*\bVFO\s*([AB])\s*$", re.I)


def pick_entry_window(windows, vfo: str = "A", title_hint: str = ""):
    """Wählt aus [(hwnd, titel), ...] das Entry Window.

    1. Titel passt auf ENTRY_TITLE_RE, bevorzugt der gewünschte VFO
    2. Fallback: Titel enthält title_hint (falls gesetzt)
    Sonst None – lieber nichts tippen als ins falsche Fenster.
    """
    matches = []
    for hwnd, title in windows:
        m = ENTRY_TITLE_RE.match(title or "")
        if m:
            matches.append((m.group(1).upper() != vfo.upper(), hwnd, title))
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
        user32, kernel32 = _win32()
        found = []

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def enum_cb(hwnd, _):
            if not user32.IsWindowVisible(hwnd):
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            title = buf.value
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
            if self.process_hint in os.path.basename(exe).lower():
                found.append((hwnd, title))
            return True

        user32.EnumWindows(enum_cb, 0)
        return found

    def find_window(self):
        wins = self.process_windows()
        self.last_titles = [t for _, t in wins]
        # Für den ersten echten Test: alles ausgeben, was der Prozess an Fenstern hat
        log.info("%d Fenster von '%s': %s", len(wins), self.process_hint,
                 ", ".join(repr(t) for t in self.last_titles))
        win = pick_entry_window(wins, self.vfo, self.title_hint)
        if win:
            log.info("Entry Window: %r", win[1])
        return win

    # -- Tippen --------------------------------------------------------------
    def type_call(self, call: str):
        """Rufzeichen ins Entry Window tippen. Liefert (ok, Meldung);
        bei Fehlschlag steht die Ursache zusätzlich in self.last_error."""
        self.last_error = None
        win = self.find_window()
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
        time.sleep(0.05)
        if self.wipe:
            self._key_combo_alt("W")
            time.sleep(0.05)
        self._type_text(call)
        return True, "ins Entry Window getippt"

    def _bring_to_front(self, hwnd, wait_s: float = 0.25) -> bool:
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
        self._send_inputs([(VK_MENU, 0, 0), (VK_MENU, 0, KEYUP)])
        user32.SetForegroundWindow(hwnd)
        ok = is_front()
        log.info("Vordergrund: per ALT-Trick %s", "ok" if ok else "FEHLGESCHLAGEN")
        return ok

    @staticmethod
    def _send_inputs(inputs):
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

    def _type_text(self, text: str):
        KEYEVENTF_UNICODE, KEYEVENTF_KEYUP = 0x0004, 0x0002
        seq = []
        for ch in text:
            seq.append((0, ord(ch), KEYEVENTF_UNICODE))
            seq.append((0, ord(ch), KEYEVENTF_UNICODE | KEYEVENTF_KEYUP))
        self._send_inputs(seq)

    def _key_combo_alt(self, letter: str):
        VK_MENU, KEYUP = 0x12, 0x0002
        vk = ord(letter.upper())
        self._send_inputs([(VK_MENU, 0, 0), (vk, 0, 0), (vk, 0, KEYUP), (VK_MENU, 0, KEYUP)])


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
            conn.sendall(b"login: ")
            conn.settimeout(30)
            data = b""
            while b"\n" not in data:
                chunk = conn.recv(256)
                if not chunk:
                    return
                data += chunk
            call = data.decode(errors="replace").strip().upper() or "N1MM"
            conn.sendall(f"Hello {call}, this is the CW decoder spot feed.\r\n{call} de {self.spotter_call} >\r\n".encode())
            conn.settimeout(None)
            with self._lock:
                self.clients.append(conn)
            # Verbindung offen halten; eingehende Zeilen ignorieren
            while not self._stop_evt.is_set():
                chunk = conn.recv(256)
                if not chunk:
                    break
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
class N1MMBridge:
    """Bündelt alles: Frequenz von N1MM lesen, Rufzeichen per Tastatur oder
    Spot übergeben; klappt das Tippen nicht, landet das Rufzeichen in der
    Zwischenablage (Strg+V in N1MM)."""

    def __init__(self, udp_port: int = 12060, spot_port: int = 7373,
                 use_typer: bool = True, use_spots: bool = True, wipe: bool = True,
                 use_clipboard: bool = True):
        self.use_clipboard = use_clipboard
        self.errors = []    # Klartext-Meldungen für die GUI (z. B. Port belegt)
        # Ausnahme, wenn die letzte Übergabe N1MM auf keinem Weg erreicht hat
        self.last_failure = None
        self.radio = RadioInfoListener(udp_port)
        if self.radio.bind():
            self.radio.start()
        else:
            self.errors.append(self.radio.error)
        self.typer = EntryWindowTyper(wipe=wipe) if use_typer else None
        self.spots = SpotServer(spot_port) if use_spots else None
        if self.spots:
            if self.spots.bind():
                self.spots.start()
            else:
                self.errors.append(self.spots.error)
                self.spots = None

    def send_call(self, call: str, snr_db: float = 20, wpm: float = 25) -> str:
        """Rufzeichen an N1MM geben. Liefert eine Statusmeldung."""
        msgs = []
        typed = False
        clipped = spotted = False
        self.last_failure = None
        if self.typer and self.typer.available:
            typed, msg = self.typer.type_call(call)
            msgs.append(msg)
        if not typed and self.use_clipboard and copy_to_clipboard(call):
            # Rückfallweg: Tippen ging nicht, der Operator fügt selbst ein
            clipped = True
            msgs.append("in der Zwischenablage – Strg+V in N1MM")
        if self.spots and self.spots.spot(call, self.radio.freq_khz, snr_db, wpm):
            spotted = True
            msgs.append(f"als Spot auf {self.radio.freq_khz:.1f} kHz gesendet")
        if not msgs:
            msgs.append("N1MM nicht erreicht (kein Entry Window, kein Telnet-Client)")
        if not (typed or clipped or spotted):
            self.last_failure = ((self.typer.last_error if self.typer else None)
                                 or EntryWindowNotFoundError(msgs[-1]))
        result = f"{call}: " + ", ".join(msgs)
        log.info("Übergabe an N1MM: %s", result)
        return result

    def stop(self):
        self.radio.stop()
        if self.spots:
            self.spots.stop()

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
import re
import socket
import sys
import threading
import time
import xml.etree.ElementTree as ET


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
        self._stop_evt = threading.Event()

    def run(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.settimeout(0.5)
        try:
            s.bind(("", self.port))
        except OSError as e:
            print(f"[n1mm] UDP-Port {self.port} nicht verfügbar: {e}", file=sys.stderr)
            return
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

    @property
    def connected(self) -> bool:
        return time.time() - self.last_rx < 30


# --------------------------------------------------------------------------
class EntryWindowTyper:
    """Tippt Text in das N1MM Entry Window (nur Windows, via ctypes/user32)."""

    def __init__(self, process_hint: str = "N1MMLogger", title_hint: str = "", wipe: bool = True):
        self.process_hint = process_hint.lower()
        self.title_hint = title_hint.lower()
        self.wipe = wipe
        self.available = sys.platform.startswith("win")

    # -- Fenstersuche ------------------------------------------------------
    def find_window(self):
        if not self.available:
            return None
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        found = []

        @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
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
            if self.process_hint in exe.lower() and self.title_hint in title.lower():
                found.append((hwnd, title))
            return True

        user32.EnumWindows(enum_cb, 0)
        return found[0] if found else None

    # -- Tippen --------------------------------------------------------------
    def type_call(self, call: str) -> bool:
        win = self.find_window()
        if not win:
            print("[n1mm] Entry Window nicht gefunden (läuft N1MM?)", file=sys.stderr)
            return False
        import ctypes
        user32 = ctypes.windll.user32
        hwnd, title = win
        user32.SetForegroundWindow(hwnd)
        time.sleep(0.05)
        if self.wipe:
            self._key_combo_alt("W")
            time.sleep(0.05)
        self._type_text(call)
        return True

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
        self.clients = []
        self._lock = threading.Lock()
        self._stop_evt = threading.Event()

    def run(self):
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            srv.bind(("127.0.0.1", self.port))
        except OSError as e:
            print(f"[n1mm] Spot-Server Port {self.port} nicht verfügbar: {e}", file=sys.stderr)
            return
        srv.listen(2)
        srv.settimeout(0.5)
        while not self._stop_evt.is_set():
            try:
                conn, _ = srv.accept()
            except socket.timeout:
                continue
            threading.Thread(target=self._serve_client, args=(conn,), daemon=True).start()
        srv.close()

    def _serve_client(self, conn):
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


# --------------------------------------------------------------------------
class N1MMBridge:
    """Bündelt alles: Frequenz von N1MM lesen, Rufzeichen per Tastatur oder
    Spot übergeben."""

    def __init__(self, udp_port: int = 12060, spot_port: int = 7373,
                 use_typer: bool = True, use_spots: bool = True, wipe: bool = True):
        self.radio = RadioInfoListener(udp_port)
        self.radio.start()
        self.typer = EntryWindowTyper(wipe=wipe) if use_typer else None
        self.spots = SpotServer(spot_port) if use_spots else None
        if self.spots:
            self.spots.start()

    def send_call(self, call: str, snr_db: float = 20, wpm: float = 25) -> str:
        """Rufzeichen an N1MM geben. Liefert eine Statusmeldung."""
        msgs = []
        if self.typer and self.typer.available and self.typer.type_call(call):
            msgs.append("ins Entry Window getippt")
        if self.spots and self.spots.spot(call, self.radio.freq_khz, snr_db, wpm):
            msgs.append(f"als Spot auf {self.radio.freq_khz:.1f} kHz gesendet")
        if not msgs:
            msgs.append("N1MM nicht erreicht (Fenster nicht gefunden, kein Telnet-Client)")
        return f"{call}: " + ", ".join(msgs)

    def stop(self):
        self.radio.stop()
        if self.spots:
            self.spots.stop()

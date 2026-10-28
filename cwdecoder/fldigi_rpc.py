# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""Engine für N1MMs CW-Reader-Fenster: XML-RPC-Schnittstelle wie fldigi (ADR-0022).

N1MM Logger+ zeigt im Fenster „CW Reader" den Text einer externen Engine
und übernimmt angeklickte Rufzeichen ins Entry Window. Als Engine erwartet
es fldigi. Dieses Modul bildet den Teil der fldigi-Schnittstelle nach, den
N1MM aufruft (Mitschnitt in Issue #3). Auf die Frage nach Name und Version
meldet sich der CW Decoder mit eigenem Namen; N1MM akzeptiert das
(Mitschnitt in Issue #13, es fragt nur `fldigi.version` ab):

    fldigi.version                       einmal, auch vor dem Start
    modem.set_by_name('CW'), rig.set_mode('CW'), main.set_frequency(Hz)
    rx.get_data            alle ~200 ms  neue Zeichen seit dem letzten Aufruf
    main.get_trx_status    alle ~400 ms  'rx'
    main.set_afc, modem.get_carrier/set_carrier   Knöpfe AFC/Align
    rig.release_control, fldigi.terminate          beim Schließen

Dazu die naheliegenden Nachbarn (text.get_rx, text.get_rx_length,
text.clear_rx, modem.get_name, main.get_frequency …). Unbekannte Methoden
werden einmal je Name geloggt und mit einem Fault beantwortet wie bei fldigi.

Nur das Protokoll ist nachgebildet, kein fldigi-Code. fldigi (W1HKJ, GPL)
ist ein eigenständiges Projekt und mit dem CW Decoder nicht verbunden.

Threading (ADR-0009): Der Server läuft in eigenen Threads und fasst kein tk
an. Die GUI hängt Text per `RxBuffer.append` an (gelockt) und setzt
Trägerfrequenz und Funkfrequenz über Provider-Funktionen, die nur
einfache Attribute lesen.
"""
import logging
import threading
import time
import xmlrpc.client
from socketserver import ThreadingMixIn
from xmlrpc.server import SimpleXMLRPCRequestHandler, SimpleXMLRPCServer

from .__version__ import APP_NAME, __version__

log = logging.getLogger(__name__)

# N1MM startet die CW-Reader-Engine mit diesem Port und Fenstertitel
# (Reader 1; 7362/7366 gehören dem Digital Interface)
DEFAULT_PORT = 7367
DEFAULT_TITLE = "Fldigi CW Engine 1"
# Eigener Name und eigene Version, kein fremder Programmname (#13).
# fldigi.version nur numerisch X.Y.Z wie bei fldigi (Beta: ohne „-betaN“);
# so in N1MM 1.0.7711 nachgewiesen. Die volle Bezeichnung steht in name_version.
ENGINE_NAME = APP_NAME
ENGINE_VERSION = __version__.split("-")[0]
ENGINE_NAME_VERSION = f"{APP_NAME} {__version__} (fldigi-kompatibel)"
RX_BUFFER_BYTES = 64 * 1024
CONNECTED_S = 3.0               # so lange nach dem letzten Abruf gilt N1MM als verbunden
FAULT_NO_METHOD = -506          # wie xmlrpc-c in fldigi


class RxBuffer:
    """Empfangstext als UTF-8-Bytes mit fortlaufender Position.

    `length` zählt alle Bytes seit Start (monoton). Gespeichert werden nur
    die letzten `max_bytes`; ältere Positionen liefern nichts mehr.
    `clear()` schiebt den Anfang ans Ende (wie „Clear RX" in fldigi), die
    Länge läuft weiter. `read_new()` liefert für rx.get_data alles seit dem
    letzten Aufruf (ein gemeinsamer Lesezeiger, wie in fldigi)."""

    def __init__(self, max_bytes: int = RX_BUFFER_BYTES):
        self.max_bytes = max_bytes
        self._data = bytearray()
        self._start = 0          # Position des ersten gespeicherten Bytes
        self._read = 0           # Lesezeiger für read_new
        self._lock = threading.Lock()

    def append(self, text: str):
        if not text:
            return
        raw = text.encode("utf-8")
        with self._lock:
            self._data += raw
            drop = len(self._data) - self.max_bytes
            if drop > 0:
                del self._data[:drop]
                self._start += drop

    @property
    def length(self) -> int:
        with self._lock:
            return self._start + len(self._data)

    def get(self, start: int, length: int) -> bytes:
        """Bytes ab Position `start`, höchstens `length` (fldigi text.get_rx)."""
        with self._lock:
            end = self._start + len(self._data)
            stop = min(int(start) + max(int(length), 0), end)
            start = max(int(start), self._start)
            if stop <= start:
                return b""
            return bytes(self._data[start - self._start:stop - self._start])

    def read_new(self) -> bytes:
        with self._lock:
            end = self._start + len(self._data)
            pos = max(self._read, self._start)
            self._read = end
            return bytes(self._data[pos - self._start:])

    def clear(self):
        with self._lock:
            self._start += len(self._data)
            self._data = bytearray()


class _Handler(SimpleXMLRPCRequestHandler):
    rpc_paths = ("/", "/RPC2")

    def log_message(self, fmt, *args):     # kein HTTP-Zugriffslog auf stderr
        pass


class _Server(ThreadingMixIn, SimpleXMLRPCServer):
    daemon_threads = True
    # ohne SO_REUSEADDR: ein belegter Port (fldigi läuft?) soll auffallen
    allow_reuse_address = False


class FldigiRpcServer(threading.Thread):
    """XML-RPC-Server wie fldigi, für N1MMs CW Reader.

    carrier():   aktuelle Tonfrequenz in Hz (Tracker), oder None
    frequency(): Funkfrequenz in Hz (RadioInfo von N1MM), oder None
    """

    def __init__(self, host: str = "127.0.0.1", port: int = DEFAULT_PORT,
                 carrier=None, frequency=None, buffer: RxBuffer = None):
        super().__init__(daemon=True, name="fldigi-rpc")
        self.host = host
        self.port = port
        self.carrier = carrier or (lambda: None)
        self.frequency = frequency or (lambda: None)
        self.rx = buffer or RxBuffer()
        self.srv = None
        self.error = None
        self.modem = "CW"
        self.afc = False
        self.n1mm_freq_hz = None    # letzte Frequenz aus main.set_frequency
        self.last_call = 0.0        # time.monotonic() des letzten Aufrufs
        self.calls = 0
        self._unknown = set()

    # -- Lebenszyklus ------------------------------------------------------
    def bind(self) -> bool:
        """Port sofort binden. False -> self.error (Klartext)."""
        try:
            srv = _Server((self.host, self.port), requestHandler=_Handler,
                          allow_none=True, logRequests=False)
        except OSError as e:
            self.error = (f"Port {self.port} belegt – läuft fldigi oder ein zweiter "
                          f"CW Decoder? Port in den N1MM-Einstellungen ändern")
            log.warning("%s (%s)", self.error, e)
            return False
        srv.register_instance(self)
        self.srv = srv
        log.info("CW-Reader-Engine für N1MM auf %s:%d", self.host, self.port)
        return True

    def run(self):
        if self.srv is None and not self.bind():
            return
        self.srv.serve_forever(poll_interval=0.2)

    def stop(self):
        if self.srv is not None:
            if self.is_alive():
                self.srv.shutdown()
            self.srv.server_close()
            self.srv = None
        if self.is_alive() and threading.current_thread() is not self:
            self.join(timeout=1.0)

    # -- Zustand für die GUI -------------------------------------------------
    @property
    def connected(self) -> bool:
        return self.calls > 0 and time.monotonic() - self.last_call < CONNECTED_S

    def seconds_since_call(self):
        return None if not self.calls else time.monotonic() - self.last_call

    def feed(self, text: str):
        """Decodierten Text anhängen (aus dem tk-Thread)."""
        self.rx.append(text)

    # -- XML-RPC ---------------------------------------------------------------
    def _dispatch(self, method, params):
        self.last_call = time.monotonic()
        self.calls += 1
        fn = _METHODS.get(method)
        if fn is None:
            if method not in self._unknown:
                self._unknown.add(method)
                log.info("CW-Reader-Engine: unbekannte Methode %s%r", method, tuple(params))
            raise xmlrpc.client.Fault(FAULT_NO_METHOD, f"Method '{method}' not defined")
        if method not in ("rx.get_data", "main.get_trx_status", "text.get_rx",
                          "text.get_rx_length"):
            log.info("CW-Reader-Engine: %s%r", method, tuple(params))
        return fn(self, *params)

    def _carrier(self) -> int:
        f = self.carrier()
        return int(round(f)) if f else 0

    def _frequency(self) -> float:
        f = self.frequency()
        if f:
            return float(f)
        return float(self.n1mm_freq_hz or 0.0)

    def _set_frequency(self, hz=0.0):
        try:
            self.n1mm_freq_hz = float(hz)
        except (TypeError, ValueError):
            pass
        return self._frequency()

    def _set_modem(self, name=""):
        old, self.modem = self.modem, str(name) or self.modem
        return old

    def _set_afc(self, on=False):
        old, self.afc = self.afc, bool(on)
        return old

    def _terminate(self, *_):
        # N1MM schließt sein CW-Reader-Fenster; der CW Decoder läuft weiter
        log.info("CW-Reader-Engine: N1MM hat den CW Reader geschlossen")
        return None


def _version_struct(version: str) -> dict:
    """„0.1.0" -> {"major": 0, "minor": 1, "patch": "0"} (Form wie bei fldigi)."""
    parts = (version.split("-")[0].split(".") + ["0", "0", "0"])[:3]
    try:
        return {"major": int(parts[0]), "minor": int(parts[1]), "patch": parts[2]}
    except ValueError:
        return {"major": 0, "minor": 0, "patch": "0"}


def _names(_srv):
    return sorted(_METHODS)


_METHODS = {
    "fldigi.version": lambda s: ENGINE_VERSION,
    "fldigi.name": lambda s: ENGINE_NAME,
    "fldigi.name_version": lambda s: ENGINE_NAME_VERSION,
    "fldigi.version_struct": lambda s: _version_struct(ENGINE_VERSION),
    "fldigi.list": lambda s: [{"name": n, "signature": "", "help": ""} for n in _names(s)],
    "fldigi.terminate": FldigiRpcServer._terminate,
    "system.listMethods": _names,
    "modem.get_name": lambda s: s.modem,
    "modem.get_names": lambda s: ["CW"],
    "modem.set_by_name": FldigiRpcServer._set_modem,
    "modem.get_carrier": FldigiRpcServer._carrier,
    # Align: Wir folgen dem Ton selbst; die Vorgabe wird bestätigt, nicht übernommen
    "modem.set_carrier": lambda s, hz=0: s._carrier(),
    "text.get_rx_length": lambda s: s.rx.length,
    "text.get_rx": lambda s, start=0, length=0: xmlrpc.client.Binary(s.rx.get(start, length)),
    "text.clear_rx": lambda s: s.rx.clear(),
    "rx.get_data": lambda s: xmlrpc.client.Binary(s.rx.read_new()),
    "main.get_frequency": FldigiRpcServer._frequency,
    "main.set_frequency": FldigiRpcServer._set_frequency,
    "main.get_trx_state": lambda s: "RX",
    "main.get_trx_status": lambda s: "rx",
    "main.get_status1": lambda s: "CW",
    "main.get_status2": lambda s: "",
    "main.get_afc": lambda s: s.afc,
    "main.set_afc": FldigiRpcServer._set_afc,
    "main.rx": lambda s: None,
    "rig.set_mode": lambda s, mode="": None,
    "rig.get_mode": lambda s: "CW",
    "rig.take_control": lambda s: None,
    "rig.release_control": lambda s: None,
}

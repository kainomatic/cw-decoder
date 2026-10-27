# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""Mitschnitt-Stub: Was ruft N1MMs CW-Reader-Fenster bei "fldigi" auf? (#3)

Stellt die XML-RPC-Schnittstelle von fldigi auf 127.0.0.1:7362 nach und
loggt jeden Aufruf mit Parametern, Antwort und Zeitstempel nach
tools/fldigi_stub.log (bzw. --log). Die Antworten sind plausibel, aber fest:
ein Testtext wächst um ein Zeichen je 0,2 s.

N1MM startet die Engine selbst über einen eingetragenen Pfad zu fldigi.exe.
Dafür wird der Stub mit PyInstaller als fldigi.exe gebaut; beliebige
Kommandozeilen-Argumente werden geloggt und ignoriert:

    pyinstaller --onefile --name fldigi --distpath C:\\fldigi_stub tools/fldigi_stub.py

Nur Protokoll, kein fldigi-Code (fldigi: W1HKJ, GPL).
"""
import argparse
import os
import sys
import threading
import time
import xmlrpc.client
from socketserver import ThreadingMixIn
from xmlrpc.server import SimpleXMLRPCRequestHandler, SimpleXMLRPCServer

TEST_TEXT = ("CQ TEST DE DL1ABC DL1ABC TEST  DJ7PR 599 14  TU DL1ABC TEST  "
             "OY1CT 5NN 15  TU  CQ TEST DE DL1ABC K  ")

# Bekannte fldigi-Methoden mit festen, plausiblen Antworten
CONST = {
    "fldigi.name": "fldigi",
    "fldigi.version": "4.2.05",
    "fldigi.name_version": "fldigi 4.2.05",
    "fldigi.version_struct": {"major": 4, "minor": 2, "patch": "05"},
    "fldigi.config_dir": "C:\\fldigi_stub\\",
    "modem.get_names": ["CW", "BPSK31", "RTTY"],
    "modem.get_id": 1,
    "modem.get_max_id": 3,
    "modem.get_bandwidth": 100,
    "modem.get_afc_search_range": 50,
    "main.get_frequency": 7025000.0,
    "main.get_trx_state": "RX",
    "main.get_trx_status": "rx",
    "main.get_status1": "CW",
    "main.get_status2": "",
    "main.get_wf_sideband": "USB",
    "main.get_sideband": "USB",
    "main.get_squelch": False,
    "main.get_squelch_level": 0.0,
    "main.get_afc": False,
    "main.get_reverse": False,
    "main.get_lock": False,
    "main.get_rsid": False,
    "main.get_txid": False,
    "rig.get_name": "",
    "rig.get_mode": "CW",
    "rig.get_bandwidth": "",
    "io.in_use": "NONE",
    "text.get_tx_length": 0,
    "log.get_call": "",
}


class StubState:
    def __init__(self, log_path, char_interval=0.2):
        self.t0 = time.monotonic()
        self.char_interval = char_interval
        self.cleared_at = 0           # Länge beim letzten clear_rx
        self.rx_read = 0              # Position für rx.get_data
        self.modem = "CW"
        self.carrier = 700
        self.log_path = log_path
        self._lock = threading.Lock()

    def rx_text(self) -> str:
        n = int((time.monotonic() - self.t0) / self.char_interval)
        reps = TEST_TEXT * (n // len(TEST_TEXT) + 1)
        return reps[:n]

    def log(self, line: str):
        stamp = time.strftime("%H:%M:%S") + f".{int(time.time() * 1000) % 1000:03d}"
        with self._lock, open(self.log_path, "a", encoding="utf-8") as f:
            f.write(f"{stamp} {line}\n")


class Handler(SimpleXMLRPCRequestHandler):
    rpc_paths = ("/", "/RPC2")

    def log_message(self, fmt, *args):   # HTTP-Zugriffe nicht auf stderr
        pass


class Server(ThreadingMixIn, SimpleXMLRPCServer):
    daemon_threads = True
    allow_reuse_address = False


class StubDispatcher:
    def __init__(self, st: StubState):
        self.st = st

    def _dispatch(self, method, params):
        try:
            result = self._answer(method, params)
        except Exception as e:  # noqa: BLE001 - alles loggen
            self.st.log(f"CALL {method}{tuple(params)!r} -> EXC {e!r}")
            raise
        shown = result
        if isinstance(result, xmlrpc.client.Binary):
            shown = f"<bytes {result.data!r}>"
        self.st.log(f"CALL {method}{tuple(params)!r} -> {shown!r}")
        return result

    def _answer(self, method, params):
        st = self.st
        text = st.rx_text().encode("utf-8")
        if method in ("system.listMethods", "fldigi.list"):
            names = sorted(set(CONST) | {
                "modem.get_name", "modem.set_by_name", "modem.get_carrier",
                "modem.set_carrier", "text.get_rx_length", "text.get_rx",
                "text.clear_rx", "rx.get_data", "fldigi.terminate"})
            if method == "fldigi.list":
                return [{"name": n, "signature": "", "help": ""} for n in names]
            return names
        if method == "modem.get_name":
            return st.modem
        if method == "modem.set_by_name":
            old, st.modem = st.modem, str(params[0]) if params else st.modem
            return old
        if method == "modem.get_carrier":
            return st.carrier
        if method == "modem.set_carrier":
            old = st.carrier
            st.carrier = int(params[0]) if params else st.carrier
            return old
        if method == "text.get_rx_length":
            return len(text)
        if method == "text.get_rx":
            start = int(params[0]) if params else 0
            length = int(params[1]) if len(params) > 1 else len(text) - start
            return xmlrpc.client.Binary(text[start:start + length])
        if method == "rx.get_data":
            chunk = text[st.rx_read:]
            st.rx_read = len(text)
            return xmlrpc.client.Binary(chunk)
        if method == "text.clear_rx":
            st.cleared_at = len(text)
            return ""
        if method == "fldigi.terminate":
            threading.Timer(0.3, lambda: os._exit(0)).start()
            return ""
        if method in CONST:
            return CONST[method]
        # Unbekannt: loggen und einen neutralen Wert liefern (Name verrät oft den Typ)
        if ".get_" in method or method.startswith("main.get"):
            return ""
        return ""


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    here = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False)
                                           else __file__))
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--stub-port", type=int, default=7362)
    p.add_argument("--xmlrpc-server-port", type=int)       # echter fldigi-Schalter
    p.add_argument("--stub-log", default=os.path.join(here, "fldigi_stub.log"))
    p.add_argument("-ti", "--title", "-title", dest="title", default="fldigi stub")
    a, _unknown = p.parse_known_args(argv)
    port = a.xmlrpc_server_port or a.stub_port
    st = StubState(a.stub_log)
    st.log(f"START pid={os.getpid()} cwd={os.getcwd()!r} argv={sys.argv!r}")
    try:
        srv = Server(("127.0.0.1", port), requestHandler=Handler, allow_none=True,
                     logRequests=False)
    except OSError as e:
        st.log(f"BIND-FEHLER Port {port}: {e!r}")
        raise SystemExit(2) from e
    srv.register_instance(StubDispatcher(st))
    st.log(f"LISTEN 127.0.0.1:{port}")
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    import tkinter as tk
    root = tk.Tk()
    root.title(a.title)
    root.geometry("360x80")
    tk.Label(root, text=f"fldigi-Stub (CW Decoder #3) - XML-RPC 127.0.0.1:{port}").pack(expand=True)
    root.protocol("WM_DELETE_WINDOW", root.destroy)
    hidden = os.path.exists(os.path.join(here, "hidden.flag"))   # Versuch: reicht ein verstecktes Fenster?
    if hidden:
        root.withdraw()
    st.log(f"FENSTER {a.title!r} {'versteckt' if hidden else 'sichtbar'}")
    try:
        root.mainloop()
    except KeyboardInterrupt:
        pass
    finally:
        st.log("ENDE")


if __name__ == "__main__":
    main()

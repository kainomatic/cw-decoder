# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""fldigi-kompatible Engine für N1MMs CW Reader (cwdecoder/fldigi_rpc.py, #3)."""
import re
import socket
import xmlrpc.client

import pytest

from cwdecoder.__version__ import APP_NAME, __version__
from cwdecoder.fldigi_rpc import FldigiRpcServer, RxBuffer, _version_struct


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture
def engine():
    state = {"carrier": 712.4, "freq": None}
    srv = FldigiRpcServer(port=free_port(), carrier=lambda: state["carrier"],
                          frequency=lambda: state["freq"])
    assert srv.bind()
    srv.start()
    proxy = xmlrpc.client.ServerProxy(f"http://127.0.0.1:{srv.port}", allow_none=True)
    yield srv, proxy, state
    srv.stop()


def test_ablauf_wie_n1mm(engine):
    """Reihenfolge aus dem Mitschnitt (Issue #3, Phase A)."""
    srv, p, _ = engine
    assert p.fldigi.version() == __version__.split("-")[0]
    assert p.modem.set_by_name("CW") == "CW"
    p.rig.set_mode("CW")
    p.main.set_frequency(7025000.0)
    assert p.main.get_trx_status() == "rx"
    srv.feed("CQ TEST DE DL1ABC")
    assert p.rx.get_data().data == b"CQ TEST DE DL1ABC"
    assert p.rx.get_data().data == b""          # nur Neues
    srv.feed(" K\n")
    assert p.rx.get_data().data == b" K\n"
    assert srv.connected
    p.rig.release_control()
    p.fldigi.terminate(0)
    assert srv.is_alive()                        # Schließen in N1MM beendet uns nicht


def test_eigener_name_und_version(engine):
    """#13: Der CW Decoder meldet sich mit eigenem Namen, nicht als fldigi.
    fldigi.version bleibt numerisch X.Y.Z (so in N1MM 1.0.7711 nachgewiesen)."""
    _, p, _ = engine
    assert re.fullmatch(r"\d+\.\d+\.\d+", p.fldigi.version())
    assert p.fldigi.name() == APP_NAME == "CW Decoder"
    assert p.fldigi.name_version() == f"CW Decoder {__version__} (fldigi-kompatibel)"
    for answer in (p.fldigi.version(), p.fldigi.name(), p.fldigi.name_version()):
        assert "4.2.05" not in answer
        assert not answer.lower().startswith("fldigi")
    major, minor, patch = (int(x) for x in __version__.split("-")[0].split("."))
    assert p.fldigi.version_struct() == {"major": major, "minor": minor, "patch": str(patch)}


def test_version_struct():
    assert _version_struct("0.1.0") == {"major": 0, "minor": 1, "patch": "0"}
    assert _version_struct("1.2.3-beta18") == {"major": 1, "minor": 2, "patch": "3"}
    assert _version_struct("kaputt") == {"major": 0, "minor": 0, "patch": "0"}


def test_laengen_und_ausschnitte(engine):
    srv, p, _ = engine
    srv.feed("CQ DE DJ7PR <AR> ÄÖ")
    raw = "CQ DE DJ7PR <AR> ÄÖ".encode("utf-8")
    assert p.text.get_rx_length() == len(raw)
    assert p.text.get_rx(0, 2).data == b"CQ"
    assert p.text.get_rx(6, 5).data == b"DJ7PR"          # Start und Länge wie fldigi
    assert p.text.get_rx(12, 4).data == b"<AR>"
    assert p.text.get_rx(len(raw) - 4, 100).data.decode("utf-8") == "ÄÖ"
    assert p.text.get_rx(len(raw), 10).data == b""


def test_offsets_nach_pufferueberlauf():
    buf = RxBuffer(max_bytes=10)
    buf.append("0123456789")
    buf.append("ABCDE")
    assert buf.length == 15                      # monoton seit Start
    assert buf.get(0, 5) == b""                  # vor dem Fenster: leer ab Fensteranfang
    assert buf.get(5, 3) == b"567"
    assert buf.get(3, 4) == b"56"                # Start vor dem Fenster wird abgeschnitten
    assert buf.read_new() == b"56789ABCDE"       # Lesezeiger springt an den Fensteranfang
    buf.append("F")
    assert buf.read_new() == b"F"


def test_clear_rx(engine):
    srv, p, _ = engine
    srv.feed("ALT ")
    p.text.clear_rx()
    assert p.text.get_rx_length() == 4           # Länge läuft weiter
    assert p.text.get_rx(0, 4).data == b""
    assert p.rx.get_data().data == b""
    srv.feed("NEU")
    assert p.text.get_rx(4, 3).data == b"NEU"
    assert p.rx.get_data().data == b"NEU"


def test_traeger_und_frequenz(engine):
    srv, p, state = engine
    assert p.modem.get_carrier() == 712
    assert p.modem.set_carrier(700) == 712       # Align: wir bleiben am Ton
    assert p.main.get_frequency() == 0.0
    p.main.set_frequency(7030000.0)
    assert p.main.get_frequency() == 7030000.0   # ohne RadioInfo: N1MMs Vorgabe
    state["freq"] = 14025000.0
    assert p.main.get_frequency() == 14025000.0  # RadioInfo hat Vorrang
    state["carrier"] = None
    assert p.modem.get_carrier() == 0
    assert p.main.set_afc(True) is False and p.main.get_afc() is True


def test_unbekannte_methode(engine, caplog):
    import logging
    caplog.set_level(logging.INFO, logger="cwdecoder.fldigi_rpc")
    _, p, _ = engine
    for _ in range(2):
        with pytest.raises(xmlrpc.client.Fault) as ei:
            p.wefax.state_string()
        assert ei.value.faultCode == -506
    assert caplog.text.count("unbekannte Methode wefax.state_string") == 1
    assert "rx.get_data" in p.system.listMethods()


def test_port_belegt():
    first = FldigiRpcServer(port=free_port())
    assert first.bind()
    try:
        second = FldigiRpcServer(port=first.port)
        assert not second.bind()
        assert f"Port {first.port} belegt" in second.error and "fldigi" in second.error
    finally:
        first.stop()


def test_stop_gibt_port_frei():
    srv = FldigiRpcServer(port=free_port())
    assert srv.bind()
    srv.start()
    srv.stop()
    again = FldigiRpcServer(port=srv.port)
    assert again.bind()
    again.stop()

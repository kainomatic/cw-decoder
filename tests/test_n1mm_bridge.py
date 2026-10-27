# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""N1MMBridge: wählbare Übergabewege und Engine für den CW Reader (ADR-0022, #3)."""
import socket
import time
import xmlrpc.client

import pytest

from cwdecoder import n1mm
from cwdecoder.gui_errors import classify_error
from cwdecoder.n1mm import (EnginePortInUseError, EntryWindowNotFoundError, N1MMBridge,
                            SpotNotSentError)


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture
def make_bridge():
    made = []

    def make(**kw):
        kw.setdefault("udp_port", 0)
        kw.setdefault("spot_port", 0)
        kw.setdefault("rpc_port", free_port())
        b = N1MMBridge(**kw)
        made.append(b)
        return b
    yield make
    for b in made:
        b.stop()


class FakeTyper:
    available = True
    wipe = True

    def __init__(self, ok):
        self.ok = ok
        self.calls = []
        self.last_error = None if ok else EntryWindowNotFoundError("weg")

    def type_call(self, call):
        self.calls.append(call)
        return (True, "ins Entry Window getippt") if self.ok else (False, "Entry Window fehlt")


def telnet_client(port):
    c = socket.create_connection(("127.0.0.1", port), timeout=2)
    assert c.recv(64).startswith(b"login:")
    c.sendall(b"DF1DS\r\n")
    c.recv(256)
    return c


def wait_for(cond, timeout=2.0):
    t_end = time.monotonic() + timeout
    while time.monotonic() < t_end:
        if cond():
            return True
        time.sleep(0.02)
    return False


def test_standard_engine_und_spot(make_bridge):
    b = make_bridge()
    assert b.engine is not None and b.spots is not None
    assert not b.use_type and not b.use_clipboard
    assert b.errors == [] and b.start_failures == []


def test_nur_engine_klick_ist_kein_fehler(make_bridge):
    b = make_bridge(spot=False)
    msg = b.send_call("DJ7PR")
    assert "im CW Reader von N1MM anklicken" in msg
    assert b.last_failure is None


def test_spot_ohne_frequenz_meldet_fehler(make_bridge):
    b = make_bridge(engine=False)
    msg = b.send_call("DJ7PR")
    assert "Frequenz von N1MM unbekannt" in msg
    assert isinstance(b.last_failure, SpotNotSentError)
    assert classify_error(b.last_failure).title == "Spot nicht gesendet"


def test_spot_nimmt_frequenz_von_der_engine(make_bridge):
    """Ohne RadioInfo-Broadcast kennt die Bridge die Frequenz aus N1MMs
    main.set_frequency an die Engine."""
    b = make_bridge()
    p = xmlrpc.client.ServerProxy(f"http://127.0.0.1:{b.rpc_port}", allow_none=True)
    p.main.set_frequency(7025000.0)
    c = telnet_client(b.spots.srv.getsockname()[1])
    try:
        assert wait_for(lambda: b.spots.clients)
        msg = b.send_call("DJ7PR", snr_db=17, wpm=24)
        assert "als Spot auf 7025.0 kHz gesendet" in msg and b.last_failure is None
        line = c.recv(256).decode()
        assert "DX de CWDEC-#:   7025.0  DJ7PR" in line and "17 dB  24 WPM" in line
    finally:
        c.close()


def test_tippen_mit_rueckfall_zwischenablage(make_bridge, monkeypatch):
    clip = []
    monkeypatch.setattr(n1mm, "copy_to_clipboard", lambda t: clip.append(t) or True)
    b = make_bridge(engine=False, spot=False, type_call=True, clipboard=True)
    b.typer = FakeTyper(ok=False)
    msg = b.send_call("OY1CT")
    assert clip == ["OY1CT"] and "Strg+V" in msg and b.last_failure is None
    b.typer = FakeTyper(ok=True)
    clip.clear()
    msg = b.send_call("OY1CT")
    assert clip == [] and "getippt" in msg


def test_tippen_scheitert_ohne_rueckfall(make_bridge):
    b = make_bridge(engine=False, spot=False, type_call=True)
    b.typer = FakeTyper(ok=False)
    b.send_call("OY1CT")
    assert isinstance(b.last_failure, EntryWindowNotFoundError)


def test_nur_zwischenablage(make_bridge, monkeypatch):
    clip = []
    monkeypatch.setattr(n1mm, "copy_to_clipboard", lambda t: clip.append(t) or True)
    b = make_bridge(engine=False, spot=False, clipboard=True)
    msg = b.send_call("DL1ABC")
    assert clip == ["DL1ABC"] and msg == "DL1ABC: in der Zwischenablage"


def test_engine_port_belegt(make_bridge):
    blocker = socket.socket()
    blocker.bind(("127.0.0.1", 0))
    blocker.listen(1)
    port = blocker.getsockname()[1]
    try:
        b = make_bridge(rpc_port=port, spot=False)
        assert b.engine is None
        assert len(b.start_failures) == 1
        exc = b.start_failures[0]
        assert isinstance(exc, EnginePortInUseError)
        assert f"Port {port} belegt" in b.errors[0]
        assert classify_error(exc).title == "Port für den N1MM CW Reader belegt"
    finally:
        blocker.close()


def test_configure_schaltet_wege_und_port(make_bridge):
    b = make_bridge()
    old_port = b.rpc_port
    assert b.configure(engine=False, spot=False) == []
    assert b.engine is None and b.spots is None
    # freigegeben: der Port lässt sich wieder binden
    s = socket.socket()
    s.bind(("127.0.0.1", old_port))
    s.close()
    new_port = free_port()
    b.configure(engine=True, rpc_port=new_port)
    assert b.engine is not None and b.engine.port == new_port
    newer = free_port()
    b.configure(rpc_port=newer)                  # Portwechsel bei laufender Engine
    assert b.engine is not None and b.engine.port == newer
    b.configure(type_call=True, clipboard=True, wipe=False)
    assert b.use_type and b.use_clipboard and b.typer.wipe is False


def test_text_und_traeger_an_n1mm(make_bridge):
    b = make_bridge(spot=False)
    p = xmlrpc.client.ServerProxy(f"http://127.0.0.1:{b.rpc_port}", allow_none=True)
    b.feed_text("CQ DE DJ7PR")
    b.carrier_hz = 655.2
    assert p.rx.get_data().data == b"CQ DE DJ7PR"
    assert p.modem.get_carrier() == 655


def test_spot_auch_ohne_login(make_bridge):
    """N1MM ohne „Automatically Logon“ schickt kein Rufzeichen und wartet
    nach „login:“; der Spot muss trotzdem ankommen (Nachweis #3)."""
    b = make_bridge(engine=False)
    b.radio.freq_khz, b.radio.last_rx = 14025.0, time.time()
    c = socket.create_connection(("127.0.0.1", b.spots.srv.getsockname()[1]), timeout=2)
    try:
        assert c.recv(64) == b"login: "
        assert wait_for(lambda: b.spots.clients)
        msg = b.send_call("OY1CT")
        assert "als Spot auf 14025.0 kHz gesendet" in msg and b.last_failure is None
        assert "OY1CT" in c.recv(256).decode()
    finally:
        c.close()

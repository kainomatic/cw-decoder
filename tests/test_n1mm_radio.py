# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""N1MM mit zwei Entry Windows (SO2R/SO2V, #31).

Je Radio ein RadioInfo-Paket; „das Radio“ ist das Fokus-Radio
(FocusRadioNr). Eingetippt wird ins Entry Window per Handle aus dem
Broadcast, sonst per Titel.
"""
import socket
import sys

import pytest

from cwdecoder import n1mm
from cwdecoder.n1mm import EntryWindowTyper, N1MMBridge, RadioInfoListener, pick_entry_window

# Titel aus dem Log des Shack-Tests (beta20, SO2R, Contest WAG, ohne CAT)
LOG_TITLES = ["7040.32 CW Manual Radio 1 ", "Telnet", "GlassPanelForm", "Manual Radio 1",
              "Available Radio 1 7040.32 CW", "CW Reader 1", "21300.00 USB Manual Radio 2 "]


def pkt(nr, freq_10hz, mode, hwnd=None, focus=None, focus_entry=None, call="DF1DS"):
    parts = [f"<RadioNr>{nr}</RadioNr>", f"<Freq>{freq_10hz}</Freq>", f"<Mode>{mode}</Mode>",
             f"<OpCall>{call}</OpCall>"]
    if hwnd is not None:
        parts.append(f"<EntryWindowHwnd>{hwnd}</EntryWindowHwnd>")
    if focus is not None:
        parts.append(f"<FocusRadioNr>{focus}</FocusRadioNr>")
    if focus_entry is not None:
        parts.append(f"<FocusEntry>{focus_entry}</FocusEntry>")
    return ("<?xml version=\"1.0\" encoding=\"utf-8\"?><RadioInfo>"
            + "".join(parts) + "</RadioInfo>").encode("utf-8")


R1 = dict(nr=1, freq_10hz=704032, mode="CW", hwnd=1111)
R2 = dict(nr=2, freq_10hz=2130000, mode="USB", hwnd=2222)


def test_zwei_radios_im_wechsel_folgen_dem_fokus():
    r = RadioInfoListener(port=0)
    for p in (R1, R2, R1, R2):              # letztes Paket: Radio 2
        r._parse(pkt(**p, focus=1, focus_entry=1111))
    assert r.radio_nr == 1 and r.freq_khz == 7040.32 and r.mode == "CW"
    assert r.multi and set(r.radios) == {1, 2}
    assert r.radios[2].freq_khz == 21300.0
    assert r.entry_candidates() == [1111]


def test_fokuswechsel_nimmt_das_andere_radio():
    r = RadioInfoListener(port=0)
    r._parse(pkt(**R1, focus=1, focus_entry=1111))
    r._parse(pkt(**R2, focus=1, focus_entry=1111))
    r._parse(pkt(**R2, focus=2, focus_entry=2222))     # Taste \ in N1MM
    assert r.radio_nr == 2 and r.freq_khz == 21300.0 and r.mode == "USB"
    assert r.entry_candidates() == [2222]
    r._parse(pkt(**R1, focus=1, focus_entry=1111))
    assert r.radio_nr == 1 and r.freq_khz == 7040.32


def test_ohne_fokusfeld_gilt_radio_1():
    r = RadioInfoListener(port=0)
    r._parse(pkt(**R1))
    r._parse(pkt(**R2))
    assert r.radio_nr == 1 and r.freq_khz == 7040.32
    assert r.entry_candidates() == [1111]


def test_ein_radio_wie_bisher():
    r = RadioInfoListener(port=0)
    r._parse(b"<RadioInfo><Freq>1402500</Freq><Mode>CW</Mode><OpCall>DF1DS</OpCall></RadioInfo>")
    assert r.radio_nr == 1 and r.freq_khz == 14025.0 and not r.multi
    assert r.entry_candidates() == [] and r.connected


def test_fokus_radio_ohne_eigenes_paket_hat_keine_frequenz():
    """Lieber keine Frequenz als die des anderen Radios."""
    r = RadioInfoListener(port=0)
    r._parse(pkt(**R1, focus=2))
    assert r.radio_nr == 2 and r.freq_khz is None
    assert r.entry_candidates() == []


def test_handle_in_hex_und_kaputte_werte():
    r = RadioInfoListener(port=0)
    r._parse(b"<RadioInfo><RadioNr>x</RadioNr><Freq>abc</Freq>"
             b"<EntryWindowHwnd>0x1A2B</EntryWindowHwnd><FocusRadioNr></FocusRadioNr></RadioInfo>")
    assert r.radio_nr == 1 and r.freq_khz is None and r.radios[1].entry_hwnd == 0x1A2B


@pytest.fixture
def bridge():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    b = N1MMBridge(udp_port=0, spot_port=0, rpc_port=port, engine=False, spot=False)
    yield b
    b.stop()


def test_spot_frequenz_folgt_dem_fokus(bridge):
    for p in (R1, R2, R1, R2):
        bridge.radio._parse(pkt(**p, focus=1))
    assert bridge.freq_khz == 7040.32
    bridge.radio._parse(pkt(**R2, focus=2))
    assert bridge.freq_khz == 21300.0


def test_bridge_gibt_handles_und_radio_an_den_typer(bridge):
    class Typer:
        available, wipe, last_error = True, True, None

        def type_call(self, call, candidates=(), slot=None):
            self.got = (call, list(candidates), slot)
            return True, "getippt"
    bridge.typer = Typer()
    bridge.configure(type_call=True)
    bridge.radio._parse(pkt(**R1, focus=2, focus_entry=2222))
    bridge.radio._parse(pkt(**R2, focus=2, focus_entry=2222))
    bridge.send_call("DL1ABC")
    assert bridge.typer.got == ("DL1ABC", [2222], 2)


# -- Fensterwahl -------------------------------------------------------------
class FakeTyper(EntryWindowTyper):
    """EntryWindowTyper ohne echte Fenster: gültige Handles und Fensterliste
    vorgegeben, Vordergrund und Tastendrücke werden mitgeschrieben."""

    def __init__(self, valid=(), windows=()):
        super().__init__()
        self.available = True
        self.valid = set(valid)
        self.windows = list(windows)
        self.front = []
        self.keys = []

    def window_ok(self, hwnd):
        return hwnd in self.valid

    def process_windows(self):
        return self.windows

    def _bring_to_front(self, hwnd, wait_s=0.25):
        self.front.append(hwnd)
        return True

    def _send_inputs(self, inputs):
        self.keys.append(list(inputs))


@pytest.fixture
def titles(monkeypatch):
    monkeypatch.setattr(n1mm, "_window_title", lambda h: f"Fenster {h}")


def test_handle_vor_focus_entry_vor_titel(titles):
    wins = [(10 + i, t) for i, t in enumerate(LOG_TITLES)]
    t = FakeTyper(valid={1111, 2222}, windows=wins)
    assert t.find_window([1111, 2222], 1)[0] == 1111
    t.valid = {2222}                                    # Handle veraltet
    assert t.find_window([1111, 2222], 1)[0] == 2222
    t.valid = set()                                     # beide veraltet: Titel
    assert t.find_window([1111, 2222], 2) == (16, "21300.00 USB Manual Radio 2 ")
    assert t.find_window([], None) == (10, "7040.32 CW Manual Radio 1 ")


def test_wipe_und_rufzeichen_ans_selbe_fenster(titles):
    t = FakeTyper(valid={2222})
    ok, _msg = t.type_call("DL1ABC", [2222], 2)
    assert ok and t.front == [2222]
    alt_w, typed = t.keys
    assert [k[0] for k in alt_w] == [0x12, ord("W"), ord("W"), 0x12]
    assert "".join(chr(k[1]) for k in typed[::2]) == "DL1ABC"


def test_titel_aus_dem_shack_log():
    wins = [(i, t) for i, t in enumerate(LOG_TITLES)]
    assert pick_entry_window(wins) == (0, "7040.32 CW Manual Radio 1 ")
    assert pick_entry_window(wins, 2) == (6, "21300.00 USB Manual Radio 2 ")
    assert pick_entry_window(wins, "B") == (6, "21300.00 USB Manual Radio 2 ")
    for bandmap in ("Manual Radio 1", "Available Radio 1 7040.32 CW", "Telnet",
                    "CW Reader 1", "GlassPanelForm"):
        assert not n1mm.ENTRY_TITLE_RE.match(bandmap), bandmap
    assert pick_entry_window([(3, "Manual Radio 1"), (4, "Available Radio 1 7040.32 CW")]) is None


def test_vfo_titel_weiter_erkannt():
    wins = [(4, "14053.63 CW Elecraft K3 VFO B"), (5, "21050.00+0.00 CW Elecraft K3 VFO A")]
    assert pick_entry_window(wins)[0] == 5
    assert pick_entry_window(wins, 2)[0] == 4


@pytest.mark.skipif(sys.platform != "win32", reason="nur unter Windows")
def test_ungueltiges_handle_ist_nicht_ok():
    t = EntryWindowTyper()
    assert not t.window_ok(0)
    assert not t.window_ok(0x7FFFFFF0)
    # gültiges Fenster, aber nicht von N1MM (Desktop gehört einem anderen Prozess)
    import ctypes
    assert not t.window_ok(ctypes.windll.user32.GetDesktopWindow())

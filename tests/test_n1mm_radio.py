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
    vorgegeben, Vordergrund und Tastendrücke werden mitgeschrieben. Das
    Rufzeichenfeld (Fokus) wird nachgebildet: Alt+W leert es nur, wenn
    wipe_works; Pos1/Umschalt+Ende/Entf leert es; Zeichen werden angehängt."""

    def __init__(self, valid=(), windows=(), field="", wipe_works=True, focus_after=0):
        super().__init__()
        self.available = True
        self.valid = set(valid)
        self.windows = list(windows)
        self.front = []
        self.keys = []
        self.field = field
        self.wipe_works = wipe_works
        self.focus_after = focus_after      # so oft fragt _focus_in, bevor der Fokus da ist
        self.events = []                    # Reihenfolge: front, focus?, keys

    def window_ok(self, hwnd):
        return hwnd in self.valid

    def process_windows(self):
        return self.windows

    def _bring_to_front(self, hwnd, wait_s=0.25):
        self.front.append(hwnd)
        self.events.append("front")
        return True

    def _focus_in(self, hwnd):
        if self.focus_after > 0:
            self.focus_after -= 1
            self.events.append("kein Fokus")
            return None
        return 4711

    def _field_text(self, field):
        return self.field if field else None

    def _send_inputs(self, inputs):
        inputs = list(inputs)
        self.keys.append(inputs)
        vks = [k[0] for k in inputs]
        if vks[:2] == [0x12, ord("W")]:
            self.events.append("Alt+W")
            if self.wipe_works:
                self.field = ""
        elif 0x2E in vks:
            self.events.append("leeren")
            self.field = ""
        else:
            self.events.append("tippen")
            self.field += "".join(chr(k[1]) for k in inputs[::2])


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
    t = FakeTyper(valid={2222}, field="ET9ECY")
    ok, _msg = t.type_call("DL1ABC", [2222], 2)
    assert ok and t.front == [2222]
    alt_w, typed = t.keys
    assert [k[0] for k in alt_w] == [0x12, ord("W"), ord("W"), 0x12]
    if sys.platform == "win32":
        assert all(k[1] for k in alt_w)            # mit Scan-Codes wie echte Tasten
    assert "".join(chr(k[1]) for k in typed[::2]) == "DL1ABC"
    assert t.field == "DL1ABC"


def test_zweimal_dasselbe_dann_ein_anderes(titles):
    """Shack-Test beta21: zweimal ET9ECY ergab ET9ECYET9ECY. Im Feld steht
    nach jedem Klick genau das angeklickte Rufzeichen."""
    t = FakeTyper(valid={2222})
    for call in ("ET9ECY", "ET9ECY", "DL1ABC"):
        t.type_call(call, [2222], 1)
        assert t.field == call


def test_wipe_kommt_nicht_an_feld_wird_selbst_geleert(titles, monkeypatch):
    monkeypatch.setattr(n1mm, "WIPE_WAIT_S", 0.05)
    t = FakeTyper(valid={2222}, field="ET9ECY", wipe_works=False)
    t.type_call("ET9ECY", [2222], 1)
    assert t.events == ["front", "Alt+W", "leeren", "tippen"]
    assert t.field == "ET9ECY"


def test_wartet_auf_den_fokus_vor_den_tasten(titles):
    """Erst wenn N1MM den Tastaturfokus im Entry Window hat, kommen Tasten."""
    t = FakeTyper(valid={2222}, field="X", focus_after=3)
    t.type_call("DL1ABC", [2222], 1)
    assert t.events[:5] == ["front", "kein Fokus", "kein Fokus", "kein Fokus", "Alt+W"]
    assert t.field == "DL1ABC"


def test_ohne_wipe_nur_das_feld_leeren(titles):
    t = FakeTyper(valid={2222}, field="ET9ECY")
    t.wipe = False
    t.type_call("DL1ABC", [2222], 1)
    assert "Alt+W" not in t.events and t.events[-2:] == ["leeren", "tippen"]
    assert t.field == "DL1ABC"
    t2 = FakeTyper(valid={2222}, field="")
    t2.wipe = False
    t2.type_call("DL1ABC", [2222], 1)
    assert t2.events == ["front", "tippen"]         # leeres Feld: nichts zu tun


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

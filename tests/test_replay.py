# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""„Nochmal hören“ mit gefälschtem sounddevice.OutputStream (ADR-0024, #19)."""
import threading
import time
import types

import numpy as np
import pytest

from cwdecoder.replay import Player, ReplayError, SLOW_RATE, prepare, stretch


def fake_sd(ok_rates=(8000, 48000, 44100), fail=None, delay=0.0):
    """Attrappe: OutputStream sammelt die geschriebenen Daten."""
    log = {"streams": []}

    class OutputStream:
        def __init__(self, samplerate, channels, dtype, device=None):
            if fail is not None:
                raise fail
            if samplerate not in ok_rates:
                raise RuntimeError(f"Invalid sample rate {samplerate}")
            assert channels == 1 and dtype == "float32"
            self.samplerate = samplerate
            self.data = []
            self.events = []
            log["streams"].append(self)

        def start(self):
            self.events.append("start")

        def write(self, chunk):
            assert chunk.ndim == 2 and chunk.shape[1] == 1
            self.data.append(chunk[:, 0].copy())
            if delay:
                time.sleep(delay)

        def stop(self):
            self.events.append("stop")

        def abort(self):
            self.events.append("abort")

        def close(self):
            self.events.append("close")

        @property
        def written(self):
            return np.concatenate(self.data) if self.data else np.zeros(0, np.float32)

    return types.SimpleNamespace(OutputStream=OutputStream, log=log)


def _tone(fs, secs, f=700.0):
    t = np.arange(int(fs * secs)) / fs
    return (0.1 * np.sin(2 * np.pi * f * t)).astype(np.float32)


def _play(player, samples, fs, **kw):
    done = threading.Event()
    result = {}

    def on_done(err):
        result["err"] = err
        done.set()
    assert player.start(samples, fs, on_done=on_done, **kw)
    return done, result


def test_daten_und_laenge_stimmen():
    sd = fake_sd()
    fs = 8000
    x = _tone(fs, 10.0)
    done, res = _play(Player(sd=sd), x, fs)
    assert done.wait(5)
    assert res["err"] is None
    s = sd.log["streams"][0]
    assert s.samplerate == fs and s.events == ["start", "stop", "close"]
    np.testing.assert_allclose(s.written, prepare(x, fs), atol=1e-6)
    assert len(s.written) == len(x)
    assert np.max(np.abs(s.written)) == pytest.approx(0.5, abs=0.01)   # Pegel angeglichen


def test_abbruch_und_zweiter_start_abgelehnt():
    sd = fake_sd(delay=0.02)                 # 50 ms Audio je 20 ms Schreiben
    fs = 8000
    p = Player(sd=sd)
    done, res = _play(p, _tone(fs, 10.0), fs)
    time.sleep(0.1)
    assert p.playing
    assert p.start(_tone(fs, 1.0), fs) is False          # kein zweiter Replay parallel
    p.stop()
    assert done.wait(5)
    assert res["err"] is None and p.stop_requested and not p.playing
    s = sd.log["streams"][0]
    assert len(sd.log["streams"]) == 1
    assert 0 < len(s.written) < 10 * fs
    assert s.events[-2:] == ["abort", "close"]


def test_ohne_ausgabegeraet_klartextfehler():
    from cwdecoder.gui_errors import classify_error
    sd = fake_sd(fail=RuntimeError("Error querying device -1"))
    done, res = _play(Player(sd=sd), _tone(8000, 1.0), 8000)
    assert done.wait(5)
    assert isinstance(res["err"], ReplayError)
    info = classify_error(res["err"])
    assert info.expected and info.title == "Wiedergabe nicht möglich"


def test_rate_nicht_moeglich_wird_umgerechnet():
    sd = fake_sd(ok_rates=(48000,))
    fs = 8000
    x = _tone(fs, 2.0)
    done, res = _play(Player(sd=sd), x, fs)
    assert done.wait(5) and res["err"] is None
    s = sd.log["streams"][0]
    assert s.samplerate == 48000
    assert abs(len(s.written) - 6 * len(x)) <= 6
    spec = np.abs(np.fft.rfft(s.written))
    assert np.argmax(spec) * 48000 / len(s.written) == pytest.approx(700, abs=2)


@pytest.mark.parametrize("fs", [8000, 48000])
def test_langsamer_ohne_tonhoehe(fs):
    from cwdecoder.decode_wav import decode_signal
    from cwdecoder.gen import render
    x = render("CQ DE DL1ABC K", fs=fs, wpm=28, snr_db=12, seed=4).astype(np.float32)
    y = stretch(x, fs)
    assert len(y) == pytest.approx(len(x) / SLOW_RATE, abs=2)

    def peak(s):
        return np.argmax(np.abs(np.fft.rfft(s))) * fs / len(s)
    assert peak(y) == pytest.approx(peak(x), abs=2)
    # Die gedehnte Fassung bleibt decodierbar. Im reinen Rauschen davor kann
    # die Dehnung kurze Scheintöne bilden (vereinzelt ein „E“); zum Hören egal
    dec, _ = decode_signal(y, fs)
    assert " ".join("".join(dec.text).split()).endswith("CQ DE DL1ABC K")
    # Player mit Tempo 0,7 schreibt die gedehnte Fassung
    sd = fake_sd()
    done, res = _play(Player(sd=sd), x, fs, rate=SLOW_RATE)
    assert done.wait(10) and res["err"] is None
    assert len(sd.log["streams"][0].written) == len(y)


# -- #25: Tempo je Block, Festhalten mit Verfall, Ausgabegerät -------------
from cwdecoder.replay import (OutputDeviceMissingError, ReplayHold, Stretcher,  # noqa: E402
                              find_output, output_devices)
from cwdecoder.ringbuffer import AudioRing, TokenRing, save_clip  # noqa: E402


def _peak_hz(s, fs):
    return np.argmax(np.abs(np.fft.rfft(s))) * fs / len(s)


@pytest.mark.parametrize("rate", [0.5, 0.75])
def test_tonhoehe_bleibt(rate):
    fs = 8000
    x = _tone(fs, 3.0, f=650.0)
    y = stretch(x, fs, rate)
    assert len(y) == pytest.approx(len(x) / rate, abs=2)
    assert _peak_hz(y, fs) == pytest.approx(650.0, abs=2)


def test_tempo_wechsel_mitten_im_durchgang():
    """Erste Hälfte des Eingangs mit 1,0, dann 0,5: die zweite Hälfte dauert
    doppelt so lange, die Tonhöhe bleibt in beiden Teilen."""
    fs = 8000
    x = _tone(fs, 4.0, f=700.0)
    st = Stretcher(x, fs)
    first, second = [], []
    while not st.done:
        if st._consumed < len(x) / 2:
            first.append(st.read(1.0))
        else:
            second.append(st.read(0.5))
    a, b = np.concatenate(first), np.concatenate(second)
    assert len(a) == pytest.approx(len(x) / 2, abs=st.hs)
    assert len(b) == pytest.approx(len(x), abs=2 * st.hs)          # halbe Geschwindigkeit
    assert _peak_hz(a, fs) == pytest.approx(700, abs=2)
    assert _peak_hz(b[st.n:], fs) == pytest.approx(700, abs=2)


def test_tempo_eins_reicht_original_durch():
    fs = 8000
    x = np.random.default_rng(1).normal(0, 0.1, fs).astype(np.float32)
    np.testing.assert_allclose(stretch(x, fs, 1.0), x, atol=1e-6)


def test_player_liest_tempo_je_block():
    sd = fake_sd()
    fs = 8000
    x = _tone(fs, 2.0)
    rates = iter([1.0] * 10 + [0.5] * 10_000)                     # nach 10 Blöcken langsamer
    done, res = _play(Player(sd=sd), x, fs, rate=lambda: next(rates))
    assert done.wait(10) and res["err"] is None
    n = len(sd.log["streams"][0].written)
    hs = Stretcher(x, fs).hs
    assert n == pytest.approx(10 * hs + (len(x) - 10 * hs) / 0.5, abs=2 * hs)


class _Clock:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t


def _ring(fs=100, seconds=60):
    ring = AudioRing(fs, seconds)
    return ring


def test_festhalten_zustandsautomat():
    """Fassen -> spielen -> innerhalb der Frist dasselbe -> nach der Frist neu."""
    clock = _Clock()
    hold = ReplayHold(hold_s=1.0, clock=clock)
    ring = _ring()
    ring.write(np.arange(1000, dtype=np.float32))
    clip, fresh = hold.grab(ring, 5)
    assert fresh and clip.seconds == 5.0 and clip.samples[-1] == 999
    hold.started()
    ring.write(np.full(300, -1, dtype=np.float32))                 # Ring läuft weiter
    clock.t += 30                                                  # lange Wiedergabe
    assert hold.active() and hold.remaining() == 1.0
    hold.finished()                                                # Frist ab Ende
    clock.t += 0.6
    again, fresh = hold.grab(ring, 5)
    assert again is clip and not fresh                             # gleiches Material
    hold.started()
    hold.finished()
    clock.t += 0.9
    assert hold.active() and hold.remaining() == pytest.approx(0.1)
    clock.t += 0.2                                                 # Frist um
    assert not hold.active() and hold.expire_if_due() and hold.clip is None
    new, fresh = hold.grab(ring, 5)
    assert fresh and new is not clip and new.samples[-1] == -1     # neues Material


def test_festhalten_leerer_ring():
    hold = ReplayHold(5)
    clip, fresh = hold.grab(_ring(), 5)
    assert clip is None and not hold.active()


def test_festgehaltenes_speichern(tmp_path):
    """Strg+S während des Festhaltens: genau dieses Material plus Tokens."""
    clock = _Clock()
    hold = ReplayHold(5, clock=clock)
    ring = _ring(fs=1000, seconds=60)
    tokens = TokenRing(60)
    ring.write(np.linspace(-0.5, 0.5, 10_000).astype(np.float32))  # 10 s
    tokens.add(6.0, "C", 1.0)
    tokens.add(9.5, "Q", 0.4)
    tokens.add(2.0, "X", 1.0)                                      # vor dem Fenster
    clip, _ = hold.grab(ring, 5, tokens)
    ring.write(np.zeros(3000, dtype=np.float32))                   # später Gehörtes
    tokens.add(12.0, "Z", 1.0)
    wav, secs = save_clip(tmp_path, clip)
    assert wav.endswith("_festgehalten.wav") and secs == 5.0
    from scipy.io import wavfile
    fs, data = wavfile.read(wav)
    assert fs == 1000 and len(data) == 5000 and data[0] > 0 and data[-1] > 15000
    lines = open(wav[:-4] + ".txt", encoding="utf-8").read().splitlines()
    assert lines == ["1.00;C;1.00", "4.50;Q;0.40"]


def _fake_sd_devices():
    sd = fake_sd()
    sd.query_devices = lambda: [
        {"name": "Mikrofon (USB Audio)", "max_input_channels": 1, "max_output_channels": 0},
        {"name": "Lautsprecher (Realtek)", "max_input_channels": 0, "max_output_channels": 2},
        {"name": "Kopfhörer (USB Audio)", "max_input_channels": 0, "max_output_channels": 2},
        {"name": "Lautsprecher (Realtek)", "max_input_channels": 0, "max_output_channels": 2},
    ]
    return sd


def test_ausgabegeraete_und_suche():
    sd = _fake_sd_devices()
    assert output_devices(sd) == ["Lautsprecher (Realtek)", "Kopfhörer (USB Audio)"]
    assert find_output(None, sd) is None
    assert find_output("kopfhörer", sd) == 2                       # Namensteil, Groß/klein
    assert find_output("USB Audio", sd) == 2                       # nur Ausgänge
    with pytest.raises(OutputDeviceMissingError):
        find_output("Bluetooth", sd)


def test_fehlendes_geraet_rueckfall_standard():
    from cwdecoder.gui_errors import classify_error
    sd = _fake_sd_devices()
    p = Player(sd=sd)
    done, res = _play(p, _tone(8000, 0.5), 8000, device="Bluetooth")
    assert done.wait(5) and res["err"] is None                     # gespielt, nur anders
    assert isinstance(p.fallback, OutputDeviceMissingError)
    info = classify_error(p.fallback)
    assert info.expected and info.title == "Ausgabegerät nicht gefunden"
    assert "Standard-Ausgabe" in info.status


def test_gewaehltes_geraet_wird_benutzt():
    sd = _fake_sd_devices()
    opened = []
    orig = sd.OutputStream

    def stream(samplerate, channels, dtype, device=None):
        opened.append(device)
        return orig(samplerate, channels, dtype)
    sd.OutputStream = stream
    p = Player(sd=sd)
    done, res = _play(p, _tone(8000, 0.5), 8000, device="Kopfhörer")
    assert done.wait(5) and res["err"] is None and p.fallback is None
    assert opened == [2]

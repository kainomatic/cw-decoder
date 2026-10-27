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
        def __init__(self, samplerate, channels, dtype):
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
    # Player mit slow=True schreibt die gedehnte Fassung
    sd = fake_sd()
    done, res = _play(Player(sd=sd), x, fs, slow=True)
    assert done.wait(10) and res["err"] is None
    assert len(sd.log["streams"][0].written) == len(y)

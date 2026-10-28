# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""CW Decoder als Engine für N1MMs CW Reader mit Beispielsignal (Dev-Werkzeug, #24).

    python tools/n1mm_demo_engine.py

Für das N1MM-Foto im Handbuch (docs/handbuch/img/n1mm-cwreader.png): startet
die Oberfläche wie `CWDecoder.exe --n1mm-engine` (Instanz-Lock, Engine auf
Port 7367), aber mit einer Attrappe der Soundkarte, die in Echtzeit
`CQ TEST DE DL1ABC DL1ABC TEST DR2ABC 5NN 14 TU` sendet (nur
Beispiel-Rufzeichen, #24). Der Decoder startet von selbst. Öffnet N1MM
danach seinen CW Reader, findet die von N1MM gestartete zweite Instanz
diese hier und beendet sich (ADR-0020); N1MM liest den Text von hier.
Beenden über das Fenster.
"""
import sys
import threading
import time
import types
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

TEXT = "CQ TEST DE DL1ABC DL1ABC TEST DR2ABC 5NN 14 TU"
FS = 8000


def fake_sounddevice():
    from cwdecoder.gen import render
    sig = np.concatenate([render(TEXT, fs=FS, wpm=24, pitch=700, snr_db=22, seed=k,
                                 lead_s=1.5, tail_s=2.0).astype(np.float32)
                          for k in range(3)])
    sd = types.ModuleType("sounddevice")
    sd.default = types.SimpleNamespace(device=[1, 0])

    def query_devices(*_a):
        return [{"name": "Lautsprecher", "max_input_channels": 0, "max_output_channels": 2},
                {"name": "USB Audio CODEC", "max_input_channels": 1, "max_output_channels": 0}]

    class InputStream:
        def __init__(self, device, channels, samplerate, blocksize, dtype, callback):
            if samplerate != FS:
                raise RuntimeError("nur 8 kHz")
            self.cb, self.bs, self.running = callback, blocksize, False

        def start(self):
            self.running = True
            threading.Thread(target=self._loop, daemon=True).start()

        def _loop(self):
            pos, t0 = 0, time.monotonic()
            while self.running:
                blk = sig[pos:pos + self.bs]
                if len(blk) < self.bs:
                    pos = 0
                    continue
                pos += self.bs
                self.cb(blk.reshape(-1, 1), self.bs, None, None)
                t0 += self.bs / FS
                time.sleep(max(0.0, t0 - time.monotonic()))

        def stop(self):
            self.running = False

        def close(self):
            pass

    sd.query_devices = query_devices
    sd.InputStream = InputStream
    return sd


def main():
    sys.modules["sounddevice"] = fake_sounddevice()
    from cwdecoder import gui, gui_start
    orig = gui.App.schedule_update_check

    def start_decoder(app):
        app.dev_var.set(next((d for d in app.dev_box["values"] if "USB" in d),
                             app.dev_var.get()))
        app.auto_var.set(True)
        app.after(800, app._toggle)
    gui.App.schedule_update_check = lambda self: start_decoder(self)
    try:
        gui_start.main(["--n1mm-engine"])
    finally:
        gui.App.schedule_update_check = orig


if __name__ == "__main__":
    main()

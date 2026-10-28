# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""Bildschirmfotos für das Handbuch erzeugen (Dev-Werkzeug, #24, ADR-0027).

    python tools/make_docs_images.py              alle Bilder nach docs/handbuch/img/
    python tools/make_docs_images.py --out DIR    anderes Ziel (Vergleich)

Nur Windows. Startet die echte Oberfläche mit einer Attrappe der Soundkarte
und einem **synthetischen** Signal mit Beispiel-Rufzeichen (DR2ABC, OY1ABC,
DF1DSE, DF1DS; keine echten fremden Rufzeichen, Regel #24). Die Blöcke
werden im Hauptthread eingespeist, der Decoder-Thread arbeitet sie ab; so
entsteht bei gleichem Code dasselbe Bild. Keine Klicks, keine Bildschirm-
kopie: jedes Fenster per PrintWindow (geht auch ohne aktive RDP-Sitzung).

Fenster 900×600 Pixel bei 100 %. Der Prozess ist DPI-bewusst und zeichnet
in der Skalierung des Rechners (Titelleiste, Menü, Haken und Inhalt
einheitlich); die Fotos werden danach auf 100 % verkleinert. So sehen sie
auf jedem Rechner gleich aus, auch bei 150 oder 200 %.

Erzeugt: hauptfenster.png, text-farben.png, knoepfe.png, vorschlag.png,
nochmal.png, uebergabe.png. Das N1MM-Foto (n1mm-cwreader.png) entsteht von
Hand am echten N1MM (docs/handbuch/README.md).
"""
import argparse
import ctypes
import os
import sys
import tempfile
import threading
import time
import types
from ctypes import wintypes
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUT_DEFAULT = ROOT / "docs" / "handbuch" / "img"

FS = 8000
BLOCK = 160                     # 20 ms wie die GUI
# Signal aus dem Prototyp der Desktop-Session (#24); Pausen aus Rauschen
SEGMENTS = (
    ("CQ CQ DE DR2ABC DR2ABC K", 0.0, 11),
    ("DR2ABC DE OY1ABC GE TNXFERFBCALL UR RST 599 5NN BK", 0.0, 12),
    ("QRZ DE DF1DSE K", 0.0, 13),
    ("DR2ABC DE DF1DS FB OM HW", 0.17, 14),
)
WIN_W, WIN_H = 900, 600


# -- Signal ------------------------------------------------------------------
def make_signal():
    from cwdecoder.gen import render
    parts = [render(text, fs=FS, wpm=24, pitch=700, snr_db=22, jitter=jit, seed=seed,
                    lead_s=2.0, tail_s=1.6).astype(np.float32)
             for text, jit, seed in SEGMENTS]
    return parts


# -- Attrappe der Soundkarte -------------------------------------------------
def fake_sounddevice():
    sd = types.ModuleType("sounddevice")
    sd.default = types.SimpleNamespace(device=[1, 0])
    sd.streams = []

    def query_devices(*_a):
        return [{"name": "Lautsprecher", "max_input_channels": 0, "max_output_channels": 2},
                {"name": "USB Audio CODEC", "max_input_channels": 1, "max_output_channels": 0}]

    class InputStream:
        def __init__(self, device, channels, samplerate, blocksize, dtype, callback):
            if samplerate != FS:
                raise RuntimeError("nur 8 kHz")
            self.cb = callback
            sd.streams.append(self)

        def start(self):
            pass

        def stop(self):
            pass

        def close(self):
            pass

    class OutputStream:
        def __init__(self, samplerate, channels, dtype, device=None):
            self.samplerate = samplerate

        def start(self):
            pass

        def write(self, chunk):
            time.sleep(len(chunk) / self.samplerate / 20)

        def stop(self):
            pass

        def abort(self):
            pass

        def close(self):
            pass

    sd.query_devices = query_devices
    sd.InputStream = InputStream
    sd.OutputStream = OutputStream
    return sd


# -- PrintWindow -------------------------------------------------------------
u32 = ctypes.windll.user32 if sys.platform == "win32" else None
g32 = ctypes.windll.gdi32 if sys.platform == "win32" else None
PW_RENDERFULLCONTENT = 2


class _BMI(ctypes.Structure):
    _fields_ = [("biSize", ctypes.c_uint32), ("biWidth", ctypes.c_int32),
                ("biHeight", ctypes.c_int32), ("biPlanes", ctypes.c_uint16),
                ("biBitCount", ctypes.c_uint16), ("biCompression", ctypes.c_uint32),
                ("rest", ctypes.c_uint32 * 6)]


def window_rect(hwnd):
    r = wintypes.RECT()
    u32.GetWindowRect(hwnd, ctypes.byref(r))
    return r.left, r.top, r.right, r.bottom


def print_window(hwnd):
    """Bild des ganzen Fensters (mit Rahmen und Titel) als PIL-Image."""
    from PIL import Image
    u32.RedrawWindow(hwnd, None, None, 0x0001 | 0x0004 | 0x0080 | 0x0100)
    left, top, right, bottom = window_rect(hwnd)
    w, h = right - left, bottom - top
    hdc = u32.GetWindowDC(hwnd)
    mdc = g32.CreateCompatibleDC(hdc)
    bmp = g32.CreateCompatibleBitmap(hdc, w, h)
    g32.SelectObject(mdc, bmp)
    u32.PrintWindow(hwnd, mdc, PW_RENDERFULLCONTENT)
    bmi = _BMI(ctypes.sizeof(_BMI), w, -h, 1, 32, 0)
    buf = ctypes.create_string_buffer(w * h * 4)
    g32.GetDIBits(mdc, bmp, 0, h, buf, ctypes.byref(bmi), 0)
    g32.DeleteObject(bmp)
    g32.DeleteDC(mdc)
    u32.ReleaseDC(hwnd, hdc)
    return Image.frombuffer("RGB", (w, h), buf, "raw", "BGRX", 0, 1)


def hwnd_of(toplevel):
    return int(toplevel.wm_frame(), 16)


# -- Ablauf ------------------------------------------------------------------
class Shooter:
    def __init__(self, out):
        self.out = Path(out)
        self.out.mkdir(parents=True, exist_ok=True)
        self.written = []

    def start_app(self):
        from cwdecoder import config
        from cwdecoder.gui import App
        cfg = dict(config.defaults(), device_name="USB Audio CODEC")
        self.app = app = App(cfg=cfg, config_path=None)
        self.scale = app.winfo_fpixels("1i") / 96.0      # 2,0 bei 200 %
        app.geometry(f"{round(WIN_W * self.scale)}x{round(WIN_H * self.scale)}+30+30")
        app.update()
        self.pump(0.3)

    def pump(self, seconds=0.0, until=None):
        end = time.time() + seconds
        while True:
            self.app.update()
            if until is not None and until():
                return True
            if time.time() >= end:
                return until is None
            time.sleep(0.01)

    def settle(self):
        """Warten, bis der Decoder alle Blöcke verarbeitet und die GUI alle
        Meldungen geholt hat."""
        live = self.app.live
        self.pump(20, until=live.q.empty)
        self.pump(0.5)

    def feed(self, x):
        cb = sys.modules["sounddevice"].streams[-1].cb
        live = self.app.live
        for i in range(0, len(x) - BLOCK + 1, BLOCK):
            cb(x[i:i + BLOCK].reshape(-1, 1), BLOCK, None, None)
            if live.q.qsize() > 200:
                self.pump(0.02)
        self.settle()

    def save(self, img, name):
        from PIL import Image
        if abs(self.scale - 1.0) > 0.01:
            img = img.resize((round(img.width / self.scale), round(img.height / self.scale)),
                             Image.LANCZOS)
        path = self.out / name
        img.save(path, optimize=True)
        self.written.append(path)
        print(f"{name}: {img.size[0]}×{img.size[1]}")

    def client_box(self, widget, pad=0):
        """Lage eines Widgets im Bild des Hauptfensters."""
        left, top, _r, _b = window_rect(hwnd_of(self.app))
        x = widget.winfo_rootx() - left
        y = widget.winfo_rooty() - top
        return (x - pad, y - pad, x + widget.winfo_width() + pad,
                y + widget.winfo_height() + pad)

    def run(self):
        app = self.app
        parts = make_signal()
        # Spektrum während der letzten Station: Signal bis kurz vor ihr Ende
        app._toggle()
        self.pump(0.2)
        for p in parts[:-1]:
            self.feed(p)
        last = parts[-1]
        cut = int(len(last) * 0.78)
        self.feed(last[:cut])
        app._draw_spectrum()
        # Statuszeile aus dem Decoderzustand (sonst Zahlen vom Sekundentakt)
        app._show_status(app.live.dec.status)
        self.pump(0.3)
        app._show_status(app.live.dec.status)
        app.update_idletasks()
        self.save(print_window(hwnd_of(app)), "hauptfenster.png")
        self.feed(last[cut:])
        self.feed(np.random.default_rng(3).normal(0, 0.02, FS * 4).astype(np.float32))
        app.text.see("1.0")
        self.pump(0.3)
        full = print_window(hwnd_of(app))
        self.save(full.crop(self.text_box()), "text-farben.png")
        self.save(full.crop(self.calls_box()), "knoepfe.png")
        self.vorschlag(full)
        self.nochmal()
        self.uebergabe()

    def text_box(self):
        """Textfeld bis knapp unter die letzte Zeile."""
        app = self.app
        x0, y0, x1, _y1 = self.client_box(app.text)
        _x, ly, _w, lh = app.text.bbox("end-1c linestart")
        return (x0, y0, x1, y0 + ly + lh + round(10 * self.scale))

    def calls_box(self):
        """Überschrift der Rufzeichen-Spalte bis zum letzten Knopf."""
        app = self.app
        rows = [p["row"] for p in app.call_rows.values()]
        x0, _y0, x1, _y1 = self.client_box(app.call_frame, pad=2)
        y0 = min(self.client_box(app.call_frame, pad=2)[1],
                 self.client_box(app.right_col)[1])
        y1 = max(self.client_box(r)[3] for r in rows) + round(4 * self.scale)
        return (x0, y0, x1, y1)

    def vorschlag(self, full):
        from PIL import Image
        app = self.app
        parts = app.call_rows["DF1DSE"]
        tip = parts["call"]._cw_tooltip
        tip._show()
        self.pump(0.3)
        tip_img = print_window(hwnd_of(tip._win))
        tip._hide()
        box = self.calls_box()
        col = full.crop(box)
        bx0, by0, _bx1, by1 = self.client_box(parts["row"])
        cx0, cy0 = box[0], box[1]
        y = by1 - cy0 + round(4 * self.scale)
        x = max(0, bx0 - cx0 + round(24 * self.scale))
        w = max(col.width, x + tip_img.width + round(4 * self.scale))
        h = max(col.height, y + tip_img.height + round(6 * self.scale))
        img = Image.new("RGB", (w, h), (240, 240, 240))
        img.paste(col, (0, 0))
        img.paste(tip_img, (x, y))
        self.save(img, "vorschlag.png")

    def nochmal(self):
        app = self.app
        app.toggle_replay()
        self.pump(0.3)
        app.set_replay_rate(0.6)
        app.toggle_replay()                         # Stopp: bleibt festgehalten
        self.pump(5, until=lambda: app.replay_secs is None)
        app._toggle()                               # Decoder aus: Statuszeile nur Festhalten
        app._hold_shown = None
        self.pump(1.3, until=lambda: "noch 4 s" in app.status.get())
        app.status_note = None
        app._refresh_status()
        self.pump(0.1)
        full = print_window(hwnd_of(app))
        top2 = app.btn_save.master
        x0, y0, x1, _ = self.client_box(top2)
        _, _, _, y1 = self.client_box(app.status_label)
        self.save(full.crop((x0, y0 - 2, x1, y1 + 2)), "nochmal.png")

    def uebergabe(self):
        app = self.app
        dlg = app.open_n1mm_settings()
        self.pump(0.4)
        self.save(print_window(hwnd_of(dlg)), "uebergabe.png")
        dlg.close()
        self.pump(0.1)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--out", default=str(OUT_DEFAULT))
    a = p.parse_args(argv)
    if sys.platform != "win32":
        raise SystemExit("Nur unter Windows (PrintWindow)")
    ctypes.windll.user32.SetProcessDPIAware()
    os.environ["APPDATA"] = tempfile.mkdtemp(prefix="cwdoc-")
    os.environ["USERPROFILE"] = os.environ["APPDATA"]
    sys.modules["sounddevice"] = fake_sounddevice()
    s = Shooter(a.out)
    s.start_app()
    try:
        s.run()
    finally:
        s.app._quit()
    threading.Event().wait(0.2)
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Grafische Oberfläche: Spektrum, Live-Text, erkannte Rufzeichen, N1MM.

    python -m cwdecoder.gui
"""
import queue
import sys
import threading
import tkinter as tk
from tkinter import ttk
import numpy as np

from .decoder import DecoderConfig
from .live import LiveDecoder, open_stream, WavRecorder
from .n1mm import N1MMBridge


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CW Decoder")
        self.geometry("900x560")
        self.msgs = queue.Queue()
        self.live = None
        self.stream = None
        self.thread = None
        self.n1mm = None
        self.calls = []
        self._build()
        self._fill_devices()
        self.after(60, self._poll)
        self.protocol("WM_DELETE_WINDOW", self._quit)

    # ------------------------------------------------------------------
    def _build(self):
        top = ttk.Frame(self, padding=6)
        top.pack(fill="x")
        ttk.Label(top, text="Eingang:").pack(side="left")
        self.dev_var = tk.StringVar()
        self.dev_box = ttk.Combobox(top, textvariable=self.dev_var, width=40, state="readonly")
        self.dev_box.pack(side="left", padx=4)
        self.btn_start = ttk.Button(top, text="Start", command=self._toggle)
        self.btn_start.pack(side="left", padx=4)
        self.auto_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(top, text="Ton automatisch suchen", variable=self.auto_var,
                        command=self._auto_changed).pack(side="left", padx=8)
        self.rec_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(top, text="Aufnahme (WAV)", variable=self.rec_var).pack(side="left", padx=8)
        ttk.Button(top, text="Text löschen", command=self._clear).pack(side="right")

        self.status = tk.StringVar(value="bereit")
        ttk.Label(self, textvariable=self.status, anchor="w", padding=(8, 0)).pack(fill="x")

        self.canvas = tk.Canvas(self, height=110, bg="#101418", highlightthickness=0)
        self.canvas.pack(fill="x", padx=6, pady=(2, 4))
        self.canvas.bind("<Button-1>", self._spectrum_click)

        mid = ttk.Frame(self)
        mid.pack(fill="both", expand=True, padx=6)
        self.text = tk.Text(mid, wrap="word", font=("Consolas", 16), height=10)
        self.text.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(mid, command=self.text.yview)
        sb.pack(side="left", fill="y")
        self.text.configure(yscrollcommand=sb.set)

        right = ttk.Frame(mid, padding=(8, 0, 0, 0), width=200)
        right.pack(side="left", fill="y")
        ttk.Label(right, text="Rufzeichen (Klick → N1MM)").pack(anchor="w")
        self.call_frame = ttk.Frame(right)
        self.call_frame.pack(fill="both", expand=True)
        self.n1mm_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(right, text="N1MM-Anbindung", variable=self.n1mm_var,
                        command=self._n1mm_changed).pack(anchor="w", pady=(6, 0))
        self.wipe_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(right, text="vorher Alt+W (Wipe)", variable=self.wipe_var,
                        command=self._n1mm_changed).pack(anchor="w")
        self.n1mm_status = tk.StringVar(value="N1MM: –")
        ttk.Label(right, textvariable=self.n1mm_status, wraplength=190).pack(anchor="w", pady=4)
        self._n1mm_changed()

    def _fill_devices(self):
        try:
            import sounddevice as sd
        except Exception as e:  # noqa: BLE001
            self.status.set(f"sounddevice fehlt: {e}  (pip install sounddevice)")
            return
        self.devs = [(i, d["name"]) for i, d in enumerate(sd.query_devices())
                     if d["max_input_channels"] > 0]
        self.dev_box["values"] = [f"{i}: {n}" for i, n in self.devs]
        default = sd.default.device[0]
        for k, (i, _) in enumerate(self.devs):
            if i == default:
                self.dev_box.current(k)
                break
        else:
            if self.devs:
                self.dev_box.current(0)

    # ------------------------------------------------------------------
    def _toggle(self):
        if self.live:
            self._stop()
        else:
            self._start()

    def _start(self):
        if not self.dev_var.get():
            return
        idx = int(self.dev_var.get().split(":")[0])
        cfg = DecoderConfig()
        if not self.auto_var.get() and getattr(self, "fixed_freq", None):
            cfg.tracker.fixed_freq = self.fixed_freq
        holder = {}

        def cb(indata, frames, t, status):
            if "live" in holder:
                holder["live"].audio_callback(indata, frames, t, status)

        try:
            self.stream, fs = open_stream(idx, cb)
        except SystemExit as e:
            self.status.set(str(e))
            return
        self.live = LiveDecoder(fs, cfg,
                                on_text=lambda s: self.msgs.put(("text", s)),
                                on_status=lambda d: self.msgs.put(("status", d)),
                                on_call=lambda c: self.msgs.put(("call", c)))
        if self.rec_var.get():
            import time
            name = time.strftime("cw_%Y%m%d_%H%M%S.wav")
            self.live.recorder = WavRecorder(name, fs)
            self.msgs.put(("text", f"[Aufnahme: {name}]\n"))
        holder["live"] = self.live
        self.thread = threading.Thread(target=lambda: self.live.run(0.25), daemon=True)
        self.thread.start()
        self.btn_start.configure(text="Stop")

    def _stop(self):
        if self.live:
            self.live.stop()
        if self.stream:
            self.stream.stop()
            self.stream.close()
        if self.live and self.live.recorder:
            self.live.recorder.close()
        self.live = None
        self.stream = None
        self.btn_start.configure(text="Start")
        self.status.set("gestoppt")

    def _quit(self):
        self._stop()
        if self.n1mm:
            self.n1mm.stop()
        self.destroy()

    def _clear(self):
        self.text.delete("1.0", "end")

    def _auto_changed(self):
        if self.live:
            self.live.dec.set_fixed_frequency(None if self.auto_var.get()
                                              else getattr(self, "fixed_freq", None))

    def _spectrum_click(self, ev):
        if not self.live:
            return
        tr = self.live.dec.tracker
        f = tr.cfg.f_min + (tr.cfg.f_max - tr.cfg.f_min) * ev.x / max(self.canvas.winfo_width(), 1)
        self.fixed_freq = float(f)
        self.auto_var.set(False)
        self.live.dec.set_fixed_frequency(self.fixed_freq)

    def _n1mm_changed(self):
        if self.n1mm_var.get():
            if self.n1mm is None:
                self.n1mm = N1MMBridge(wipe=self.wipe_var.get())
            else:
                self.n1mm.typer.wipe = self.wipe_var.get()
        elif self.n1mm is not None:
            self.n1mm.stop()
            self.n1mm = None
            self.n1mm_status.set("N1MM: aus")

    # ------------------------------------------------------------------
    def _poll(self):
        try:
            while True:
                kind, val = self.msgs.get_nowait()
                if kind == "text":
                    self.text.insert("end", val)
                    self.text.see("end")
                elif kind == "status":
                    self._show_status(val)
                elif kind == "call":
                    self._add_call(val)
        except queue.Empty:
            pass
        if self.live:
            self._draw_spectrum()
        if self.n1mm:
            r = self.n1mm.radio
            if r.connected:
                self.n1mm_status.set(f"N1MM: {r.freq_khz:.1f} kHz {r.mode or ''}  ({r.mycall or ''})")
            else:
                self.n1mm_status.set("N1MM: keine Broadcasts (Port 12060)")
        self.after(60, self._poll)

    def _show_status(self, st):
        lock = "Ton" if st["locked"] else "kein Ton"
        self.status.set(f"{lock}: {st['freq_hz']:.0f} Hz   SNR {st['snr_db']:.0f} dB   "
                        f"{st['wpm']:.0f} WPM   Filter {st['bw_hz']:.0f} Hz   "
                        f"{'■' if st['key'] else '□'}")

    def _draw_spectrum(self):
        tr = self.live.dec.tracker
        spec = tr.spectrum_db
        if spec is None:
            return
        c = self.canvas
        w, h = max(c.winfo_width(), 10), max(c.winfo_height(), 10)
        c.delete("all")
        lo, hi = np.percentile(spec, 5), np.max(spec)
        span = max(hi - lo, 20.0)
        n = len(spec)
        xs = np.linspace(0, w, n)
        pts = []
        for x, v in zip(xs, spec):
            y = h - (v - lo) / span * (h - 10) - 4
            pts += [x, y]
        if len(pts) >= 4:
            c.create_line(*pts, fill="#4fd1c5", width=1)
        fx = (tr.freq - tr.cfg.f_min) / (tr.cfg.f_max - tr.cfg.f_min) * w
        c.create_line(fx, 0, fx, h, fill="#f6ad55" if tr.locked else "#718096", width=2)
        c.create_text(6, 6, anchor="nw", fill="#a0aec0", font=("Segoe UI", 8),
                      text=f"{tr.cfg.f_min:.0f} Hz")
        c.create_text(w - 6, 6, anchor="ne", fill="#a0aec0", font=("Segoe UI", 8),
                      text=f"{tr.cfg.f_max:.0f} Hz")

    def _add_call(self, call):
        if call in self.calls:
            return
        self.calls.insert(0, call)
        self.calls = self.calls[:12]
        for wdg in self.call_frame.winfo_children():
            wdg.destroy()
        for cs in self.calls:
            ttk.Button(self.call_frame, text=cs, command=lambda c=cs: self._send_call(c)
                       ).pack(fill="x", pady=1)

    def _send_call(self, call):
        if not self.n1mm:
            self.n1mm_status.set("N1MM-Anbindung ist aus")
            return
        st = self.live.dec.status if self.live else {"snr_db": 20, "wpm": 25}
        msg = self.n1mm.send_call(call, st["snr_db"], st["wpm"])
        self.n1mm_status.set(msg)


def main():
    App().mainloop()


if __name__ == "__main__":
    main()

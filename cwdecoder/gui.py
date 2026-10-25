# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""Grafische Oberfläche: Spektrum, Live-Text, erkannte Rufzeichen, N1MM.

    python -m cwdecoder.gui            N1MM-Anbindung aus (per Haken einschaltbar)
    python -m cwdecoder.gui --n1mm     N1MM-Anbindung gleich beim Start an
"""
import logging
import os
import queue
import sys
import threading
import time
from datetime import datetime
import tkinter as tk
from tkinter import ttk
import numpy as np

from . import utf8_console
from .decoder import DecoderConfig
from .live import AudioDeviceError, LiveDecoder, open_stream, WavRecorder
from .n1mm import N1MMBridge
from .paths import get_recordings_dir

log = logging.getLogger(__name__)

NO_DEVICE = "(kein Eingangsgerät gefunden)"


class App(tk.Tk):
    def __init__(self, n1mm: bool = False):
        super().__init__()
        self.n1mm_on_start = n1mm
        self.title("CW Decoder")
        self.geometry("900x560")
        self.msgs = queue.Queue()
        self.live = None
        self.stream = None
        self.thread = None
        self.n1mm = None
        self.n1mm_note = None   # (Meldung, sichtbar bis time.monotonic())
        self.calls = []
        self.devs = []
        # Generation des laufenden Decoders; wird bei Start und Stop erhöht.
        # Meldungen tragen ihre Generation, veraltete Status werden verworfen.
        self.gen = 0
        # None = Standard-Aufnahmeordner (Dokumente\CW Decoder\Aufnahmen),
        # wird erst beim ersten Aufnehmen angelegt; Tests setzen einen Temp-Ordner
        self.rec_dir = None
        self.rec_path = None
        self._build()
        self._fill_devices()
        self._poll_id = self.after(60, self._poll)
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
        # standardmäßig aus: Ports werden erst gebunden, wenn der Haken gesetzt wird
        self.n1mm_var = tk.BooleanVar(value=self.n1mm_on_start)
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
        if not self.devs:
            self.dev_box["values"] = []
            self.dev_var.set(NO_DEVICE)
            self.status.set("Kein Audio-Eingangsgerät gefunden – USB-Audio bzw. "
                            "VB-Cable anschließen und Programm neu starten")
            return
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
        if not self.devs or not self.dev_var.get() or self.dev_var.get() == NO_DEVICE:
            self.status.set("Start nicht möglich: kein Audio-Eingangsgerät vorhanden")
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
        except AudioDeviceError as e:
            self.status.set(str(e))
            return
        log.info("Decoder gestartet: %s, %d Hz, Ton %s", self.dev_var.get(), fs,
                 "automatisch" if cfg.tracker.fixed_freq is None
                 else f"fest {cfg.tracker.fixed_freq:.0f} Hz")
        self.gen += 1
        g = self.gen
        self.live = LiveDecoder(fs, cfg,
                                on_text=lambda s: self.msgs.put(("text", g, s)),
                                on_status=lambda d: self.msgs.put(("status", g, d)),
                                on_call=lambda c: self.msgs.put(("call", g, c)))
        self.rec_path = None
        if self.rec_var.get():
            # Zeitstempel mit Millisekunden: schneller Neustart überschreibt nichts
            name = datetime.now().strftime("cw_%Y%m%d_%H%M%S_%f")[:-3] + ".wav"
            try:
                rec_dir = self.rec_dir or str(get_recordings_dir())
                os.makedirs(rec_dir, exist_ok=True)
                self.rec_path = os.path.join(rec_dir, name)
                self.live.recorder = WavRecorder(self.rec_path, fs)
            except OSError as e:
                log.error("Aufnahme nicht möglich: %s", e)
                self.rec_path = None
                self.msgs.put(("text", g, f"[Aufnahme nicht möglich: {e}]\n"))
            else:
                log.info("Aufnahme: %s", self.rec_path)
                self.msgs.put(("text", g, f"[Aufnahme: {self.rec_path}]\n"))
        holder["live"] = self.live
        # gebundene Methode statt lambda: der Thread darf nicht erst beim
        # Anlaufen self.live nachschlagen (kann nach schnellem Stop None sein)
        self.thread = threading.Thread(target=self.live.run, args=(0.25,), daemon=True)
        self.thread.start()
        self.btn_start.configure(text="Stop")

    def _stop(self):
        if self.live:
            log.info("Decoder gestoppt")
        self.gen += 1   # ab jetzt eintreffende Statusmeldungen sind veraltet
        if self.live:
            self.live.stop()
        if self.stream:
            self.stream.stop()
            self.stream.close()
        # Decoder-Thread auslaufen lassen, bevor die WAV-Datei geschlossen
        # wird, sonst schreibt er ggf. noch in die geschlossene Datei
        if self.thread:
            self.thread.join(timeout=2.0)
            self.thread = None
        if self.live and self.live.recorder:
            self.live.recorder.close()
        self.live = None
        self.stream = None
        self.btn_start.configure(text="Start")
        if self.rec_path:
            self.status.set(f"gestoppt – Aufnahme gespeichert: {self.rec_path}")
            self.rec_path = None
        else:
            self.status.set("gestoppt")

    def _quit(self):
        self._stop()
        if self.n1mm:
            self.n1mm.stop()
        # Poll-Timer abmelden, sonst feuert er nach destroy() ins Leere
        self.after_cancel(self._poll_id)
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
                log.info("N1MM-Anbindung ein (Wipe %s)", "an" if self.wipe_var.get() else "aus")
                self.n1mm = N1MMBridge(wipe=self.wipe_var.get())
            else:
                self.n1mm.typer.wipe = self.wipe_var.get()
        else:
            if self.n1mm is not None:
                log.info("N1MM-Anbindung aus")
                self.n1mm.stop()
                self.n1mm = None
            self.n1mm_status.set("N1MM: aus")

    # ------------------------------------------------------------------
    def _poll(self):
        try:
            while True:
                kind, gen, val = self.msgs.get_nowait()
                if kind == "status" and gen != self.gen:
                    continue    # verspätet aus einem bereits gestoppten Lauf
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
                line = f"N1MM: {r.freq_khz:.1f} kHz {r.mode or ''}  ({r.mycall or ''})"
            else:
                line = "N1MM: keine Broadcasts (Port 12060)"
            # Fehler (z. B. Port belegt) bleiben stehen, Meldungen eine Weile
            extra = list(self.n1mm.errors)
            if self.n1mm_note and time.monotonic() < self.n1mm_note[1]:
                extra.append(self.n1mm_note[0])
            self.n1mm_status.set("\n".join([line] + extra))
        self._poll_id = self.after(60, self._poll)

    def _show_status(self, st):
        lock = "Ton" if st["locked"] else "kein Ton"
        self.status.set(f"{lock}: {st['freq_hz']:.0f} Hz   SNR {st['snr_db']:.0f} dB   "
                        f"{st['wpm']:.0f} WPM   Filter {st['bw_hz']:.0f} Hz   "
                        f"{'■' if st['key'] else '□'}"
                        + (f"   ● REC {os.path.basename(self.rec_path)}" if self.rec_path else ""))

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
        self.n1mm_note = (msg, time.monotonic() + 8.0)   # 8 s sichtbar, _poll zeigt sie an


def main():
    utf8_console()
    from .logging_setup import install_exception_hooks, log_startup, setup_logging
    setup_logging()
    install_exception_hooks()
    log_startup("GUI")
    import argparse
    p = argparse.ArgumentParser(description="CW Decoder – Oberfläche")
    p.add_argument("--n1mm", action="store_true",
                   help="N1MM-Anbindung beim Start einschalten (UDP 12060, Telnet 7373)")
    a = p.parse_args()
    App(n1mm=a.n1mm).mainloop()


if __name__ == "__main__":
    main()

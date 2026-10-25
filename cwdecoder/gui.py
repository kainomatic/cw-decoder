# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""Grafische Oberfläche: Spektrum, Live-Text, erkannte Rufzeichen, N1MM.

    python -m cwdecoder.gui            Einstellungen aus config.json
    python -m cwdecoder.gui --n1mm     N1MM-Anbindung für diesen Lauf an

Die Einstellungen (Gerät, feste Tonfrequenz, Haken) werden beim Start aus
<App-Ordner>/config.json gelesen und bei jeder Änderung gespeichert.
Kommandozeilenschalter gelten nur für den laufenden Start.

Threading (ADR-0009): Kein tk-Aufruf aus anderen Threads. Decoder-Thread
und Callbacks legen Meldungen in self.msgs, _poll() holt sie per after() ab.

Alle sichtbaren Texte stehen als _LBL_*, _MSG_*, _TT_* oben im Modul
(Vorbereitung für Übersetzungen).
"""
import logging
import os
import queue
import threading
import time
from datetime import datetime
import tkinter as tk
from tkinter import ttk
import numpy as np

from . import config as config_mod
from . import error_report
from . import utf8_console
from .__version__ import CHANNEL, __version__
from .decoder import DecoderConfig
from .gui_error_report import ErrorReportDialog, open_folder_or_report
from .gui_errors import report_exception
from .gui_tooltip import attach_tooltip
from .live import AudioDeviceError, LiveDecoder, open_stream, WavRecorder
from .n1mm import N1MMBridge, PortInUseError
from .paths import get_log_dir, get_recordings_dir

log = logging.getLogger(__name__)

# -- Beschriftungen --------------------------------------------------------
_LBL_TITLE = "CW Decoder"
_LBL_INPUT = "Eingang:"
_LBL_START = "Start"
_LBL_STOP = "Stop"
_LBL_AUTO = "Ton automatisch suchen"
_LBL_RECORD = "Aufnahme (WAV)"
_LBL_CLEAR = "Text löschen"
_LBL_CALLS = "Rufzeichen (Klick → N1MM)"
_LBL_N1MM = "N1MM-Anbindung"
_LBL_WIPE = "vorher Alt+W (Wipe)"
_LBL_NO_DEVICE = "(kein Eingangsgerät gefunden)"
_LBL_MENU_HELP = "Hilfe"
_LBL_MENU_LOGDIR = "Log-Ordner öffnen"
_LBL_MENU_REPORT = "Fehler melden…"

# -- Meldungen -------------------------------------------------------------
_MSG_READY = "bereit"
_MSG_STOPPED = "gestoppt"
_MSG_STOPPED_REC = "gestoppt – Aufnahme gespeichert: {path}"
_MSG_NO_SOUNDDEVICE = "sounddevice fehlt: {err}  (pip install sounddevice)"
_MSG_NO_INPUT = ("Kein Audio-Eingangsgerät gefunden – USB-Audio bzw. "
                 "VB-Cable anschließen und Programm neu starten")
_MSG_START_NO_INPUT = "Start nicht möglich: kein Audio-Eingangsgerät vorhanden"
_MSG_REC_FAILED = "[Aufnahme nicht möglich: {err}]\n"
_MSG_REC_FILE = "[Aufnahme: {path}]\n"
_MSG_CONFIG_NOT_SAVED = "Einstellungen nicht gespeichert: {err}"
_MSG_STATUS = ("{lock}: {freq:.0f} Hz   SNR {snr:.0f} dB   {wpm:.0f} WPM   "
               "Filter {bw:.0f} Hz   {key}")
_MSG_STATUS_LOCK = "Ton"
_MSG_STATUS_NOLOCK = "kein Ton"
_MSG_STATUS_REC = "   ● REC {name}"
_MSG_N1MM_OFF = "N1MM: aus"
_MSG_N1MM_IDLE = "N1MM: –"
_MSG_N1MM_RADIO = "N1MM: {freq:.1f} kHz {mode}  ({call})"
_MSG_N1MM_NO_BROADCAST = "N1MM: keine Broadcasts (Port 12060)"
_MSG_N1MM_DISABLED = "N1MM-Anbindung ist aus"
_MSG_CONFIG_RESET_DETAIL = "Beiseitegelegt als: {name}\nGrund: {reason}"
_MSG_CTX_GUI = "Fehler in der Oberfläche"
_MSG_CTX_DECODER = "Decoder abgebrochen"
_MSG_CTX_N1MM = "N1MM-Anbindung"
_MSG_DECODER_CRASHED = "Decoder abgebrochen – Details im Fehlerdialog"
_MSG_AUDIO_INFO = "{device}, {rate}"
_MSG_AUDIO_RATE = "{fs} Hz"
_MSG_AUDIO_RATE_LAST = "zuletzt {fs} Hz"
_MSG_AUDIO_NOT_STARTED = "nicht gestartet"

# -- Tooltips --------------------------------------------------------------
_TT_DEVICE = ("Audio-Eingang mit dem Empfängersignal: USB-Audio des Funkgeräts, "
              "VB-Cable oder Line-In. Wird gespeichert.")
_TT_START = "Decoder starten bzw. stoppen."
_TT_AUTO = ("An: Der Decoder sucht den CW-Ton selbst und folgt ihm.\n"
            "Aus: feste Tonfrequenz (per Klick ins Spektrum gesetzt).")
_TT_RECORD = ("Beim nächsten Start das Audio als WAV mitschneiden "
              "(Ordner Dokumente\\CW Decoder\\Aufnahmen). Hilft bei der Fehlersuche.")
_TT_CLEAR = "Dekodierten Text löschen."
_TT_STATUS = ("Ton: erkannte Tonfrequenz · SNR: Signal-Rausch-Abstand · "
              "WPM: Tempo · Filter: aktuelle Bandbreite · ■ Taste gedrückt")
_TT_SPECTRUM = ("Spektrum 300–1200 Hz. Orange Linie = verfolgter Ton.\n"
                "Klick setzt eine feste Tonfrequenz.")
_TT_TEXT = "Dekodierter Text, neueste Zeichen unten."
_TT_CALLS = "Erkannte Rufzeichen, neueste oben."
_TT_CALL_BUTTON = "Rufzeichen an N1MM übergeben (Entry Window, Zwischenablage, Spot)."
_TT_N1MM = ("N1MM Logger+ anbinden: empfängt Frequenz per UDP 12060 und bietet "
            "Spots auf Telnet 127.0.0.1:7373. Belegt die Ports erst beim Einschalten.")
_TT_WIPE = "Vor dem Eintippen Alt+W senden, damit das Entry Window leer ist."
_TT_N1MM_STATUS = "Zustand der N1MM-Anbindung und Ergebnis der letzten Übergabe."

NO_DEVICE = _LBL_NO_DEVICE


class App(tk.Tk):
    def __init__(self, n1mm=None, cfg=None, config_path=None):
        """n1mm: None = Einstellung aus der Config, True/False = nur für
        diesen Lauf überschreiben. config_path None = nichts speichern
        (Tests)."""
        super().__init__()
        self.cfg = config_mod.defaults()
        self.cfg.update(cfg or {})
        self.config_path = config_path
        self.n1mm_on_start = self.cfg["n1mm_enabled"] if n1mm is None else bool(n1mm)
        # feste Tonfrequenz (Spektrum-Klick); None = noch keine gewählt
        self.fixed_freq = self.cfg["fixed_freq"]
        self.title(_LBL_TITLE)
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
        self.shown_errors = []  # angezeigte Fehler (ErrorInfo), für Tests
        self.last_fs = None     # Abtastrate des letzten Laufs (Fehlerbericht)
        self._build_menu()
        self._build()
        self._fill_devices()
        self._poll_id = self.after(60, self._poll)
        self.protocol("WM_DELETE_WINDOW", self._quit)

    # ------------------------------------------------------------------
    def _build_menu(self):
        bar = tk.Menu(self)
        m_help = tk.Menu(bar, tearoff=False)
        m_help.add_command(label=_LBL_MENU_LOGDIR, command=self.open_log_dir)
        m_help.add_command(label=_LBL_MENU_REPORT, command=self.open_error_report)
        bar.add_cascade(label=_LBL_MENU_HELP, menu=m_help)
        self.configure(menu=bar)
        self.menubar = bar

    def _build(self):
        top = ttk.Frame(self, padding=6)
        top.pack(fill="x")
        lbl = ttk.Label(top, text=_LBL_INPUT)
        lbl.pack(side="left")
        attach_tooltip(lbl, _TT_DEVICE)
        self.dev_var = tk.StringVar()
        self.dev_box = ttk.Combobox(top, textvariable=self.dev_var, width=40, state="readonly")
        self.dev_box.pack(side="left", padx=4)
        self.dev_box.bind("<<ComboboxSelected>>", self._device_changed)
        attach_tooltip(self.dev_box, _TT_DEVICE)
        self.btn_start = ttk.Button(top, text=_LBL_START, command=self._toggle)
        self.btn_start.pack(side="left", padx=4)
        attach_tooltip(self.btn_start, _TT_START)
        self.auto_var = tk.BooleanVar(value=self.fixed_freq is None)
        cb = ttk.Checkbutton(top, text=_LBL_AUTO, variable=self.auto_var,
                             command=self._auto_changed)
        cb.pack(side="left", padx=8)
        attach_tooltip(cb, _TT_AUTO)
        self.rec_var = tk.BooleanVar(value=self.cfg["record_default"])
        cb = ttk.Checkbutton(top, text=_LBL_RECORD, variable=self.rec_var,
                             command=self._rec_changed)
        cb.pack(side="left", padx=8)
        attach_tooltip(cb, _TT_RECORD)
        btn = ttk.Button(top, text=_LBL_CLEAR, command=self._clear)
        btn.pack(side="right")
        attach_tooltip(btn, _TT_CLEAR)

        self.status = tk.StringVar(value=_MSG_READY)
        self.status_label = ttk.Label(self, textvariable=self.status, anchor="w",
                                      padding=(8, 0))
        self.status_label.pack(fill="x")
        attach_tooltip(self.status_label, _TT_STATUS)

        self.canvas = tk.Canvas(self, height=110, bg="#101418", highlightthickness=0)
        self.canvas.pack(fill="x", padx=6, pady=(2, 4))
        self.canvas.bind("<Button-1>", self._spectrum_click)
        attach_tooltip(self.canvas, _TT_SPECTRUM)

        mid = ttk.Frame(self)
        mid.pack(fill="both", expand=True, padx=6)
        self.text = tk.Text(mid, wrap="word", font=("Consolas", 16), height=10)
        self.text.pack(side="left", fill="both", expand=True)
        attach_tooltip(self.text, _TT_TEXT)
        sb = ttk.Scrollbar(mid, command=self.text.yview)
        sb.pack(side="left", fill="y")
        self.text.configure(yscrollcommand=sb.set)

        right = ttk.Frame(mid, padding=(8, 0, 0, 0), width=200)
        right.pack(side="left", fill="y")
        lbl = ttk.Label(right, text=_LBL_CALLS)
        lbl.pack(anchor="w")
        attach_tooltip(lbl, _TT_CALLS)
        self.call_frame = ttk.Frame(right)
        self.call_frame.pack(fill="both", expand=True)
        # standardmäßig aus: Ports werden erst gebunden, wenn der Haken gesetzt wird
        self.n1mm_var = tk.BooleanVar(value=self.n1mm_on_start)
        cb = ttk.Checkbutton(right, text=_LBL_N1MM, variable=self.n1mm_var,
                             command=self._n1mm_changed)
        cb.pack(anchor="w", pady=(6, 0))
        attach_tooltip(cb, _TT_N1MM)
        self.wipe_var = tk.BooleanVar(value=self.cfg["n1mm_wipe"])
        cb = ttk.Checkbutton(right, text=_LBL_WIPE, variable=self.wipe_var,
                             command=self._n1mm_changed)
        cb.pack(anchor="w")
        attach_tooltip(cb, _TT_WIPE)
        self.n1mm_status = tk.StringVar(value=_MSG_N1MM_IDLE)
        lbl = ttk.Label(right, textvariable=self.n1mm_status, wraplength=190)
        lbl.pack(anchor="w", pady=4)
        attach_tooltip(lbl, _TT_N1MM_STATUS)
        self._n1mm_changed(save=False)

    def _fill_devices(self):
        try:
            import sounddevice as sd
        except Exception as e:  # noqa: BLE001
            log.error("sounddevice nicht verfügbar: %s", e)
            self.status.set(_MSG_NO_SOUNDDEVICE.format(err=e))
            return
        self.devs = [(i, d["name"]) for i, d in enumerate(sd.query_devices())
                     if d["max_input_channels"] > 0]
        if not self.devs:
            log.warning("Kein Audio-Eingangsgerät gefunden")
            self.dev_box["values"] = []
            self.dev_var.set(NO_DEVICE)
            self.status.set(_MSG_NO_INPUT)
            return
        self.dev_box["values"] = [f"{i}: {n}" for i, n in self.devs]
        wanted = self.cfg["device_name"]
        if wanted:
            for k, (_, name) in enumerate(self.devs):
                if name == wanted:
                    self.dev_box.current(k)
                    return
            log.warning("Gespeichertes Gerät %r nicht vorhanden, nehme Standard", wanted)
        default = sd.default.device[0]
        for k, (i, _) in enumerate(self.devs):
            if i == default:
                self.dev_box.current(k)
                break
        else:
            if self.devs:
                self.dev_box.current(0)

    # -- Einstellungen -------------------------------------------------
    def _save_config(self, **changes):
        """Änderung übernehmen und config.json schreiben (falls vorhanden)."""
        self.cfg.update(changes)
        if self.config_path is None:
            return
        try:
            config_mod.save(self.cfg, self.config_path)
        except OSError as e:
            log.error("Config nicht gespeichert: %s", e)
            self.status.set(_MSG_CONFIG_NOT_SAVED.format(err=e))

    def _device_changed(self, _ev=None):
        k = self.dev_box.current()
        if 0 <= k < len(self.devs):
            self._save_config(device_name=self.devs[k][1])

    def _rec_changed(self):
        self._save_config(record_default=bool(self.rec_var.get()))

    # ------------------------------------------------------------------
    def _toggle(self):
        if self.live:
            self._stop()
        else:
            self._start()

    def _start(self):
        if not self.devs or not self.dev_var.get() or self.dev_var.get() == NO_DEVICE:
            self.status.set(_MSG_START_NO_INPUT)
            return
        idx = int(self.dev_var.get().split(":")[0])
        cfg = DecoderConfig()
        if not self.auto_var.get() and self.fixed_freq:
            cfg.tracker.fixed_freq = self.fixed_freq
        holder = {}

        def cb(indata, frames, t, status):
            if "live" in holder:
                holder["live"].audio_callback(indata, frames, t, status)

        try:
            self.stream, fs = open_stream(idx, cb)
        except AudioDeviceError as e:
            self.status.set(str(e))
            self.report_error(e, f"Start mit {self.dev_var.get()}")
            return
        self.last_fs = fs
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
                self.msgs.put(("text", g, _MSG_REC_FAILED.format(err=e)))
            else:
                log.info("Aufnahme: %s", self.rec_path)
                self.msgs.put(("text", g, _MSG_REC_FILE.format(path=self.rec_path)))
        holder["live"] = self.live
        # gebundene Methode statt lambda: der Thread darf nicht erst beim
        # Anlaufen self.live nachschlagen (kann nach schnellem Stop None sein)
        self.thread = threading.Thread(target=self._run_decoder, args=(self.live, g),
                                       daemon=True, name="decoder")
        self.thread.start()
        self.btn_start.configure(text=_LBL_STOP)

    def _run_decoder(self, live, gen):
        """Läuft im Decoder-Thread: kein tk-Aufruf, Fehler über die Queue."""
        try:
            live.run(0.25)
        except Exception as e:  # noqa: BLE001 - wird in der GUI angezeigt
            self.msgs.put(("error", gen, e))

    def report_error(self, exc, context=None):
        """Ausnahme loggen und als Dialog zeigen (nur im tk-Thread aufrufen)."""
        info = report_exception(self, exc, context)
        self.shown_errors.append(info)
        return info

    # -- Hilfe ---------------------------------------------------------
    def audio_info(self):
        """Gerät und Abtastrate für den Fehlerbericht."""
        if self.live:
            rate = _MSG_AUDIO_RATE.format(fs=self.live.fs)
        elif self.last_fs:
            rate = _MSG_AUDIO_RATE_LAST.format(fs=self.last_fs)
        else:
            rate = _MSG_AUDIO_NOT_STARTED
        return _MSG_AUDIO_INFO.format(device=self.dev_var.get() or "?", rate=rate)

    def open_log_dir(self):
        open_folder_or_report(self, get_log_dir())

    def open_error_report(self):
        from .logging_setup import get_log_path
        log_dir = get_log_dir()
        text = error_report.build_error_report(__version__, CHANNEL, get_log_path(log_dir),
                                               self.audio_info())
        log.info("Fehlerbericht-Dialog geöffnet")
        return ErrorReportDialog(self, text, __version__,
                                 save_dir=get_recordings_dir().parent, log_dir=log_dir)

    def report_callback_exception(self, exc_type, exc, tb):
        """Ausnahmen aus tk-Callbacks: Dialog statt Ausgabe auf stderr."""
        self.report_error(exc.with_traceback(tb), _MSG_CTX_GUI)

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
        self.btn_start.configure(text=_LBL_START)
        if self.rec_path:
            self.status.set(_MSG_STOPPED_REC.format(path=self.rec_path))
            self.rec_path = None
        else:
            self.status.set(_MSG_STOPPED)

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
        self._save_config(fixed_freq=None if self.auto_var.get() else self.fixed_freq)
        if self.live:
            self.live.dec.set_fixed_frequency(None if self.auto_var.get() else self.fixed_freq)

    def _spectrum_click(self, ev):
        if not self.live:
            return
        tr = self.live.dec.tracker
        f = tr.cfg.f_min + (tr.cfg.f_max - tr.cfg.f_min) * ev.x / max(self.canvas.winfo_width(), 1)
        self.fixed_freq = round(float(f), 1)
        self.auto_var.set(False)
        self._save_config(fixed_freq=self.fixed_freq)
        self.live.dec.set_fixed_frequency(self.fixed_freq)

    def _n1mm_changed(self, save=True):
        if save:
            self._save_config(n1mm_enabled=bool(self.n1mm_var.get()),
                              n1mm_wipe=bool(self.wipe_var.get()))
        if self.n1mm_var.get():
            if self.n1mm is None:
                log.info("N1MM-Anbindung ein (Wipe %s)", "an" if self.wipe_var.get() else "aus")
                self.n1mm = N1MMBridge(wipe=self.wipe_var.get())
                for msg in self.n1mm.errors:
                    self.report_error(PortInUseError(msg), _MSG_CTX_N1MM)
            else:
                self.n1mm.typer.wipe = self.wipe_var.get()
        else:
            if self.n1mm is not None:
                log.info("N1MM-Anbindung aus")
                self.n1mm.stop()
                self.n1mm = None
            self.n1mm_status.set(_MSG_N1MM_OFF)

    # ------------------------------------------------------------------
    def _poll(self):
        try:
            while True:
                kind, gen, val = self.msgs.get_nowait()
                if kind == "status" and gen != self.gen:
                    continue    # verspätet aus einem bereits gestoppten Lauf
                if kind == "error":
                    if gen == self.gen and self.live:
                        self._stop()
                        self.status.set(_MSG_DECODER_CRASHED)
                    self.report_error(val, _MSG_CTX_DECODER)
                elif kind == "text":
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
                line = _MSG_N1MM_RADIO.format(freq=r.freq_khz, mode=r.mode or "",
                                              call=r.mycall or "")
            else:
                line = _MSG_N1MM_NO_BROADCAST
            # Fehler (z. B. Port belegt) bleiben stehen, Meldungen eine Weile
            extra = list(self.n1mm.errors)
            if self.n1mm_note and time.monotonic() < self.n1mm_note[1]:
                extra.append(self.n1mm_note[0])
            self.n1mm_status.set("\n".join([line] + extra))
        self._poll_id = self.after(60, self._poll)

    def _show_status(self, st):
        text = _MSG_STATUS.format(
            lock=_MSG_STATUS_LOCK if st["locked"] else _MSG_STATUS_NOLOCK,
            freq=st["freq_hz"], snr=st["snr_db"], wpm=st["wpm"], bw=st["bw_hz"],
            key="■" if st["key"] else "□")
        if self.rec_path:
            text += _MSG_STATUS_REC.format(name=os.path.basename(self.rec_path))
        self.status.set(text)

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

    def show_config_notice(self, broken_name, reason):
        exc = config_mod.ConfigError(
            _MSG_CONFIG_RESET_DETAIL.format(name=broken_name, reason=reason))
        self.report_error(exc)

    def _add_call(self, call):
        if call in self.calls:
            return
        self.calls.insert(0, call)
        self.calls = self.calls[:12]
        for wdg in self.call_frame.winfo_children():
            wdg.destroy()
        for cs in self.calls:
            btn = ttk.Button(self.call_frame, text=cs, command=lambda c=cs: self._send_call(c))
            btn.pack(fill="x", pady=1)
            attach_tooltip(btn, _TT_CALL_BUTTON)

    def _send_call(self, call):
        if not self.n1mm:
            self.n1mm_status.set(_MSG_N1MM_DISABLED)
            return
        st = self.live.dec.status if self.live else {"snr_db": 20, "wpm": 25}
        msg = self.n1mm.send_call(call, st["snr_db"], st["wpm"])
        self.n1mm_note = (msg, time.monotonic() + 8.0)   # 8 s sichtbar, _poll zeigt sie an
        if self.n1mm.last_failure is not None:
            self.report_error(self.n1mm.last_failure, _MSG_CTX_N1MM)


def main():
    utf8_console()
    from .logging_setup import install_exception_hooks, log_startup, setup_logging
    setup_logging()
    install_exception_hooks()
    log_startup("GUI")
    import argparse
    p = argparse.ArgumentParser(description="CW Decoder – Oberfläche")
    p.add_argument("--n1mm", action="store_true", default=None,
                   help="N1MM-Anbindung für diesen Lauf einschalten (UDP 12060, Telnet 7373)")
    a = p.parse_args()
    config_path = config_mod.get_config_path()
    cfg = config_mod.load(config_path)
    app = App(n1mm=a.n1mm, cfg=cfg, config_path=config_path)
    notice = config_mod.pop_broken_notice(config_path)
    if notice:
        app.after(300, lambda: app.show_config_notice(*notice))
    app.mainloop()


if __name__ == "__main__":
    main()

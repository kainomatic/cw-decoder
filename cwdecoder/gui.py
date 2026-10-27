# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""Grafische Oberfläche: Spektrum, Live-Text, erkannte Rufzeichen, N1MM.

    python -m cwdecoder.gui            Einstellungen aus config.json
    python -m cwdecoder.gui --n1mm     N1MM-Anbindung für diesen Lauf an
    python -m cwdecoder.gui --n1mm-engine [--xmlrpc-server-port N] [-ti TITEL]
                                       zusätzlich Engine für N1MMs CW Reader

Die Einstellungen (Gerät, feste Tonfrequenz, Haken) werden beim Start aus
<App-Ordner>/config.json gelesen und bei jeder Änderung gespeichert.
Kommandozeilenschalter gelten nur für den laufenden Start.

Threading (ADR-0009): Kein tk-Aufruf aus anderen Threads. Decoder-Thread
und Callbacks legen Meldungen in self.msgs, _poll() holt sie per after() ab.

Alle sichtbaren Texte stehen als _LBL_*, _MSG_*, _TT_* oben im Modul
(Vorbereitung für Übersetzungen).
"""
import gc
import logging
import os
import queue
import threading
import time
from datetime import datetime
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk
import numpy as np

from . import config as config_mod
from . import error_report
from . import utf8_console
from . import updater
from .__version__ import APP_NAME, CHANNEL, REPO_URL, __version__
from .decoder import DecoderConfig, UNSURE_CONF
from .gui_error_report import ErrorReportDialog, open_folder_or_report
from .gui_errors import report_exception
from .gui_tooltip import attach_tooltip
from .live import (AudioDeviceError, DecodeLog, LiveDecoder, WavRecorder,
                   decode_log_path, open_stream)
from .fldigi_rpc import DEFAULT_TITLE as ENGINE_TITLE
from .n1mm import N1MMBridge
from .paths import data_path, get_log_dir, get_recordings_dir

log = logging.getLogger(__name__)

# -- Beschriftungen --------------------------------------------------------
_LBL_TITLE = "{name} v{version}"
_LBL_TITLE_BETA = " BETA"
_LBL_INPUT = "Eingang:"
_LBL_START = "Start"
_LBL_STOP = "Stop"
_LBL_AUTO = "Ton automatisch suchen"
_LBL_RECORD = "Aufnahme (WAV)"
_LBL_CLEAR = "Text löschen"
_LBL_CALLS = "Rufzeichen (Klick → N1MM)"
_LBL_N1MM = "N1MM-Anbindung"
_LBL_N1MM_WAYS = "Übergabe…"
_LBL_NO_DEVICE = "(kein Eingangsgerät gefunden)"
_LBL_MENU_FILE = "Datei"
_LBL_MENU_RECDIR = "Aufnahmeordner öffnen"
_LBL_MENU_QUIT = "Beenden"
_LBL_MENU_HELP = "Hilfe"
_LBL_MENU_UPDATE = "Nach Updates suchen"
_LBL_MENU_LOGDIR = "Log-Ordner öffnen"
_LBL_MENU_REPORT = "Fehler melden…"
_LBL_MENU_ABOUT = "Über CW Decoder"
_LBL_ABOUT_TITLE = "Über CW Decoder"
_LBL_ABOUT_CLOSE = "Schließen"
_LBL_OK = "OK"

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
_MSG_CALL_COUNTRY = "{name} ({prefix}, {continent}, CQ {cq}, ITU {itu})"
_MSG_N1MM_OFF = "N1MM: aus"
_MSG_N1MM_IDLE = "N1MM: –"
_MSG_N1MM_RADIO = "N1MM: {freq:.1f} kHz {mode}  ({call})"
_MSG_N1MM_NO_BROADCAST = "N1MM: keine Broadcasts (Port 12060)"
_MSG_N1MM_DISABLED = "N1MM-Anbindung ist aus"
_MSG_ENGINE_CONNECTED = "CW Reader: N1MM verbunden, letzter Abruf vor {s:.0f} s"
_MSG_ENGINE_WAITING = "CW Reader: wartet auf N1MM (Port {port})"
_MSG_CONFIG_RESET_DETAIL = "Beiseitegelegt als: {name}\nGrund: {reason}"
_MSG_CTX_GUI = "Fehler in der Oberfläche"
_MSG_CTX_DECODER = "Decoder abgebrochen"
_MSG_CTX_N1MM = "N1MM-Anbindung"
_MSG_DECODER_CRASHED = "Decoder abgebrochen – Details im Fehlerdialog"
_MSG_AUDIO_INFO = "{device}, {rate}"
_MSG_AUDIO_RATE = "{fs} Hz"
_MSG_AUDIO_RATE_LAST = "zuletzt {fs} Hz"
_MSG_AUDIO_NOT_STARTED = "nicht gestartet"
_MSG_UPDATE_TITLE = "Nach Updates suchen"
_MSG_UPDATE_CHECKING = "Suche nach Updates …"
_MSG_UPDATE_CURRENT = "Der CW Decoder v{version} ist aktuell."
_MSG_UPDATE_HINT = "⬆ Update auf v{version} verfügbar"
_MSG_UPDATE_OPTED_OUT = ("Automatische Update-Prüfung beim Start ist aus "
                         "(Hilfe → Nach Updates suchen geht weiterhin).")
_MSG_CTX_UPDATE = "Update-Prüfung"
_MSG_CTX_INSTALL = "Update-Installation"
_MSG_ABOUT = ("Version {version} ({channel})\n\n"
              "Live-Morsedecoder für Audio vom Funkgerät mit Anbindung an "
              "N1MM Logger+.\n\n"
              "Copyright (C) 2026 DF1DS (kainomatic)\n"
              "Lizenz: GNU General Public License v3.0 oder später "
              "(GPL-3.0-or-later). Ohne jede Gewährleistung.")

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
_TT_CALL_BUTTON = ("Rufzeichen an N1MM übergeben (gewählte Wege unter „Übergabe…“: "
                   "Spot, Entry Window, Zwischenablage).")
_TT_CALL_TAG = ("Erkanntes Rufzeichen. Klick übergibt es an N1MM "
                "(wie der Knopf rechts).")
_TT_UNSURE_TAG = "unsicher erkannt"
_TT_CALL_UNSURE = "enthält unsichere Zeichen"
_TT_N1MM = ("N1MM Logger+ anbinden: Engine für N1MMs CW Reader (Port 7367), "
            "Frequenz per UDP 12060, Spots auf Telnet 127.0.0.1:7373. Belegt die "
            "Ports erst beim Einschalten.")
_TT_N1MM_WAYS = ("Wege der Übergabe an N1MM wählen: CW Reader (Engine), Skimmer-Spot, "
                 "Entry Window tippen, Zwischenablage; Port der Engine.")
_TT_N1MM_STATUS = "Zustand der N1MM-Anbindung und Ergebnis der letzten Übergabe."
_TT_REPO_LINK = "Projektseite im Browser öffnen."
_TT_UPDATE_OK = "Dialog schließen."

NO_DEVICE = _LBL_NO_DEVICE
UPDATE_CHECK_DELAY_MS = 1500
MIN_WIDTH, MIN_HEIGHT = 760, 480   # Rufzeichen-Spalte bleibt sichtbar
TEXT_FONT = ("Consolas", 16)
CALL_TAG = "call"                  # Markierung erkannter Rufzeichen im Text
CALL_TAG_PREFIX = "call:"          # zweiter Tag je Vorkommen: call:DL1ABC
CALL_TAG_BG = "#ffe08a"
UNSURE_TAG = "unsure"              # unsicher erkannte Zeichen (ADR-0023)
UNSURE_FG = "#8a8a8a"
CALL_MAX = 12                      # so viele Rufzeichen merkt sich die Spalte
CALL_FIT_DELAY_MS = 80             # Neuberechnung der sichtbaren Knöpfe (entprellt)
CALL_CHARS = 9                     # Breite der Rufzeichen-Spalte im Knopf (Zeichen)
CALL_NAME_CHARS = 14               # Landesname, länger wird mit „…" gekürzt
FLAG_W, FLAG_H = 24, 16            # cwdecoder/data/flags/<iso>.png
CALL_BTN_HOVER = "#e5f1fb"
TOKENS_KEEP = 2000                 # so viele Zeichen merkt sich die Markierung


def window_title(channel=CHANNEL, version=__version__):
    """"CW Decoder v0.1.0", im Beta-Kanal mit " BETA" dahinter."""
    title = _LBL_TITLE.format(name=APP_NAME, version=version)
    return title + (_LBL_TITLE_BETA if channel == "beta" else "")


class App(tk.Tk):
    def __init__(self, n1mm=None, cfg=None, config_path=None, engine_port=None,
                 engine_title=None):
        """n1mm: None = Einstellung aus der Config, True/False = nur für
        diesen Lauf überschreiben. config_path None = nichts speichern
        (Tests). engine_port/engine_title: Start durch N1MMs CW Reader
        (--n1mm-engine); schaltet für diesen Lauf Anbindung und Engine ein."""
        super().__init__()
        self.cfg = config_mod.defaults()
        self.cfg.update(cfg or {})
        self.config_path = config_path
        engine_start = engine_port is not None or engine_title is not None
        if engine_start:
            n1mm = True
        self.n1mm_on_start = self.cfg["n1mm_enabled"] if n1mm is None else bool(n1mm)
        self.engine_on_start = True if engine_start else self.cfg["n1mm_engine"]
        self.rpc_port = int(engine_port or self.cfg["n1mm_rpc_port"])
        self.engine_title = engine_title or ENGINE_TITLE
        self.engine_win = None      # verstecktes Fenster, an dem N1MM die Engine erkennt
        self.n1mm_dialog = None
        # feste Tonfrequenz (Spektrum-Klick); None = noch keine gewählt
        self.fixed_freq = self.cfg["fixed_freq"]
        self.title(window_title())
        self.geometry("900x560")
        # Rufzeichen-Spalte muss immer sichtbar bleiben (auch bei 150 % DPI)
        self.minsize(MIN_WIDTH, MIN_HEIGHT)
        self.msgs = queue.Queue()
        # decodierte Zeichen des laufenden Decoders: Nr. im Zeichenstrom
        # (ohne Leerzeichen) -> (Textindex Anfang, Ende); für die Markierung
        # erkannter Rufzeichen im Text
        self._tokens = {}
        self._tok_n = 0
        self._unsure_tok = set()   # Nr. unsicherer Zeichen im Zeichenstrom
        # Rufzeichen, deren Vorkommen bisher alle unsichere Zeichen enthielten
        self.unsure_calls = set()
        self._sure_calls = set()
        self.live = None
        self.stream = None
        self.thread = None
        self.n1mm = None
        self.n1mm_note = None   # (Meldung, sichtbar bis time.monotonic())
        self.calls = []
        self.call_rows = {}     # Rufzeichen -> Widgets des Knopfs (Tests)
        self._call_row_h = None   # gemessene Höhe eines Knopfs (Pixel, mit Abstand)
        self._call_fit_id = None
        self._shown_calls = 0
        self._flag_cache = {}   # ISO-Code -> PhotoImage; hält die Bilder gegen den GC
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
        # Self-Update (ADR-0013); main() setzt Lock und Mutex, damit sie vor
        # dem Installer-Start freigegeben werden können
        self.instance_lock = None
        self.app_mutex = None
        self.update_checking = False
        self.pending_update = None      # Ergebnis nach "Später" (Hinweis im Menü)
        self.update_dialog = None
        self.check_for_update = updater.check_for_update    # Tests ersetzen das
        self.launch_installer = updater.launch_installer_and_exit
        self._build_menu()
        self._build()
        self._fill_devices()
        self._poll_id = self.after(60, self._poll)
        self.protocol("WM_DELETE_WINDOW", self._quit)

    # ------------------------------------------------------------------
    def _build_menu(self):
        bar = tk.Menu(self)
        m_file = tk.Menu(bar, tearoff=False)
        m_file.add_command(label=_LBL_MENU_RECDIR, command=self.open_recordings_dir)
        m_file.add_separator()
        m_file.add_command(label=_LBL_MENU_QUIT, command=self._quit)
        bar.add_cascade(label=_LBL_MENU_FILE, menu=m_file)
        m_help = tk.Menu(bar, tearoff=False)
        m_help.add_command(label=_LBL_MENU_UPDATE, command=self.check_updates_manual)
        m_help.add_separator()
        m_help.add_command(label=_LBL_MENU_LOGDIR, command=self.open_log_dir)
        m_help.add_command(label=_LBL_MENU_REPORT, command=self.open_error_report)
        m_help.add_separator()
        m_help.add_command(label=_LBL_MENU_ABOUT, command=self.show_about)
        bar.add_cascade(label=_LBL_MENU_HELP, menu=m_help)
        self.configure(menu=bar)
        self.menubar = bar
        self.help_menu = m_help
        self.update_hint = None     # Beschriftung des Hinweis-Eintrags im Hilfe-Menü

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
        # Rechte Spalte und Scrollbalken zuerst packen: pack verteilt den
        # Platz in Pack-Reihenfolge, so kann der Text sie nicht verdrängen
        # (bei 125-150 % DPI wäre ein Text mit 80 Zeichen Wunschbreite
        # breiter als das Fenster, #9)
        right = ttk.Frame(mid, padding=(8, 0, 0, 0), width=200)
        right.pack(side="right", fill="y")
        self.right_col = right
        sb = ttk.Scrollbar(mid)
        sb.pack(side="right", fill="y")
        self.text = tk.Text(mid, wrap="word", font=TEXT_FONT, height=10, width=40)
        self.text.pack(side="left", fill="both", expand=True)
        attach_tooltip(self.text, _TT_TEXT)
        sb.configure(command=self.text.yview)
        self.text.configure(yscrollcommand=sb.set)
        self._setup_call_tag()

        lbl = ttk.Label(right, text=_LBL_CALLS)
        lbl.pack(anchor="w")
        attach_tooltip(lbl, _TT_CALLS)
        # N1MM-Block unten verankern und vor den Knöpfen packen: viele
        # Rufzeichen-Knöpfe verdrängen ihn sonst nach unten aus dem Fenster
        bottom = ttk.Frame(right)
        bottom.pack(side="bottom", fill="x")
        self.call_frame = ttk.Frame(right)
        self._call_bg = ttk.Style(self).lookup("TButton", "background") or self.cget("bg")
        self._bold_font = None
        self.call_frame.pack(fill="both", expand=True)
        # nur so viele Knöpfe, wie hineinpassen (#14); neu bei Größenänderung
        self.call_frame.bind("<Configure>", self._schedule_call_fit, add="+")
        # standardmäßig aus: Ports werden erst gebunden, wenn der Haken gesetzt wird
        self.n1mm_var = tk.BooleanVar(value=self.n1mm_on_start)
        cb = ttk.Checkbutton(bottom, text=_LBL_N1MM, variable=self.n1mm_var,
                             command=self._n1mm_changed)
        cb.pack(anchor="w", pady=(6, 0))
        self.cb_n1mm = cb
        attach_tooltip(cb, _TT_N1MM)
        # Übergabewege (Dialog „Übergabe…“, ADR-0022)
        self.engine_var = tk.BooleanVar(value=self.engine_on_start)
        self.spot_var = tk.BooleanVar(value=self.cfg["n1mm_spot"])
        self.type_var = tk.BooleanVar(value=self.cfg["n1mm_type"])
        self.wipe_var = tk.BooleanVar(value=self.cfg["n1mm_wipe"])
        self.clip_var = tk.BooleanVar(value=self.cfg["n1mm_clipboard"])
        self.btn_n1mm_ways = ttk.Button(bottom, text=_LBL_N1MM_WAYS,
                                        command=self.open_n1mm_settings)
        self.btn_n1mm_ways.pack(anchor="w", pady=(2, 0))
        attach_tooltip(self.btn_n1mm_ways, _TT_N1MM_WAYS)
        self.n1mm_status = tk.StringVar(value=_MSG_N1MM_IDLE)
        lbl = ttk.Label(bottom, textvariable=self.n1mm_status, wraplength=190)
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
        # neuer Decoder = neuer Zeichenstrom des Spotters (Positionen ab 0)
        self._tokens = {}
        self._tok_n = 0
        self._unsure_tok = set()
        self.live = LiveDecoder(fs, cfg,
                                on_text=lambda s: self.msgs.put(("text", g, s)),
                                on_char_conf=lambda ch, c: self.msgs.put(("char", g, (ch, c))),
                                on_status=lambda d: self.msgs.put(("status", g, d)),
                                on_call=lambda c: self.msgs.put(("call", g, c)),
                                on_call_span=lambda c, a, b: self.msgs.put(("span", g, (c, a, b))))
        self.rec_path = None
        if self.rec_var.get():
            # Zeitstempel mit Millisekunden: schneller Neustart überschreibt nichts
            name = datetime.now().strftime("cw_%Y%m%d_%H%M%S_%f")[:-3] + ".wav"
            try:
                rec_dir = self.rec_dir or str(get_recordings_dir())
                os.makedirs(rec_dir, exist_ok=True)
                self.rec_path = os.path.join(rec_dir, name)
                self.live.recorder = WavRecorder(self.rec_path, fs)
                # Decodier-Log neben der Aufnahme: Zeit je Zeichen (#10)
                self.live.decode_log = DecodeLog(decode_log_path(self.rec_path))
            except OSError as e:
                log.error("Aufnahme nicht möglich: %s", e)
                self.rec_path = None
                self.msgs.put(("note", g, _MSG_REC_FAILED.format(err=e)))
            else:
                log.info("Aufnahme: %s", self.rec_path)
                self.msgs.put(("note", g, _MSG_REC_FILE.format(path=self.rec_path)))
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

    def open_recordings_dir(self):
        open_folder_or_report(self, get_recordings_dir())

    # -- Self-Update (ADR-0013) ----------------------------------------
    def schedule_update_check(self):
        """Automatische Prüfung kurz nach dem Start, wenn update_check an ist."""
        if self.cfg.get("update_check", True):
            self.after(UPDATE_CHECK_DELAY_MS, lambda: self.start_update_check(manual=False))
        else:
            log.info("Automatische Update-Prüfung ist abgeschaltet")

    def check_updates_manual(self):
        """Hilfe → Nach Updates suchen (auch bei update_check false)."""
        self.start_update_check(manual=True)

    def start_update_check(self, manual):
        if self.update_checking:
            return
        if self.update_dialog is not None:
            self.update_dialog.top.lift()
            return
        self.update_checking = True
        if manual:
            self.status.set(_MSG_UPDATE_CHECKING)
        check = self.check_for_update

        def run():
            """Läuft im Hintergrund-Thread: kein tk-Aufruf."""
            try:
                result = check(__version__, CHANNEL)
            except Exception as e:  # noqa: BLE001 - check_for_update wirft eigentlich nicht
                result = updater.UpdateCheckResult(updater.UpdateStatus.ERROR,
                                                   error_message=str(e))
            self.msgs.put(("update", 0, (result, manual)))

        threading.Thread(target=run, daemon=True, name="update-check").start()

    def handle_update_result(self, result, manual):
        """Ergebnis der Prüfung im tk-Thread auswerten."""
        self.update_checking = False
        if self.status.get() == _MSG_UPDATE_CHECKING:
            self.status.set(_MSG_READY)
        if result.status is updater.UpdateStatus.UPDATE_AVAILABLE:
            return self.show_update_dialog(result)
        if result.status is updater.UpdateStatus.UP_TO_DATE:
            self.set_update_hint(None)
            if manual:
                return self._info_dialog(_MSG_UPDATE_TITLE,
                                         _MSG_UPDATE_CURRENT.format(version=__version__))
            return None
        # Fehler: beim Auto-Check nur ins Log (schreibt updater), sonst Dialog
        if manual:
            self.report_error(updater.UpdateError(result.error_message), _MSG_CTX_UPDATE)
        return None

    def show_update_dialog(self, result):
        from .gui_update import UpdateDialog
        if self.update_dialog is not None:
            self.update_dialog.top.lift()
            return self.update_dialog

        def later():
            self.update_dialog = None
            self.set_update_hint(result)

        def opt_out():
            later()
            self._save_config(update_check=False)
            log.info("Automatische Update-Prüfung vom Nutzer abgeschaltet")
            self.status.set(_MSG_UPDATE_OPTED_OUT)

        def install(path):
            self.update_dialog = None
            self.install_update(path)

        self.update_dialog = UpdateDialog(self, __version__, result, on_install=install,
                                          on_later=later, on_opt_out=opt_out)
        return self.update_dialog

    def set_update_hint(self, result):
        """Hinweis "Update auf vX.Y.Z verfügbar" oben im Hilfe-Menü (None = weg)."""
        self.pending_update = result
        if self.update_hint is not None:
            self.help_menu.delete(0)
            self.update_hint = None
        if result is not None:
            self.update_hint = _MSG_UPDATE_HINT.format(version=result.new_version)
            self.help_menu.insert_command(0, label=self.update_hint,
                                          command=lambda: self.show_update_dialog(result))

    def install_update(self, installer_path):
        """Vor dem Installer: Audio stoppen, N1MM-Ports schließen, Lock und
        Mutex freigeben; dann Installer starten und beenden."""
        log.info("Update wird installiert, Programm beendet sich")
        self._stop()
        if self.n1mm:
            self.n1mm.stop()
            self.n1mm = None
        self._sync_engine_window()
        if self.instance_lock is not None:
            self.instance_lock.release()
        if self.app_mutex is not None:
            self.app_mutex.close()
        try:
            self.launch_installer(installer_path, self._quit)
        except OSError as e:
            self.report_error(e, _MSG_CTX_INSTALL)

    def _info_dialog(self, title, message):
        dlg = tk.Toplevel(self)
        dlg.title(title)
        dlg.resizable(False, False)
        dlg.transient(self)
        frm = ttk.Frame(dlg, padding=16)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, text=message, wraplength=380, justify="left").pack(anchor="w")
        btn = ttk.Button(frm, text=_LBL_OK, command=dlg.destroy)
        btn.pack(anchor="e", pady=(12, 0))
        attach_tooltip(btn, _TT_UPDATE_OK)
        btn.focus_set()
        dlg.bind("<Return>", lambda _e: dlg.destroy())
        dlg.bind("<Escape>", lambda _e: dlg.destroy())
        return dlg

    def show_about(self):
        import webbrowser
        dlg = tk.Toplevel(self)
        dlg.title(_LBL_ABOUT_TITLE)
        dlg.resizable(False, False)
        dlg.transient(self)
        frm = ttk.Frame(dlg, padding=16)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, text=APP_NAME, font=("Segoe UI", 14, "bold")).pack(anchor="w")
        ttk.Label(frm, text=_MSG_ABOUT.format(version=__version__, channel=CHANNEL),
                  wraplength=380, justify="left").pack(anchor="w", pady=(6, 8))
        link = ttk.Label(frm, text=REPO_URL, foreground="#1a5fb4", cursor="hand2")
        link.pack(anchor="w")
        link.bind("<Button-1>", lambda _e: webbrowser.open(REPO_URL))
        attach_tooltip(link, _TT_REPO_LINK)
        ttk.Button(frm, text=_LBL_ABOUT_CLOSE, command=dlg.destroy).pack(anchor="e",
                                                                        pady=(12, 0))
        dlg.bind("<Escape>", lambda _e: dlg.destroy())
        return dlg

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
        if self.live and self.live.decode_log:
            self.live.decode_log.close()
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
            self.n1mm = None
        # Timer abmelden, sonst feuern sie nach destroy() ins Leere
        self.after_cancel(self._poll_id)
        if self._call_fit_id is not None:
            self.after_cancel(self._call_fit_id)
            self._call_fit_id = None
        self.destroy()

    def _clear(self):
        self.text.delete("1.0", "end")
        self._tokens = {}       # Textindizes gelten nicht mehr
        self._unsure_tok = set()

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

    def _n1mm_ways(self):
        return dict(engine=bool(self.engine_var.get()), spot=bool(self.spot_var.get()),
                    type_call=bool(self.type_var.get()),
                    clipboard=bool(self.clip_var.get()), wipe=bool(self.wipe_var.get()))

    def _n1mm_changed(self, save=True):
        ways = self._n1mm_ways()
        if save:
            self._save_config(n1mm_enabled=bool(self.n1mm_var.get()),
                              n1mm_engine=ways["engine"], n1mm_spot=ways["spot"],
                              n1mm_type=ways["type_call"],
                              n1mm_clipboard=ways["clipboard"], n1mm_wipe=ways["wipe"])
        if self.n1mm_var.get():
            if self.n1mm is None:
                log.info("N1MM-Anbindung ein: %s, Engine-Port %d", ways, self.rpc_port)
                self.n1mm = N1MMBridge(rpc_port=self.rpc_port,
                                       engine_title=self.engine_title, **ways)
                failed = self.n1mm.start_failures
            else:
                log.info("N1MM-Übergabe: %s", ways)
                failed = self.n1mm.configure(**ways)
            for exc in failed:
                self.report_error(exc, _MSG_CTX_N1MM)
        else:
            if self.n1mm is not None:
                log.info("N1MM-Anbindung aus")
                self.n1mm.stop()
                self.n1mm = None
            self.n1mm_status.set(_MSG_N1MM_OFF)
        self._sync_engine_window()

    def set_rpc_port(self, port):
        """Neuer Port der Engine (Dialog); startet eine laufende Engine neu."""
        self.rpc_port = int(port)
        self._save_config(n1mm_rpc_port=self.rpc_port)
        if self.n1mm is not None:
            for exc in self.n1mm.configure(rpc_port=self.rpc_port):
                self.report_error(exc, _MSG_CTX_N1MM)
        self._sync_engine_window()

    def open_n1mm_settings(self):
        if self.n1mm_dialog is not None:
            self.n1mm_dialog.lift()
            return self.n1mm_dialog
        from .gui_n1mm import N1MMSettingsDialog
        self.n1mm_dialog = N1MMSettingsDialog(self)
        return self.n1mm_dialog

    def _sync_engine_window(self):
        """N1MM erkennt die Engine an einem Fenster mit dem Titel aus `-ti`
        (Standard „Fldigi CW Engine 1“). Ein verstecktes Fenster genügt."""
        want = self.n1mm is not None and self.n1mm.engine is not None
        if want and self.engine_win is None:
            win = tk.Toplevel(self)
            win.title(self.engine_title)
            # Kein transient(): ein Fenster mit Besitzer findet N1MM nicht
            # (getestet). Schließen versteckt es nur; _poll versteckt es
            # wieder, wenn N1MM es einblendet, sonst hielte Windows es für
            # das Hauptfenster (taskkill, Taskleiste).
            win.protocol("WM_DELETE_WINDOW", win.withdraw)
            win.withdraw()
            self.engine_win = win
            log.info("Engine-Fenster %r angelegt", self.engine_title)
        elif not want and self.engine_win is not None:
            try:
                self.engine_win.destroy()
            except tk.TclError:
                pass
            self.engine_win = None

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
                    self._insert_decoded(val, gen)
                    if self.n1mm:
                        self.n1mm.feed_text(val)
                elif kind == "char":
                    # Zeichen mit Vertrauen (ADR-0023); N1MM bekommt es unverändert
                    ch, conf = val
                    self._insert_decoded(ch, gen, conf)
                    if self.n1mm:
                        self.n1mm.feed_text(ch)
                elif kind == "note":
                    self.text.insert("end", val)
                    self.text.see("end")
                elif kind == "span":
                    if gen == self.gen:
                        self._mark_call(*val)
                elif kind == "status":
                    self._show_status(val)
                elif kind == "call":
                    self._add_call(val)
                elif kind == "update":
                    self.handle_update_result(*val)
        except queue.Empty:
            pass
        if self.live:
            self._draw_spectrum()
        if self.engine_win is not None and self.engine_win.state() != "withdrawn":
            # N1MM blendet das Fenster seiner Engine ein; bei uns ist es leer
            self.engine_win.withdraw()
        if self.n1mm:
            r = self.n1mm.radio
            if r.connected:
                line = _MSG_N1MM_RADIO.format(freq=r.freq_khz, mode=r.mode or "",
                                              call=r.mycall or "")
            else:
                line = _MSG_N1MM_NO_BROADCAST
            eng = self.n1mm.engine
            if eng is not None:
                if eng.connected:
                    line += "\n" + _MSG_ENGINE_CONNECTED.format(s=eng.seconds_since_call())
                else:
                    line += "\n" + _MSG_ENGINE_WAITING.format(port=eng.port)
            # Fehler (z. B. Port belegt) bleiben stehen, Meldungen eine Weile
            extra = list(self.n1mm.errors)
            if self.n1mm_note and time.monotonic() < self.n1mm_note[1]:
                extra.append(self.n1mm_note[0])
            self.n1mm_status.set("\n".join([line] + extra))
        self._poll_id = self.after(60, self._poll)

    def _show_status(self, st):
        if self.n1mm:
            # Tonfrequenz für modem.get_carrier der Engine
            self.n1mm.carrier_hz = st["freq_hz"] if st["locked"] else None
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

    # -- Rufzeichen im Text (#9) ------------------------------------------
    def _insert_decoded(self, val, gen, conf=None):
        """Decodiertes Stück anhängen und Zeichen für die Markierung merken.

        Der Spotter zählt jedes Zeichen außer Leerzeichen/Absätzen; dieselbe
        Zählung hier ordnet seinen Positionen Textindizes zu. conf < UNSURE_CONF
        = unsicher erkannt: grau (ADR-0023)."""
        start = self.text.index("end-1c")
        unsure = conf is not None and conf < UNSURE_CONF
        self.text.insert("end", val, (UNSURE_TAG,) if unsure else ())
        if gen == self.gen and val.strip():
            self._tokens[self._tok_n] = (start, self.text.index("end-1c"))
            if unsure:
                self._unsure_tok.add(self._tok_n)
            self._tok_n += 1
            self._tokens.pop(self._tok_n - TOKENS_KEEP, None)
            self._unsure_tok.discard(self._tok_n - TOKENS_KEEP)
        self.text.see("end")

    def _mark_call(self, call, a, b):
        """Zeichen a..b-1 des Stroms als Rufzeichen markieren."""
        first, last = self._tokens.get(a), self._tokens.get(b - 1)
        if first is None or last is None:
            return      # schon aus dem Speicher oder Text gelöscht
        self.text.tag_add(CALL_TAG, first[0], last[1])
        self.text.tag_add(CALL_TAG_PREFIX + call, first[0], last[1])
        self._note_call_confidence(call, any(n in self._unsure_tok for n in range(a, b)))

    def _note_call_confidence(self, call, unsure):
        """Rufzeichen gilt als unsicher, solange jedes Vorkommen unsichere
        Zeichen hatte; ein sicheres Vorkommen bestätigt es (ADR-0023)."""
        if unsure and call not in self._sure_calls:
            self.unsure_calls.add(call)
        elif not unsure:
            self._sure_calls.add(call)
            self.unsure_calls.discard(call)
        parts = self.call_rows.get(call)
        if parts is not None:
            # Knopf gibt es schon (on_call kommt vor dem Vorkommen): Tooltip nachziehen
            parts["tooltip"] = tip = self._call_tooltip(_TT_CALL_BUTTON, call)
            for w in parts["widgets"]:
                t = getattr(w, "_cw_tooltip", None)
                if t is not None:
                    t.set_text(tip)

    def _setup_call_tag(self):
        family, size = TEXT_FONT
        self.text.tag_configure(UNSURE_TAG, foreground=UNSURE_FG)
        self.text.tag_configure(CALL_TAG, background=CALL_TAG_BG,
                                font=(family, size, "bold"))
        # Rufzeichen-Markierung liegt über dem Grau (Tag-Priorität)
        self.text.tag_raise(CALL_TAG, UNSURE_TAG)
        self.text.tag_bind(CALL_TAG, "<Button-1>", self._call_clicked)
        self.text.tag_bind(CALL_TAG, "<Enter>", self._call_tag_enter)
        self.text.tag_bind(CALL_TAG, "<Leave>", self._call_tag_leave)
        self.text.tag_bind(UNSURE_TAG, "<Enter>", self._unsure_tag_enter)
        self.text.tag_bind(UNSURE_TAG, "<Leave>", self._call_tag_leave)

    def _unsure_tag_enter(self, ev=None):
        """Tooltip „unsicher erkannt"; auf einem Rufzeichen gilt dessen Tooltip."""
        if ev is not None and self._call_at(ev.x, ev.y):
            return
        tip = getattr(self.text, "_cw_tooltip", None)
        if tip is not None:
            tip.set_text(_TT_UNSURE_TAG)
            tip.schedule()

    def _call_at(self, x, y):
        idx = self.text.index(f"@{x},{y}")
        for name in self.text.tag_names(idx):
            if name.startswith(CALL_TAG_PREFIX):
                return name[len(CALL_TAG_PREFIX):]
        return None

    def _call_clicked(self, ev):
        call = self._call_at(ev.x, ev.y)
        if call:
            log.info("Rufzeichen im Text angeklickt: %s", call)
            self._add_call(call)
            self._send_call(call)
        return "break"

    def _call_tag_enter(self, ev=None):
        self.text.configure(cursor="hand2")
        tip = getattr(self.text, "_cw_tooltip", None)
        if tip is not None:
            call = self._call_at(ev.x, ev.y) if ev is not None else None
            tip.set_text(self._call_tooltip(_TT_CALL_TAG, call))
            tip.schedule()

    def _call_tag_leave(self, _ev=None):
        self.text.configure(cursor="xterm")
        tip = getattr(self.text, "_cw_tooltip", None)
        if tip is not None:
            tip.cancel()
            tip.set_text(_TT_TEXT)

    # -- Rufzeichen-Knöpfe mit Flagge und Landesname (ADR-0021) ----------
    def _country(self, call):
        """DXCC-Entität oder None; Datenfehler kosten nur die Anzeige."""
        if not call:
            return None
        try:
            from . import dxcc
            return dxcc.lookup(call)
        except (OSError, ValueError) as e:
            log.warning("DXCC-Daten nicht lesbar: %s", e)
            return None

    def _call_tooltip(self, base, call):
        """Tooltip-Text plus Zeile „Landesname (Präfix, Kontinent, CQ, ITU)",
        bei unsicher erkannten Rufzeichen dazu „enthält unsichere Zeichen"."""
        text = base
        e = self._country(call)
        if e is not None:
            text += "\n" + _MSG_CALL_COUNTRY.format(
                name=e.short, prefix=e.prefix, continent=e.continent, cq=e.cq, itu=e.itu)
        if call in self.unsure_calls:
            text += "\n" + _TT_CALL_UNSURE
        return text

    def _flag_image(self, iso):
        """PhotoImage der Flagge (gecacht); ohne iso oder Datei ein leeres
        Bild gleicher Größe, damit die Namen untereinander stehen."""
        key = iso or ""
        img = self._flag_cache.get(key)
        if img is not None:
            return img
        if iso:
            try:
                img = tk.PhotoImage(master=self, file=str(data_path("flags", f"{iso}.png")))
            except tk.TclError as e:
                log.warning("Flagge %s nicht lesbar: %s", iso, e)
        if img is None:
            img = self._flag_cache.get("") or tk.PhotoImage(master=self, width=FLAG_W,
                                                            height=FLAG_H)
            self._flag_cache[""] = img
        self._flag_cache[key] = img
        return img

    def _call_font(self):
        if self._bold_font is None:
            self._bold_font = tkfont.nametofont("TkDefaultFont").copy()
            self._bold_font.configure(weight="bold")
        return self._bold_font

    def _add_call(self, call):
        if call in self.calls:
            return
        self.calls.insert(0, call)
        self.calls = self.calls[:CALL_MAX]
        self._render_calls()

    def _calls_fit(self):
        """Wie viele Knöpfe passen in die Spalte (#14)? None = noch unbekannt
        (Spalte nicht gezeichnet oder Knopfhöhe noch nicht gemessen)."""
        avail = self.call_frame.winfo_height()
        if self._call_row_h is None or avail <= 1:
            return None
        return max(0, avail // self._call_row_h)

    def _render_calls(self):
        """Knöpfe neu aufbauen, neueste oben, nur so viele wie sichtbar sind;
        die älteren stehen im Text und sind dort anklickbar (#14)."""
        for wdg in self.call_frame.winfo_children():
            wdg.destroy()
        self.call_rows = {}
        fit = self._calls_fit()
        n = len(self.calls) if fit is None else min(fit, len(self.calls))
        for cs in self.calls[:n]:
            parts = self._make_call_button(cs)
            if self._call_row_h is None:
                parts["row"].update_idletasks()
                self._call_row_h = parts["row"].winfo_reqheight() + 2   # pady=1
                fit = self._calls_fit()
                if fit is not None:
                    n = min(fit, len(self.calls))
                    if n == 0:
                        parts["row"].destroy()
                        self.call_rows = {}
                        break
            if len(self.call_rows) >= n:
                break
        self._shown_calls = len(self.call_rows)
        if fit is None and self.calls:
            self._schedule_call_fit()

    def _schedule_call_fit(self, _ev=None):
        """Nach Größenänderung entprellt neu rechnen (<Configure>)."""
        if self._call_fit_id is not None:
            self.after_cancel(self._call_fit_id)
        self._call_fit_id = self.after(CALL_FIT_DELAY_MS, self._refit_calls)

    def _refit_calls(self):
        self._call_fit_id = None
        fit = self._calls_fit()
        if fit is None:
            return
        if min(fit, len(self.calls)) != self._shown_calls:
            self._render_calls()

    def _make_call_button(self, call):
        """Knopf aus Labels: Rufzeichen links, rechts Flagge und Landesname.
        Feste Breiten in Zeichen, damit die Spalte nicht springt. Klick auf
        jede Stelle übergibt das Rufzeichen (_send_call)."""
        e = self._country(call)
        bg = self._call_bg
        row = tk.Frame(self.call_frame, relief="raised", bd=1, bg=bg, cursor="hand2",
                       takefocus=1)
        row.pack(fill="x", pady=1)
        lbl = tk.Label(row, text=call, font=self._call_font(), anchor="w",
                       width=CALL_CHARS, bg=bg, pady=0)
        lbl.pack(side="left", padx=(4, 2), pady=1)
        parts = {"row": row, "call": lbl, "flag": None, "name": None, "entity": e}
        if e is not None:
            from .dxcc import short_name
            parts["flag"] = tk.Label(row, image=self._flag_image(e.iso), bg=bg, pady=0)
            parts["flag"].pack(side="left", padx=(2, 4))
            parts["name"] = tk.Label(row, text=short_name(e, CALL_NAME_CHARS), anchor="w",
                                     width=CALL_NAME_CHARS, bg=bg, pady=0)
            parts["name"].pack(side="left", padx=(0, 4))
        widgets = [w for w in (row, lbl, parts["flag"], parts["name"]) if w is not None]
        parts["widgets"] = widgets
        parts["tooltip"] = tip = self._call_tooltip(_TT_CALL_BUTTON, call)

        def paint(color):
            for w in widgets:
                try:
                    w.configure(bg=color)
                except tk.TclError:     # Knopf schon abgebaut
                    pass

        def inside():
            try:
                w = self.winfo_containing(*self.winfo_pointerxy())
            except (tk.TclError, KeyError):
                return False
            return w is not None and str(w).startswith(str(row))

        def release(_ev=None):
            row.configure(relief="raised")
            if inside():
                self._send_call(call)

        for w in widgets:
            w.bind("<Enter>", lambda _e: paint(CALL_BTN_HOVER), add="+")
            w.bind("<Leave>", lambda _e: self.after_idle(
                lambda: None if inside() else paint(bg)), add="+")
            w.bind("<ButtonPress-1>", lambda _e: row.configure(relief="sunken"), add="+")
            w.bind("<ButtonRelease-1>", release, add="+")
            attach_tooltip(w, tip)
        row.bind("<Return>", lambda _e: self._send_call(call))
        row.bind("<space>", lambda _e: self._send_call(call))
        self.call_rows[call] = parts
        return parts

    def _send_call(self, call):
        if not self.n1mm:
            self.n1mm_status.set(_MSG_N1MM_DISABLED)
            return
        st = self.live.dec.status if self.live else {"snr_db": 20, "wpm": 25}
        msg = self.n1mm.send_call(call, st["snr_db"], st["wpm"])
        self.n1mm_note = (msg, time.monotonic() + 8.0)   # 8 s sichtbar, _poll zeigt sie an
        if self.n1mm.last_failure is not None:
            self.report_error(self.n1mm.last_failure, _MSG_CTX_N1MM)


def _preload_dxcc():
    try:
        from . import dxcc
        dxcc.load()
    except Exception as e:  # noqa: BLE001 - Anzeige fällt dann nur weg
        log.warning("DXCC-Daten nicht geladen: %s", e)


def run_app(n1mm=None, lock=None, splash=None, timer=None, engine_port=None,
            engine_title=None):
    """Hauptfenster bauen und laufen lassen (Aufruf aus gui_start.main,
    nachdem der Lock erworben ist und das Startfenster steht)."""
    from .app_mutex import create_app_mutex
    from .gui_start import close_splash
    # Für den Installer (AppMutex); Handle bis Prozessende halten
    mutex = create_app_mutex()
    # cty.dat vorab laden (reines Python, kein tk), damit das erste
    # Rufzeichen nicht wartet (ADR-0021)
    threading.Thread(target=_preload_dxcc, daemon=True, name="dxcc-load").start()
    # Setup-Dateien früherer Updates aus %TEMP% entfernen (ohne tk, im Hintergrund)
    threading.Thread(target=updater.cleanup_old_installers, daemon=True,
                     name="update-cleanup").start()
    config_path = config_mod.get_config_path()
    cfg = config_mod.load(config_path)
    # Das Startfenster ist ein eigenes Tk; vor dem Hauptfenster schließen,
    # damit tk-Variablen ohne master am Hauptfenster hängen
    close_splash(splash)
    app = App(n1mm=n1mm, cfg=cfg, config_path=config_path, engine_port=engine_port,
              engine_title=engine_title)
    app.instance_lock = lock
    app.app_mutex = mutex
    notice = config_mod.pop_broken_notice(config_path)
    if notice:
        app.after(300, lambda: app.show_config_notice(*notice))
    app.schedule_update_check()
    if timer is not None:
        app.update()
        timer.phase("Fenster sichtbar")
    app.mainloop()
    # Tk-Objekte im Hauptthread abräumen, bevor ein noch laufender
    # Hintergrund-Thread die Garbage Collection auslöst (Tcl verträgt
    # das Löschen aus fremden Threads nicht)
    del app
    gc.collect()


def main(argv=None):
    """`python -m cwdecoder.gui`: wie die EXE über gui_start (Lock, Startfenster)."""
    from .gui_start import main as start_main
    start_main(argv)


if __name__ == "__main__":
    main()

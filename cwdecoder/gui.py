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
import math
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
from .replay import Player, ReplayHold
from .ringbuffer import save_clip, save_excerpt
from .segment import SEP as SEGMENT_SEP, WordBuffer

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
_LBL_SAVE_LAST = "Letzte {s} s speichern"
_LBL_REPLAY = "Nochmal hören"
_LBL_REPLAY_HELD = "Nochmal (festgehalten)"
_LBL_REPLAY_STOP = "Stopp"
_LBL_RATE = "Tempo"
_LBL_RATE_VALUE = "{rate:.2f}×"
_LBL_CALL_REMOVE = "Entfernen"
_LBL_CALL_REMOVE_X = "×"
_LBL_CALLS_CLEAR = "Alle löschen"
_LBL_MENU_SETTINGS = "Einstellungen"
_LBL_MENU_RING = "Puffer und Nochmal hören…"
_LBL_MENU_SEGMENT = "Zusammengeklebte Wörter trennen (·)"
_LBL_MENU_ENGINE_SEG = "An N1MMs CW Reader getrennt mit Leerzeichen"
_LBL_CALL_ADOPT = "{call} übernehmen"
_LBL_CALLS = "Rufzeichen (Klick → N1MM)"
_LBL_N1MM = "N1MM-Anbindung"
_LBL_N1MM_WAYS = "Übergabe…"
_LBL_NO_DEVICE = "(kein Eingangsgerät gefunden)"
_LBL_MENU_FILE = "Datei"
_LBL_MENU_RECDIR = "Aufnahmeordner öffnen"
_LBL_MENU_QUIT = "Beenden"
_LBL_MENU_HELP = "Hilfe"
_LBL_MENU_MANUAL = "Handbuch"
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
_MSG_SAVED = "Gespeichert: {name} ({secs:.0f} s)"
_MSG_SAVE_NOT_RUNNING = "Speichern geht nur, während der Decoder läuft"
_MSG_REPLAY_RUNNING = "▶ Wiedergabe {secs:.0f} s …"
_MSG_REPLAY_RATE = " ({rate:.2f}×)"
_MSG_REPLAY_HELD = "festgehalten {secs:.0f} s – noch {left:.0f} s"
_MSG_SAVED_HELD = "Festgehalten gespeichert: {name} ({secs:.0f} s)"
_MSG_REPLAY_DONE = "Wiedergabe beendet"
_MSG_REPLAY_STOPPED = "Wiedergabe abgebrochen"
_MSG_REPLAY_EMPTY = "Noch nichts zum Abspielen im Puffer"
_MSG_CTX_SAVE = "Letzte Sekunden speichern"
_MSG_CTX_REPLAY = "Nochmal hören"
_MSG_CALL_COUNTRY = "{name} ({prefix}, {continent}, CQ {cq}, ITU {itu})"
_MSG_N1MM_OFF = "N1MM: aus"
_MSG_ENGINE_FORCED = "Engine für N1MMs CW Reader eingeschaltet (nur dieser Lauf)"
_MSG_N1MM_IDLE = "N1MM: –"
_MSG_N1MM_RADIO = "N1MM: {freq:.1f} kHz {mode}  ({call})"
_MSG_N1MM_NO_BROADCAST = "N1MM: keine Broadcasts (Port 12060)"
_MSG_N1MM_DISABLED = "N1MM-Anbindung ist aus"
_MSG_ENGINE_CONNECTED = "CW Reader: N1MM verbunden, letzter Abruf vor {s:.0f} s"
_MSG_ENGINE_WAITING = "CW Reader: wartet auf N1MM (Port {port})"
_MSG_CONFIG_RESET_DETAIL = "Beiseitegelegt als: {name}\nGrund: {reason}"
_MSG_CTX_GUI = "Fehler in der Oberfläche"
_MSG_CTX_MANUAL = "Handbuch öffnen"
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
_TT_SAVE_LAST = ("Die letzten Sekunden Audio als WAV in Dokumente\\CW Decoder\\Aufnahmen "
                 "sichern, dazu der decodierte Text als .txt (Strg+S). Ohne "
                 "Daueraufnahme: z. B. eine Fehldecodierung als Testdatei festhalten.")
_TT_REPLAY = ("Die letzten Sekunden nochmal abspielen (Strg+R); der Decoder läuft "
              "weiter. Der Ausschnitt bleibt festgehalten: Strg+R innerhalb der "
              "Frist nach dem Ende (Standard 5 s) spielt denselben noch einmal, "
              "Strg+S speichert ihn. Danach verfällt er, das nächste Strg+R fasst neu. "
              "Während der Wiedergabe: Stopp.")
_TT_RATE = ("Tempo der Wiedergabe, 0,5× bis 1,0×, ohne Änderung der Tonhöhe. Wirkt "
            "sofort, auch mitten im Abspielen; mit neuem Ausschnitt springt der "
            "Regler auf den Wert aus den Einstellungen zurück.")
_TT_CALL_REMOVE = ("Rufzeichen aus der Liste entfernen (Markierung im Text bleibt; "
                   "wird es wieder gehört, erscheint es wieder).")
_TT_CALLS_CLEAR = "Alle Rufzeichen aus der Liste entfernen; der Text bleibt."
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
_TT_CALL_SCP = "in Super Check Partial"
_TT_CALL_NOT_SCP = "nicht in SCP"
_TT_CALL_NEAR = "ähnlich: {calls}"
_TT_CALL_ADOPT = "Rechtsklick: {call} übernehmen"
_TT_INFERRED = ("· = vom Wörterbuch getrennt, kein Wortabstand gehört "
                "(Einstellungen → Zusammengeklebte Wörter trennen)")
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
ENGINE_WIN_REOPEN_MS = 1500        # Engine-Fenster nach WM_CLOSE neu anlegen (#13)
MIN_WIDTH, MIN_HEIGHT = 760, 480   # Rufzeichen-Spalte bleibt sichtbar
TEXT_FONT = ("Consolas", 16)
CALL_TAG = "call"                  # Markierung erkannter Rufzeichen im Text
CALL_TAG_PREFIX = "call:"          # zweiter Tag je Vorkommen: call:DL1ABC
CALL_TAG_BG = "#ffe08a"            # Rufzeichen, nicht in SCP (gelb)
CALL_SCP_TAG = "call_scp"          # Rufzeichen in Super Check Partial (ADR-0026)
CALL_SCP_BG = "#b9e8b0"            # grün
INFERRED_TAG = "inferred"          # Trenner · der Wörterbuch-Zerlegung
INFERRED_FG = "#9a9a9a"
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
        (--n1mm-engine); schaltet die Engine nur für diesen Lauf ein, wie
        eine Anforderung der zweiten Instanz (request_engine, ADR-0030)."""
        super().__init__()
        self.cfg = config_mod.defaults()
        self.cfg.update(cfg or {})
        self.config_path = config_path
        engine_start = engine_port is not None or engine_title is not None
        self.n1mm_on_start = self.cfg["n1mm_enabled"] if n1mm is None else bool(n1mm)
        self.engine_on_start = self.cfg["n1mm_engine"]
        # Engine nur für diesen Lauf (N1MM hat uns gerufen); Haken und
        # Config bleiben, wie sie sind (#30, ADR-0030)
        self.engine_forced = engine_start
        self.rpc_port = int(engine_port or self.cfg["n1mm_rpc_port"])
        self.engine_title = engine_title or ENGINE_TITLE
        # Anforderungsdatei der zweiten Instanz (run_app setzt sie neben den Lock)
        self.engine_request_file = None
        self._request_next = 0.0
        self._n1mm_last = None      # Stand der Haken beim letzten _n1mm_changed
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
        # Ringpuffer (ADR-0024): Speichern im Hintergrund, Wiedergabe
        self.player = Player()
        self.replay_secs = None     # laufende Wiedergabe (Sekunden) oder None
        # Festhalten mit Verfall (#25); das Tempo liest der Wiedergabe-Thread
        # als bloße Zahl (kein tk im Thread, ADR-0009)
        self.hold = ReplayHold(self.cfg["replay_hold_s"])
        self.replay_rate_now = float(self.cfg["replay_rate"])
        self._hold_shown = None     # zuletzt angezeigte Restsekunden
        self._fallback_reported = False  # Dialog „Ausgabegerät fehlt“ schon gezeigt
        self._removed_calls = set()  # aus der Liste entfernt; kommen beim Hören wieder
        self.status_note = None     # (Meldung, sichtbar bis time.monotonic())
        self.saved_paths = []       # gespeicherte Ausschnitte (Tests)
        self.ring_dialog = None
        self._last_st = None
        # Super Check Partial (ADR-0026): Ähnliche je Rufzeichen (gecacht)
        self._near_cache = {}
        # N1MM-Engine: Wort erst am Ende, mit echten Leerzeichen an den
        # Zerlegestellen (n1mm_engine_segmented)
        self._engine_words = WordBuffer(self._engine_emit, " ")
        self._build_menu()
        self._build()
        self._fill_devices()
        if self.engine_forced and self.n1mm is not None and self.n1mm.engine is not None:
            self._note(_MSG_ENGINE_FORCED)
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
        m_set = tk.Menu(bar, tearoff=False)
        m_set.add_command(label=_LBL_MENU_RING, command=self.open_ring_settings)
        m_set.add_separator()
        self.segment_var = tk.BooleanVar(value=self.cfg["segment_words"])
        self.engine_seg_var = tk.BooleanVar(value=self.cfg["n1mm_engine_segmented"])
        m_set.add_checkbutton(label=_LBL_MENU_SEGMENT, variable=self.segment_var,
                              command=self._segment_changed)
        m_set.add_checkbutton(label=_LBL_MENU_ENGINE_SEG, variable=self.engine_seg_var,
                              command=self._segment_changed)
        bar.add_cascade(label=_LBL_MENU_SETTINGS, menu=m_set)
        self.settings_menu = m_set
        m_help = tk.Menu(bar, tearoff=False)
        m_help.add_command(label=_LBL_MENU_MANUAL, command=self.open_manual)
        m_help.add_separator()
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
        # zweite Zeile: in der ersten ist bei 760-900 px kein Platz mehr
        top2 = ttk.Frame(self, padding=(6, 0, 6, 4))
        top2.pack(fill="x")
        btn = ttk.Button(top2, text=_LBL_CLEAR, command=self._clear)
        btn.pack(side="right")
        attach_tooltip(btn, _TT_CLEAR)
        # Ringpuffer (ADR-0024): aktiv, solange der Decoder läuft
        self.btn_save = ttk.Button(top2, text=self._save_label(), command=self.save_last,
                                   state="disabled")
        self.btn_save.pack(side="left", padx=(0, 4))
        attach_tooltip(self.btn_save, _TT_SAVE_LAST)
        # feste Breite: der Knopf springt nicht, wenn er „Stopp“ zeigt
        self.btn_replay = ttk.Button(top2, text=_LBL_REPLAY, command=self.toggle_replay,
                                     width=22, state="disabled")
        self.btn_replay.pack(side="left", padx=2)
        attach_tooltip(self.btn_replay, _TT_REPLAY)
        # Tempo-Regler (#25): wirkt sofort, auch während der Wiedergabe
        lbl = ttk.Label(top2, text=_LBL_RATE)
        lbl.pack(side="left", padx=(8, 2))
        attach_tooltip(lbl, _TT_RATE)
        self.rate_var = tk.DoubleVar(value=self.replay_rate_now)
        self.rate_scale = ttk.Scale(top2, from_=0.5, to=1.0, length="68p",   # wächst mit der Skalierung
                                    variable=self.rate_var, command=self._rate_moved)
        self.rate_scale.pack(side="left")
        attach_tooltip(self.rate_scale, _TT_RATE)
        self.rate_label = ttk.Label(top2, width=5,
                                    text=_LBL_RATE_VALUE.format(rate=self.replay_rate_now))
        self.rate_label.pack(side="left", padx=(2, 0))
        attach_tooltip(self.rate_label, _TT_RATE)
        for seq in ("<Control-s>", "<Control-S>"):
            self.bind(seq, lambda _e: self.save_last() or "break")
        for seq in ("<Control-r>", "<Control-R>"):
            self.bind(seq, lambda _e: self.toggle_replay() or "break")

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
        # „Alle löschen“ am Ende der Rufzeichen-Spalte (#25)
        self.btn_calls_clear = ttk.Button(bottom, text=_LBL_CALLS_CLEAR,
                                          command=self.clear_calls)
        self.btn_calls_clear.pack(anchor="e", pady=(2, 0))
        attach_tooltip(self.btn_calls_clear, _TT_CALLS_CLEAR)
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
        self._engine_words.end()
        self.live = LiveDecoder(fs, cfg,
                                on_text=lambda s: self.msgs.put(("text", g, s)),
                                on_char_conf=lambda ch, c: self.msgs.put(("char", g, (ch, c))),
                                on_status=lambda d: self.msgs.put(("status", g, d)),
                                on_call=lambda c: self.msgs.put(("call", g, c)),
                                on_call_replace=lambda o, n: self.msgs.put(("replace", g, (o, n))),
                                on_call_span=lambda c, a, b: self.msgs.put(("span", g, (c, a, b))),
                                on_segment=lambda cuts: self.msgs.put(("seg", g, cuts)),
                                segment=bool(self.segment_var.get()),
                                ring_seconds=self.cfg["ring_seconds"])
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
        self._update_ring_buttons()

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

    def open_manual(self):
        """Hilfe → Handbuch: mitgeliefertes PDF, sonst das des Releases (#24)."""
        from .manual import open_manual
        try:
            log.info("Handbuch geöffnet: %s", open_manual())
        except OSError as e:
            self.report_error(e, _MSG_CTX_MANUAL)

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
        self._last_st = None
        self._engine_words.end()
        self.btn_start.configure(text=_LBL_START)
        self._update_ring_buttons()
        if self.rec_path:
            self.status.set(_MSG_STOPPED_REC.format(path=self.rec_path))
            self.rec_path = None
        else:
            self.status.set(_MSG_STOPPED)

    def _quit(self):
        self._stop()
        self.player.stop()
        self.player.join(timeout=1.0)
        if self.n1mm:
            self.n1mm.stop()
            self.n1mm = None
        # Timer abmelden, sonst feuern sie nach destroy() ins Leere
        self.after_cancel(self._poll_id)
        if self._call_fit_id is not None:
            self.after_cancel(self._call_fit_id)
            self._call_fit_id = None
        self.destroy()

    # -- Ringpuffer: speichern und nochmal hören (ADR-0024) ---------------
    def _save_label(self):
        return _LBL_SAVE_LAST.format(s=self.cfg["save_last_s"])

    def _update_ring_buttons(self):
        """Speichern bei laufendem Decoder oder festgehaltenem Ausschnitt; der
        Wiedergabe-Knopf bleibt als „Stopp“ aktiv, solange etwas spielt."""
        held = self.hold.active()
        self.btn_save.configure(text=self._save_label(),
                                state="normal" if (self.live or held) else "disabled")
        playing = self.replay_secs is not None
        text = _LBL_REPLAY_STOP if playing else (_LBL_REPLAY_HELD if held else _LBL_REPLAY)
        self.btn_replay.configure(text=text,
                                  state="normal" if (self.live or playing or held)
                                  else "disabled")

    def _note(self, text, seconds=8.0):
        """Meldung in der Statuszeile; bei laufendem Decoder hinter dem Status."""
        self.status_note = (text, time.monotonic() + seconds)
        self._refresh_status()

    def _refresh_status(self):
        if self.live and self._last_st is not None:
            self._show_status(self._last_st)
            return
        parts = []
        if self.replay_secs is not None or self.hold.active():
            parts.append(self._replay_text())
        if self.status_note and time.monotonic() < self.status_note[1]:
            parts.append(self.status_note[0])
        if parts:
            self.status.set("   ".join(parts))

    def _replay_text(self):
        """„▶ Wiedergabe 10 s … (0,70×)“ bzw. „festgehalten 10 s – noch 4 s“."""
        if self.replay_secs is not None:
            text = _MSG_REPLAY_RUNNING.format(secs=self.replay_secs)
            if self.replay_rate_now < 0.995:
                text += _MSG_REPLAY_RATE.format(rate=self.replay_rate_now)
            return text
        if self.hold.active():
            return _MSG_REPLAY_HELD.format(secs=self.hold.clip.seconds,
                                           left=math.ceil(self.hold.remaining()))
        return ""

    def _tick_hold(self):
        """Aus _poll: Countdown des Festhaltens und Verfall."""
        if self.hold.expire_if_due():
            log.info("Festgehaltener Ausschnitt verfallen")
            self._hold_shown = None
            self._reset_rate()
            self._update_ring_buttons()
            if self.live:
                self._refresh_status()
            else:
                self.status.set(_MSG_READY)
            return
        if self.hold.active() and self.replay_secs is None:
            left = math.ceil(self.hold.remaining())
            if left != self._hold_shown:
                self._hold_shown = left
                self._refresh_status()

    def save_last(self):
        """„Letzte … s speichern“ (Strg+S): Schreiben im Hintergrund-Thread,
        Ergebnis über self.msgs. Ist ein Ausschnitt festgehalten, wird genau
        dieser gespeichert (`…_festgehalten.wav`, #25)."""
        rec_dir = self.rec_dir or str(get_recordings_dir())
        clip = self.hold.clip if self.hold.active() else None
        live = self.live
        if clip is None and (live is None or live.ring is None):
            self.status.set(_MSG_SAVE_NOT_RUNNING)
            return
        secs = min(self.cfg["save_last_s"], self.cfg["ring_seconds"])

        def run():
            """Hintergrund-Thread: kein tk."""
            try:
                if clip is not None:
                    result = save_clip(rec_dir, clip) + (True,)
                else:
                    result = save_excerpt(rec_dir, live.ring, live.token_ring, secs) + (False,)
            except Exception as e:  # noqa: BLE001 - SaveLastError u. a., Dialog in der GUI
                self.msgs.put(("save_error", 0, e))
            else:
                self.msgs.put(("saved", 0, result))

        threading.Thread(target=run, daemon=True, name="save-last").start()

    def _saved(self, path, secs, held=False):
        log.info("Ausschnitt gespeichert: %s (%.1f s)", path, secs)
        self.saved_paths.append(path)
        msg = _MSG_SAVED_HELD if held else _MSG_SAVED
        self._note(msg.format(name=os.path.basename(path), secs=secs))

    def toggle_replay(self):
        """„Nochmal hören“ (Strg+R) bzw. „Stopp“ während der Wiedergabe.

        Fasst die letzten replay_s Sekunden und hält sie fest; innerhalb der
        Frist nach dem Ende spielt Strg+R denselben Ausschnitt erneut (#25)."""
        if self.replay_secs is not None:
            log.info("Wiedergabe vom Nutzer abgebrochen")
            self.player.stop()
            return
        live = self.live
        if not self.hold.active() and (live is None or live.ring is None):
            return
        clip, fresh = self.hold.grab(live.ring if live else None, self.cfg["replay_s"],
                                     live.token_ring if live else None)
        if clip is None:
            self._note(_MSG_REPLAY_EMPTY)
            return
        if fresh:
            self._reset_rate()
        if not self.player.start(clip.samples, clip.fs, rate=lambda: self.replay_rate_now,
                                 device=self.cfg["output_device"],
                                 on_done=lambda err: self.msgs.put(("replay_done", 0, err))):
            return
        self.hold.started()
        self.replay_secs = clip.seconds
        log.info("Wiedergabe %.1f s (%s), Tempo %.2f", self.replay_secs,
                 "neu gefasst" if fresh else "festgehalten", self.replay_rate_now)
        self._update_ring_buttons()
        self._refresh_status()

    def _replay_done(self, err):
        stopped = self.player.stop_requested
        self.replay_secs = None
        self.hold.finished()        # Frist läuft ab jetzt
        self._hold_shown = None
        self._update_ring_buttons()
        if self.player.fallback is not None:
            # gewähltes Ausgabegerät fehlt: Standard benutzt. Dialog einmal je
            # Sitzung, danach nur die Statuszeile
            if not self._fallback_reported:
                self._fallback_reported = True
                info = self.report_error(self.player.fallback, _MSG_CTX_REPLAY)
            else:
                from .gui_errors import classify_error
                info = classify_error(self.player.fallback)
                log.warning("Ausgabegerät fehlt weiter: %s", self.player.fallback)
            self._note(info.status)
        if err is not None:
            info = self.report_error(err, _MSG_CTX_REPLAY)
            self._note(info.status)
        elif self.player.fallback is None:
            self._note(_MSG_REPLAY_STOPPED if stopped else _MSG_REPLAY_DONE, 4.0)

    def _rate_moved(self, _value=None):
        """Regler: gilt sofort, nur für den laufenden Ausschnitt; der Wert
        in den Einstellungen bleibt."""
        r = round(float(self.rate_var.get()) * 20) / 20       # 0,05er-Schritte
        self.replay_rate_now = r
        self.rate_label.configure(text=_LBL_RATE_VALUE.format(rate=r))
        if self.replay_secs is not None:
            self._refresh_status()

    def set_replay_rate(self, rate):
        """Regler setzen (Tests, Rücksprung)."""
        self.rate_var.set(float(rate))
        self._rate_moved()

    def _reset_rate(self):
        self.set_replay_rate(self.cfg["replay_rate"])

    def set_ring_settings(self, **changes):
        """Werte aus dem Dialog übernehmen; Puffergröße gilt ab dem nächsten Start."""
        if "output_device" in changes:
            self._fallback_reported = False     # neues Gerät: Fehlen wieder melden
        cfg = dict(self.cfg, **changes)
        if cfg["save_last_s"] > cfg["ring_seconds"]:
            changes["save_last_s"] = cfg["ring_seconds"]
        log.info("Ringpuffer-Einstellungen: %s", changes)
        self._save_config(**changes)
        if "replay_hold_s" in changes:
            self.hold.hold_s = float(changes["replay_hold_s"])
        if "replay_rate" in changes and not self.hold.active():
            self._reset_rate()
        self._update_ring_buttons()

    def open_ring_settings(self):
        if self.ring_dialog is not None:
            self.ring_dialog.lift()
            return self.ring_dialog
        from .gui_ring import RingSettingsDialog
        self.ring_dialog = RingSettingsDialog(self)
        return self.ring_dialog

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

    def _n1mm_settings(self):
        """Stand der Haken als Config-Schlüssel (das, was gespeichert wird)."""
        ways = self._n1mm_ways()
        return {"n1mm_enabled": bool(self.n1mm_var.get()), "n1mm_engine": ways["engine"],
                "n1mm_spot": ways["spot"], "n1mm_type": ways["type_call"],
                "n1mm_clipboard": ways["clipboard"], "n1mm_wipe": ways["wipe"]}

    def _effective_ways(self):
        """Wege, die wirklich laufen: die Haken, dazu die Engine, wenn N1MM
        sie für diesen Lauf verlangt hat. Ist die Anbindung aus, läuft dann
        nur die Engine (#30)."""
        ways = self._n1mm_ways()
        if self.engine_forced:
            if not self.n1mm_var.get():
                ways = dict.fromkeys(ways, False)
            ways["engine"] = True
        return ways

    def _n1mm_changed(self, save=True):
        """Haken geändert (oder Start). Gespeichert wird nur, was der Nutzer
        seit dem letzten Aufruf wirklich umgeschaltet hat; Werte nur für
        diesen Lauf (--n1mm, Engine für N1MM) landen so nie in config.json."""
        now = self._n1mm_settings()
        last = self._n1mm_last or now
        changed = {k: v for k, v in now.items() if v != last[k]}
        self._n1mm_last = now
        if save and changed:
            self._save_config(**changed)
        if "n1mm_engine" in changed and self.engine_forced:
            # Nutzer entscheidet selbst über die Engine
            log.info("Engine-Haken umgeschaltet: Engine nur für diesen Lauf endet")
            self.engine_forced = False
        self._apply_n1mm()

    def _apply_n1mm(self):
        """Brücke zu N1MM nach den wirksamen Wegen starten, umstellen oder stoppen."""
        ways = self._effective_ways()
        if self.n1mm_var.get() or self.engine_forced:
            if self.n1mm is None:
                log.info("N1MM-Anbindung ein: %s, Engine-Port %d%s", ways, self.rpc_port,
                         " (Engine nur für diesen Lauf)" if self.engine_forced else "")
                self.n1mm = N1MMBridge(rpc_port=self.rpc_port,
                                       engine_title=self.engine_title, **ways)
                failed = self.n1mm.start_failures
            else:
                log.info("N1MM-Übergabe: %s", ways)
                self.n1mm.engine_title = self.engine_title
                failed = self.n1mm.configure(rpc_port=self.rpc_port, **ways)
            for exc in failed:
                self.report_error(exc, _MSG_CTX_N1MM)
        else:
            if self.n1mm is not None:
                log.info("N1MM-Anbindung aus")
                self.n1mm.stop()
                self.n1mm = None
            self.n1mm_status.set(_MSG_N1MM_OFF)
        self._sync_engine_window()

    def request_engine(self, port, title):
        """N1MM hat einen zweiten CW Decoder als Engine gestartet, und dieser
        bittet uns, sie anzubieten (Anforderungsdatei, ADR-0030). Engine nur
        für diesen Lauf mit Port und Fenstertitel von N1MM; Haken und Config
        bleiben unverändert. Fehler (z. B. Port belegt) zeigt report_error."""
        port = int(port)
        if (self.n1mm is not None and self.n1mm.engine is not None
                and self.rpc_port == port and self.engine_title == title):
            log.info("Engine-Anforderung: Engine läuft schon auf Port %d", port)
            return
        log.info("Engine-Anforderung von N1MM: Port %d, Titel %r – Engine für diesen "
                 "Lauf ein (Haken und Config bleiben)", port, title)
        self.rpc_port = port            # nicht gespeichert (set_rpc_port speichert)
        self.engine_title = title
        self.engine_forced = True
        self._apply_n1mm()
        if self.n1mm is not None and self.n1mm.engine is not None:
            self._note(_MSG_ENGINE_FORCED)

    def _check_engine_request(self):
        """Aus _poll: Anforderungsdatei der zweiten Instanz abholen (4-mal je s)."""
        if self.engine_request_file is None or time.monotonic() < self._request_next:
            return
        self._request_next = time.monotonic() + 0.25
        from .engine_request import take_request
        req = take_request(self.engine_request_file)
        if req is not None:
            self.request_engine(*req)

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
        if want and self.engine_win is not None and self.engine_win.title() != self.engine_title:
            self.engine_win.title(self.engine_title)
            log.info("Engine-Fenster heißt jetzt %r", self.engine_title)
        if want and self.engine_win is None:
            win = tk.Toplevel(self)
            win.title(self.engine_title)
            # Kein transient(): ein Fenster mit Besitzer findet N1MM nicht
            # (getestet). _poll versteckt es wieder, wenn N1MM es einblendet,
            # sonst hielte Windows es für das Hauptfenster (taskkill, Taskleiste).
            win.protocol("WM_DELETE_WINDOW", self._engine_window_closed)
            win.withdraw()
            self.engine_win = win
            log.info("Engine-Fenster %r angelegt", self.engine_title)
        elif not want and self.engine_win is not None:
            try:
                self.engine_win.destroy()
            except tk.TclError:
                pass
            self.engine_win = None

    def _engine_window_closed(self):
        """WM_CLOSE am Engine-Fenster: wirklich schließen, gleich neu anlegen.

        N1MM schließt beim Start mit offenem CW Reader eine vermeintlich
        übrige fldigi-Engine: Es schickt WM_CLOSE an das Fenster mit dem
        Engine-Titel, bis es verschwindet (gemessen über 3000-mal pro
        Sekunde, Issue #13). Bliebe es nur versteckt, hinge N1MM beim
        Startbild. Danach sucht N1MM das Fenster wieder; deshalb kommt es
        nach ENGINE_WIN_REOPEN_MS neu."""
        if self.engine_win is None:
            return
        log.info("Engine-Fenster von außen geschlossen (N1MM-Start?), "
                 "neu in %d ms", ENGINE_WIN_REOPEN_MS)
        try:
            self.engine_win.destroy()
        except tk.TclError:
            pass
        self.engine_win = None
        self.after(ENGINE_WIN_REOPEN_MS, self._sync_engine_window)

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
                    # Leerzeichen bzw. Absatz (Zeichen kommen als "char")
                    self._insert_decoded(val, gen)
                    self._engine_text(val)
                elif kind == "char":
                    # Zeichen mit Vertrauen (ADR-0023); N1MM bekommt es unverändert
                    ch, conf = val
                    self._insert_decoded(ch, gen, conf)
                    self._engine_char(ch, gen)
                elif kind == "seg":
                    if gen == self.gen:
                        self._insert_separators(val)
                        self._engine_words.cut(val)
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
                elif kind == "replace":
                    self.replace_call(*val)
                elif kind == "update":
                    self.handle_update_result(*val)
                elif kind == "saved":
                    self._saved(*val)
                elif kind == "save_error":
                    info = self.report_error(val, _MSG_CTX_SAVE)
                    self._note(info.status)
                elif kind == "replay_done":
                    self._replay_done(val)
        except queue.Empty:
            pass
        self._check_engine_request()
        self._tick_hold()
        if self.live:
            self._draw_spectrum()
        if self.engine_win is not None and self.engine_win.state() != "withdrawn":
            # N1MM blendet das Fenster seiner Engine ein; bei uns ist es leer
            self.engine_win.withdraw()
        if self.n1mm:
            r = self.n1mm.radio
            if r.connected and r.freq_khz is not None:
                # SO2R/SO2V: Nummer des Fokus-Radios dazu (#31)
                mode = (r.mode or "") + (f" R{r.radio_nr}" if r.multi else "")
                line = _MSG_N1MM_RADIO.format(freq=r.freq_khz, mode=mode,
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
        if self.replay_secs is not None or self.hold.active():
            text += "   " + self._replay_text()
        if self.status_note and time.monotonic() < self.status_note[1]:
            text += "   " + self.status_note[0]
        self._last_st = st
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

    # -- Wörterbuch-Zerlegung (ADR-0026) ----------------------------------
    def _insert_separators(self, cuts):
        """Grauen Trenner · vor die Zeichen cuts (Positionen im Strom) setzen.

        Die gemerkten Textindizes der folgenden Zeichen derselben Zeile
        rücken um eins nach rechts; der Trenner selbst zählt nicht als
        Zeichen des Stroms (Rufzeichen-Markierung bleibt stimmig)."""
        for p in sorted(cuts, reverse=True):
            tok = self._tokens.get(p)
            if tok is None:
                continue
            line, col = (int(v) for v in tok[0].split("."))
            self.text.insert(tok[0], SEGMENT_SEP, (INFERRED_TAG,))
            for q in range(p, self._tok_n):
                t = self._tokens.get(q)
                if t is not None:
                    self._tokens[q] = (_shift_index(t[0], line, col),
                                       _shift_index(t[1], line, col))

    def _engine_segmented(self):
        return bool(self.segment_var.get()) and bool(self.engine_seg_var.get())

    def _engine_emit(self, text):
        if self.n1mm:
            self.n1mm.feed_text(text)

    def _engine_char(self, ch, gen):
        """Zeichen an N1MMs CW Reader: sofort oder (zerlegt) am Wortende."""
        if self._engine_segmented() and gen == self.gen:
            self._engine_words.add(ch, self._tok_n - 1)
        else:
            self._engine_emit(ch)

    def _engine_text(self, text):
        if text.strip():
            self._engine_words.end()
            self._engine_emit(text)
        else:
            self._engine_words.end(text)

    def _segment_changed(self):
        on = bool(self.segment_var.get())
        self._save_config(segment_words=on,
                          n1mm_engine_segmented=bool(self.engine_seg_var.get()))
        if self.live is not None:
            self.live.spotter.segment = on
        self._engine_words.end()
        log.info("Wörterbuch-Zerlegung %s, an N1MM getrennt %s", on,
                 bool(self.engine_seg_var.get()))

    # -- Super Check Partial (ADR-0026) ----------------------------------
    def _call_in_scp(self, call):
        from . import scp
        return bool(call) and scp.DEFAULT.is_known(call)

    def _call_near(self, call):
        """Bekannte Nachbarn (ein Edit) eines Rufzeichens, das nicht in SCP
        steht; leer für bekannte Rufzeichen."""
        if not call or self._call_in_scp(call):
            return []
        if call not in self._near_cache:
            from . import scp
            self._near_cache[call] = scp.DEFAULT.near(call)
        return self._near_cache[call]

    def _mark_call(self, call, a, b):
        """Zeichen a..b-1 des Stroms als Rufzeichen markieren."""
        first, last = self._tokens.get(a), self._tokens.get(b - 1)
        if first is None or last is None:
            return      # schon aus dem Speicher oder Text gelöscht
        self.text.tag_add(CALL_TAG, first[0], last[1])
        self.text.tag_add(CALL_TAG_PREFIX + call, first[0], last[1])
        if self._call_in_scp(call):
            self.text.tag_add(CALL_SCP_TAG, first[0], last[1])
        if call in self._removed_calls:
            self._add_call(call)        # entfernt, aber wieder gehört (#25)
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
        self.text.tag_configure(CALL_SCP_TAG, background=CALL_SCP_BG)
        self.text.tag_configure(INFERRED_TAG, foreground=INFERRED_FG)
        # Rufzeichen-Markierung liegt über dem Grau (Tag-Priorität), Grün
        # (in SCP) über Gelb
        self.text.tag_raise(CALL_TAG, UNSURE_TAG)
        self.text.tag_raise(CALL_SCP_TAG, CALL_TAG)
        self.text.tag_bind(INFERRED_TAG, "<Enter>", self._inferred_tag_enter)
        self.text.tag_bind(INFERRED_TAG, "<Leave>", self._call_tag_leave)
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

    def _inferred_tag_enter(self, ev=None):
        """Tooltip zum Trenner ·; auf einem Rufzeichen gilt dessen Tooltip."""
        if ev is not None and self._call_at(ev.x, ev.y):
            return
        tip = getattr(self.text, "_cw_tooltip", None)
        if tip is not None:
            tip.set_text(_TT_INFERRED)
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
        if call:
            if self._call_in_scp(call):
                text += "\n" + _TT_CALL_SCP
            else:
                text += "\n" + _TT_CALL_NOT_SCP
                near = self._call_near(call)
                if near:
                    text += "\n" + _TT_CALL_NEAR.format(calls=", ".join(near))
                if len(near) == 1 and base == _TT_CALL_BUTTON:
                    text += "\n" + _TT_CALL_ADOPT.format(call=near[0])
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
        self._removed_calls.discard(call)
        if call in self.calls:
            return
        self.calls.insert(0, call)
        self.calls = self.calls[:CALL_MAX]
        self._render_calls()

    def remove_call(self, call):
        """Knopf entfernen (#25): nur die Liste; die Markierung im Text bleibt
        anklickbar, der Spotter zählt weiter. Wird das Rufzeichen wieder
        gehört, erscheint es wieder."""
        if call not in self.calls:
            return
        log.info("Rufzeichen aus der Liste entfernt: %s", call)
        self.calls.remove(call)
        self._removed_calls.add(call)
        self._render_calls()

    def clear_calls(self):
        """„Alle löschen“: alle Knöpfe weg, Text und Markierungen bleiben."""
        log.info("Rufzeichen-Liste geleert (%d)", len(self.calls))
        self._removed_calls.update(self.calls)
        self.calls = []
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
        # Rufzeichen grün unterlegt, wenn in SCP, sonst gelb wie im Text
        call_bg = CALL_SCP_BG if self._call_in_scp(call) else CALL_TAG_BG
        row = tk.Frame(self.call_frame, relief="raised", bd=1, bg=bg, cursor="hand2",
                       takefocus=1)
        row.pack(fill="x", pady=1)
        lbl = tk.Label(row, text=call, font=self._call_font(), anchor="w",
                       width=CALL_CHARS, bg=call_bg, pady=0)
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
        # „×“: eigener Klickbereich, übergibt nichts, entfernt nur (#25)
        rm = tk.Label(row, text=_LBL_CALL_REMOVE_X, bg=bg, fg="#707070", padx=4, pady=0,
                      cursor="hand2")
        rm.pack(side="right", padx=(0, 2))
        rm.bind("<ButtonRelease-1>", lambda _e: self.remove_call(call) or "break")
        rm.bind("<Enter>", lambda _e: rm.configure(fg="#c03030"))
        rm.bind("<Leave>", lambda _e: rm.configure(fg="#707070"))
        attach_tooltip(rm, _TT_CALL_REMOVE)
        parts["remove"] = rm
        parts["tooltip"] = tip = self._call_tooltip(_TT_CALL_BUTTON, call)

        parts["call_bg"] = call_bg

        def paint(color):
            for w in widgets:
                try:
                    # ohne Hover: Rufzeichen behält sein Grün bzw. Gelb
                    w.configure(bg=call_bg if (w is lbl and color == bg) else color)
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
            w.bind("<Button-3>", lambda ev: self._call_context(ev, call), add="+")
            attach_tooltip(w, tip)
        row.bind("<Return>", lambda _e: self._send_call(call))
        row.bind("<space>", lambda _e: self._send_call(call))
        self.call_rows[call] = parts
        return parts

    def replace_call(self, old, new):
        """Kürzeren Knopf durch das ganze Rufzeichen ersetzen (IK2J ->
        IK2JET, #23): gleicher Platz; die Markierungen des kurzen im Text
        bleiben. Gibt es keinen kurzen Knopf, kommt der neue nach oben."""
        log.info("Rufzeichen ersetzt: %s -> %s", old, new)
        if old not in self.calls:
            return self._add_call(new)
        calls = [c for c in self.calls if c != new]
        self.calls = [new if c == old else c for c in calls]
        self._render_calls()

    def call_suggestion(self, call):
        """Der eine bekannte Nachbar (SCP, ein Edit) oder None – bei keinem
        oder mehreren Nachbarn gibt es keinen Vorschlag zum Übernehmen."""
        near = self._call_near(call)
        return near[0] if len(near) == 1 else None

    def call_menu_for(self, call):
        """Kontextmenü eines Knopfs: „X übernehmen“, wenn es genau einen
        Vorschlag gibt (nie automatisch, ADR-0026), und „Entfernen“ (#25)."""
        menu = tk.Menu(self, tearoff=False)
        new = self.call_suggestion(call)
        if new is not None:
            menu.add_command(label=_LBL_CALL_ADOPT.format(call=new),
                             command=lambda: self.adopt_call(call, new))
        menu.add_command(label=_LBL_CALL_REMOVE, command=lambda: self.remove_call(call))
        self.call_menu = menu       # Tests
        return menu

    def _call_context(self, ev, call):
        """Rechtsklick auf einen Knopf: Kontextmenü (call_menu_for)."""
        menu = self.call_menu_for(call)
        try:
            menu.tk_popup(ev.x_root, ev.y_root)
        finally:
            menu.grab_release()
        return "break"

    def adopt_call(self, old, new):
        """Vorschlag übernehmen: Knopf ersetzen und wie per Klick übergeben."""
        log.info("Vorschlag übernommen: %s -> %s", old, new)
        calls = [c for c in self.calls if c != new]
        self.calls = [new if c == old else c for c in calls]
        if new not in self.calls:
            self.calls.insert(0, new)
        self.calls = self.calls[:CALL_MAX]
        self._render_calls()
        self._send_call(new)

    def _send_call(self, call):
        if not self.n1mm:
            self.n1mm_status.set(_MSG_N1MM_DISABLED)
            return
        st = self.live.dec.status if self.live else {"snr_db": 20, "wpm": 25}
        msg = self.n1mm.send_call(call, st["snr_db"], st["wpm"])
        self.n1mm_note = (msg, time.monotonic() + 8.0)   # 8 s sichtbar, _poll zeigt sie an
        if self.n1mm.last_failure is not None:
            self.report_error(self.n1mm.last_failure, _MSG_CTX_N1MM)


def _shift_index(index, line, col):
    """Textindex "Zeile.Spalte" um ein Zeichen nach rechts, wenn er in Zeile
    line ab Spalte col liegt (nach einem Einfügen an line.col)."""
    ln, c = (int(v) for v in index.split("."))
    return f"{ln}.{c + 1}" if ln == line and c >= col else index


def _preload_dxcc():
    try:
        from . import dxcc
        dxcc.load()
    except Exception as e:  # noqa: BLE001 - Anzeige fällt dann nur weg
        log.warning("DXCC-Daten nicht geladen: %s", e)
    try:
        from . import scp
        scp.load()
    except Exception as e:  # noqa: BLE001 - dann ohne SCP (alles gelb)
        log.warning("Super Check Partial nicht geladen: %s", e)


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
    if lock is not None:
        # _poll holt sie ab; veraltete (> 30 s) verwirft take_request selbst
        from .engine_request import REQUEST_FILE
        app.engine_request_file = lock.path.parent / REQUEST_FILE
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

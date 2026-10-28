# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""Fehlermeldungen für Menschen (ADR-0007).

classify_error(exc) -> ErrorInfo
    Ordnet erwartete Fehler (Soundkarte, Port belegt, N1MM-Fenster, Config,
    Update, Ausschnitt speichern, Wiedergabe) einem Klartext mit Handlungshinweis zu. Alles andere ist ein
    "Unerwarteter Fehler" mit Traceback im Detailbereich. Reine Logik,
    ohne Display testbar.

show_error(parent, title, message, detail=None)
    Fehlerdialog mit aufklappbarem, kopierbarem Detailbereich.

Im Terminal-Modus (live.py, decode_wav.py) bleiben Meldungen auf stderr.
"""
import errno
import logging
import traceback
from dataclasses import dataclass

log = logging.getLogger(__name__)

_TITLE_AUDIO = "Soundkarte nicht verfügbar"
_MSG_AUDIO = ("Der Audio-Eingang ließ sich nicht öffnen.\n\n"
              "Bitte prüfen: Ist das Funkgerät bzw. USB-Audio angeschlossen und "
              "eingeschaltet? Nutzt ein anderes Programm das Gerät exklusiv? "
              "Danach ein anderes Gerät wählen oder erneut starten.")
_STATUS_AUDIO = "Soundkarte nicht verfügbar – Gerät prüfen"

_TITLE_PORT = "Port belegt"
_MSG_PORT = ("Ein Netzwerk-Port für die N1MM-Anbindung ist bereits belegt.\n\n"
             "Meist läuft der Decoder schon ein zweites Mal oder ein anderes "
             "Programm empfängt die N1MM-Broadcasts (UDP 12060) bzw. nutzt "
             "Port 7373. Das andere Programm beenden und die N1MM-Anbindung "
             "aus- und wieder einschalten.")
_STATUS_PORT = "N1MM: Port belegt"

_TITLE_ENGINE_PORT = "Port für den N1MM CW Reader belegt"
_MSG_ENGINE_PORT = ("Die Engine für das CW-Reader-Fenster von N1MM konnte ihren Port "
                    "nicht öffnen.\n\n"
                    "Meist läuft fldigi als CW-Reader-Engine oder der CW Decoder ein "
                    "zweites Mal. Das andere Programm beenden oder unter "
                    "„N1MM-Übergabe…“ einen anderen Port wählen. Der Decoder läuft "
                    "ohne Engine weiter.")
_STATUS_ENGINE_PORT = "N1MM CW Reader: Port belegt"

_TITLE_SPOT = "Spot nicht gesendet"
_MSG_SPOT = ("Das Rufzeichen ging nicht als Spot an N1MM.\n\n"
             "In N1MM das Telnet-Fenster mit 127.0.0.1, Port 7373 verbinden. Für die "
             "Frequenz in N1MM unter Config → Configure Ports → Broadcast Data "
             "„Radio“ an 127.0.0.1:12060 senden lassen oder den CW Reader von N1MM "
             "öffnen. Der Spot-Weg lässt sich unter „N1MM-Übergabe…“ abschalten.")
_STATUS_SPOT = "Spot nicht gesendet"

_TITLE_N1MM = "N1MM-Fenster nicht gefunden"
_MSG_N1MM = ("Das Rufzeichen konnte nicht an N1MM Logger+ übergeben werden: "
             "das Entry Window wurde nicht gefunden.\n\n"
             "Läuft N1MM? Ist das Entry Window geöffnet? Die gefundenen "
             "Fenstertitel stehen im Log (Hilfe → Log-Ordner öffnen).")
_STATUS_N1MM = "N1MM-Fenster nicht gefunden"

_TITLE_CONFIG = "Einstellungen ungültig"
_MSG_CONFIG = ("Die Einstellungsdatei war beschädigt und wurde beiseitegelegt. "
               "Es gelten die Standardwerte; bitte Gerät und Optionen neu wählen.")
_STATUS_CONFIG = "Einstellungen zurückgesetzt"

_TITLE_UPDATE = "Update nicht möglich"
_MSG_UPDATE = ("Die Suche nach Updates bzw. der Download hat nicht geklappt.\n\n"
               "Bitte die Internetverbindung prüfen und es später erneut versuchen. "
               "Neue Versionen gibt es auch unter "
               "https://github.com/kainomatic/cw-decoder/releases.")
_STATUS_UPDATE = "Update-Prüfung fehlgeschlagen"

_TITLE_SAVE_LAST = "Ausschnitt nicht gespeichert"
_MSG_SAVE_LAST = ("Die letzten Sekunden ließen sich nicht als WAV speichern.\n\n"
                  "Bitte prüfen: Ist der Ordner Dokumente\\CW Decoder\\Aufnahmen "
                  "beschreibbar (Schreibschutz, Virenscanner, OneDrive-Sperre)? Ist "
                  "die Platte voll? Der Decoder läuft weiter.")
_STATUS_SAVE_LAST = "Ausschnitt nicht gespeichert – Aufnahmen-Ordner prüfen"

_TITLE_REPLAY = "Wiedergabe nicht möglich"
_MSG_REPLAY = ("„Nochmal hören“ konnte nichts abspielen: Das Standard-Ausgabegerät "
               "fehlt oder ist belegt.\n\n"
               "Bitte in Windows unter Einstellungen → System → Sound ein "
               "Ausgabegerät (Lautsprecher, Kopfhörer) als Standard wählen und "
               "prüfen, ob ein anderes Programm es exklusiv nutzt. Der Decoder "
               "läuft weiter.")
_STATUS_REPLAY = "Wiedergabe nicht möglich – Ausgabegerät prüfen"
_TITLE_OUTPUT_MISSING = "Ausgabegerät nicht gefunden"
_MSG_OUTPUT_MISSING = ("Das unter Einstellungen → „Puffer und Nochmal hören…“ gewählte "
                       "Ausgabegerät fehlt (abgezogen oder umbenannt) oder lässt sich "
                       "nicht öffnen. „Nochmal hören“ spielt deshalb über die "
                       "Standard-Ausgabe.\n\n"
                       "Gerät wieder anschließen oder dort ein anderes wählen. Der "
                       "Decoder läuft weiter.")
_STATUS_OUTPUT_MISSING = "Ausgabegerät fehlt – Standard-Ausgabe benutzt"

_TITLE_UNEXPECTED = "Unerwarteter Fehler"
_MSG_UNEXPECTED = ("Es ist ein unerwarteter Fehler aufgetreten:\n{err}\n\n"
                   "Bitte über Hilfe → Fehler melden… einen Bericht schicken.")
_STATUS_UNEXPECTED = "Fehler: {err}"

_LBL_OK = "OK"
_LBL_SHOW_DETAILS = "▼ Details anzeigen"
_LBL_HIDE_DETAILS = "▲ Details ausblenden"
_LBL_COPY = "Details kopieren"
_TT_DETAILS = "Technische Einzelheiten zum Fehler, z. B. für einen Fehlerbericht."
_TT_COPY = "Details in die Zwischenablage kopieren."

# Windows-Fehlernummer für "Adresse wird bereits verwendet"
_WSAEADDRINUSE = 10048


@dataclass(frozen=True)
class ErrorInfo:
    title: str
    message: str
    status: str          # kurze Zeile für die Statusleiste
    expected: bool       # True = bekannter Fall, Klartext genügt
    detail: str = None   # Technische Details (Traceback bei unerwarteten Fehlern)


def _is_port_in_use(exc) -> bool:
    from .n1mm import PortInUseError
    if isinstance(exc, PortInUseError):
        return True
    return isinstance(exc, OSError) and (
        exc.errno == errno.EADDRINUSE or getattr(exc, "winerror", None) == _WSAEADDRINUSE)


def _is_audio_error(exc) -> bool:
    from .live import AudioDeviceError
    # sounddevice.PortAudioError ohne sounddevice zu importieren erkennen
    return isinstance(exc, AudioDeviceError) or type(exc).__name__ == "PortAudioError"


def _traceback_text(exc) -> str:
    return "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))


def classify_error(exc: BaseException) -> ErrorInfo:
    """Ausnahme auf eine Meldung für Menschen abbilden."""
    from .config import ConfigError
    from .n1mm import EnginePortInUseError, EntryWindowNotFoundError, SpotNotSentError
    from .updater import UpdateError
    from .replay import OutputDeviceMissingError, ReplayError
    from .ringbuffer import SaveLastError

    detail = str(exc) or None
    # vor Soundkarte und Port: beides sind eigene Fälle (ADR-0024)
    if isinstance(exc, OutputDeviceMissingError):
        return ErrorInfo(_TITLE_OUTPUT_MISSING, _MSG_OUTPUT_MISSING, _STATUS_OUTPUT_MISSING,
                         True, detail)
    if isinstance(exc, ReplayError):
        return ErrorInfo(_TITLE_REPLAY, _MSG_REPLAY, _STATUS_REPLAY, True, detail)
    if isinstance(exc, SaveLastError):
        return ErrorInfo(_TITLE_SAVE_LAST, _MSG_SAVE_LAST, _STATUS_SAVE_LAST, True, detail)
    if _is_audio_error(exc):
        return ErrorInfo(_TITLE_AUDIO, _MSG_AUDIO, _STATUS_AUDIO, True, detail)
    if isinstance(exc, EnginePortInUseError):
        return ErrorInfo(_TITLE_ENGINE_PORT, _MSG_ENGINE_PORT, _STATUS_ENGINE_PORT, True,
                         detail)
    if isinstance(exc, SpotNotSentError):
        return ErrorInfo(_TITLE_SPOT, _MSG_SPOT, _STATUS_SPOT, True, detail)
    if _is_port_in_use(exc):
        return ErrorInfo(_TITLE_PORT, _MSG_PORT, _STATUS_PORT, True, detail)
    if isinstance(exc, EntryWindowNotFoundError):
        return ErrorInfo(_TITLE_N1MM, _MSG_N1MM, _STATUS_N1MM, True, detail)
    if isinstance(exc, UpdateError):
        return ErrorInfo(_TITLE_UPDATE, _MSG_UPDATE, _STATUS_UPDATE, True, detail)
    if isinstance(exc, ConfigError):
        return ErrorInfo(_TITLE_CONFIG, _MSG_CONFIG, _STATUS_CONFIG, True, detail)
    err = f"{type(exc).__name__}: {exc}"
    return ErrorInfo(_TITLE_UNEXPECTED, _MSG_UNEXPECTED.format(err=err),
                     _STATUS_UNEXPECTED.format(err=err), False, _traceback_text(exc))


def show_error(parent, title, message, detail=None, wait=False):
    """Fehlerdialog anzeigen und zurückgeben.

    detail erscheint in einem aufklappbaren, schreibgeschützten Textfeld.
    wait=True blockiert bis zum Schließen (z. B. vor dem Hauptfenster).
    """
    import tkinter as tk
    from tkinter import ttk
    from .gui_tooltip import attach_tooltip

    dlg = tk.Toplevel(parent)
    dlg.title(title)
    dlg.resizable(True, True)
    if parent is not None:
        try:
            dlg.transient(parent)
        except tk.TclError:
            pass

    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)
    ttk.Label(frm, text=message, wraplength=440, justify="left").pack(anchor="w")

    if detail:
        box = ttk.Frame(frm)
        txt = tk.Text(box, height=12, width=78, wrap="none", font=("Consolas", 9))
        sy = ttk.Scrollbar(box, orient="vertical", command=txt.yview)
        sx = ttk.Scrollbar(box, orient="horizontal", command=txt.xview)
        txt.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)
        sy.pack(side="right", fill="y")
        sx.pack(side="bottom", fill="x")
        txt.pack(side="left", fill="both", expand=True)
        txt.insert("1.0", detail)
        txt.configure(state="disabled")
        attach_tooltip(txt, _TT_DETAILS)

        row = ttk.Frame(frm)
        row.pack(fill="x", pady=(8, 0))
        shown = {"on": False}

        def toggle():
            shown["on"] = not shown["on"]
            if shown["on"]:
                box.pack(fill="both", expand=True, pady=(6, 0), after=row)
                btn.configure(text=_LBL_HIDE_DETAILS)
            else:
                box.pack_forget()
                btn.configure(text=_LBL_SHOW_DETAILS)

        def copy():
            dlg.clipboard_clear()
            dlg.clipboard_append(detail)

        btn = ttk.Button(row, text=_LBL_SHOW_DETAILS, command=toggle)
        btn.pack(side="left")
        attach_tooltip(btn, _TT_DETAILS)
        cbtn = ttk.Button(row, text=_LBL_COPY, command=copy)
        cbtn.pack(side="left", padx=6)
        attach_tooltip(cbtn, _TT_COPY)

    ok = ttk.Button(frm, text=_LBL_OK, command=dlg.destroy)
    ok.pack(side="bottom", anchor="e", pady=(12, 0))
    dlg.bind("<Return>", lambda _e: dlg.destroy())
    dlg.bind("<Escape>", lambda _e: dlg.destroy())
    ok.focus_set()
    if wait:
        dlg.grab_set()
        dlg.wait_window()
    return dlg


def report_exception(parent, exc, context=None):
    """Ausnahme loggen und als Dialog zeigen. Liefert das ErrorInfo."""
    info = classify_error(exc)
    if info.expected:
        log.warning("%s%s: %s", f"{context}: " if context else "", info.title, exc)
    else:
        log.error("%s", context or "Unerwarteter Fehler",
                  exc_info=(type(exc), exc, exc.__traceback__))
    show_error(parent, info.title, info.message, info.detail)
    return info

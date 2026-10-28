# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""Dialog „Übergabe an N1MM“: Wege und Engine-Port (ADR-0022, #3).

Die Haken hängen direkt an den tk-Variablen des Hauptfensters und wirken
sofort (App._n1mm_changed). Der Port wird beim Schließen oder mit Enter
übernommen; ein ungültiger Wert springt auf den alten zurück.

Der Dialog selbst hat keine tk-Variablen: Nach dem Schließen bleibt so
nichts übrig, dessen Abräumen Tcl aus einem fremden Thread aufrufen könnte.
"""
import tkinter as tk
from tkinter import ttk

from .gui_tooltip import attach_tooltip

_LBL_TITLE = "Übergabe an N1MM"
_LBL_WAYS = "Rufzeichen an N1MM übergeben über:"
_LBL_ENGINE = "CW Reader von N1MM (Engine)"
_LBL_SPOT = "Skimmer-Spot (Telnet 7373)"
_LBL_TYPE = "ins Entry Window tippen"
_LBL_WIPE = "vorher Alt+W (Wipe)"
_LBL_CLIPBOARD = "Zwischenablage"
_LBL_PORT = "Port der Engine:"
_LBL_CLOSE = "Schließen"
_MSG_PORT_INVALID = "Port {value!r} ungültig (1024–65535), bleibt bei {port}"

_TT_ENGINE = ("Der CW Decoder spricht die Schnittstelle von fldigi. In N1MM: Window → CW Reader → "
              "Setup → Fldigi, Pfad zu CWDecoder.exe. N1MM zeigt dann unseren Text; "
              "ein Klick auf ein Rufzeichen dort setzt es ins Entry Window.")
_TT_SPOT = ("Klick auf ein Rufzeichen schickt einen Skimmer-Spot auf der aktuellen "
            "Frequenz. In N1MM: Telnet-Fenster mit 127.0.0.1, Port 7373 verbinden.")
_TT_TYPE = ("Klick auf ein Rufzeichen tippt es ins Entry Window von N1MM "
            "(holt N1MM dafür in den Vordergrund).")
_TT_WIPE = "Vor dem Eintippen Alt+W senden, damit das Entry Window leer ist."
_TT_CLIPBOARD = ("Klick auf ein Rufzeichen legt es in die Zwischenablage. Beim Tippen "
                 "auch der Rückfallweg, wenn N1MM nicht gefunden wird.")
_TT_PORT = ("XML-RPC-Port für den CW Reader. N1MM nimmt für CW Reader 1 den Port "
            "7367 und startet die Engine damit; nur bei Konflikten ändern.")
_TT_CLOSE = "Dialog schließen; der Port wird übernommen."


def parse_port(text):
    """Port aus dem Eingabefeld oder None, wenn ungültig."""
    try:
        port = int(str(text).strip())
    except ValueError:
        return None
    return port if 1024 <= port <= 65535 else None


class N1MMSettingsDialog(tk.Toplevel):
    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.title(_LBL_TITLE)
        self.resizable(False, False)
        self.transient(app)
        frm = ttk.Frame(self, padding=12)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, text=_LBL_WAYS).pack(anchor="w", pady=(0, 4))
        self.checks = {}
        for key, label, var, tip, pad in (
                ("engine", _LBL_ENGINE, app.engine_var, _TT_ENGINE, 0),
                ("spot", _LBL_SPOT, app.spot_var, _TT_SPOT, 0),
                ("type", _LBL_TYPE, app.type_var, _TT_TYPE, 0),
                ("wipe", _LBL_WIPE, app.wipe_var, _TT_WIPE, 20),
                ("clipboard", _LBL_CLIPBOARD, app.clip_var, _TT_CLIPBOARD, 0)):
            cb = ttk.Checkbutton(frm, text=label, variable=var, command=app._n1mm_changed)
            cb.pack(anchor="w", padx=(pad, 0))
            attach_tooltip(cb, tip)
            self.checks[key] = cb
        row = ttk.Frame(frm)
        row.pack(anchor="w", pady=(8, 0))
        lbl = ttk.Label(row, text=_LBL_PORT)
        lbl.pack(side="left")
        attach_tooltip(lbl, _TT_PORT)
        self.port_entry = ttk.Entry(row, width=7)
        self.port_entry.insert(0, str(app.rpc_port))
        self.port_entry.pack(side="left", padx=(6, 0))
        self.port_entry.bind("<Return>", lambda _e: self.apply_port())
        attach_tooltip(self.port_entry, _TT_PORT)
        self.note = ttk.Label(frm, text="", foreground="#b03030", wraplength=280)
        self.note.pack(anchor="w", pady=(4, 0))
        btn = ttk.Button(frm, text=_LBL_CLOSE, command=self.close)
        btn.pack(anchor="e", pady=(8, 0))
        attach_tooltip(btn, _TT_CLOSE)
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.bind("<Escape>", lambda _e: self.close())
        # über dem Hauptfenster statt in der Bildschirmecke
        self.update_idletasks()
        x = app.winfo_rootx() + max((app.winfo_width() - self.winfo_reqwidth()) // 2, 0)
        y = app.winfo_rooty() + max((app.winfo_height() - self.winfo_reqheight()) // 3, 0)
        self.geometry(f"+{x}+{y}")

    def set_port_text(self, text):
        self.port_entry.delete(0, "end")
        self.port_entry.insert(0, text)

    def apply_port(self) -> bool:
        text = self.port_entry.get()
        port = parse_port(text)
        if port is None:
            self.note.configure(text=_MSG_PORT_INVALID.format(value=text,
                                                              port=self.app.rpc_port))
            self.set_port_text(str(self.app.rpc_port))
            return False
        self.note.configure(text="")
        if port != self.app.rpc_port:
            self.app.set_rpc_port(port)
        return True

    def close(self):
        self.apply_port()
        self.app.n1mm_dialog = None
        self.destroy()

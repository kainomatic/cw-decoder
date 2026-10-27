# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""Dialog „Puffer und Nochmal hören“ (ADR-0024, #19).

Drei Zahlen (Puffergröße, Länge für „Letzte … s speichern“, Länge für
„Nochmal hören“) und der Haken „langsamer (0,7×)“. Die Zahlen werden beim
Schließen oder mit Enter übernommen; ein ungültiger Wert springt auf den
alten zurück. Der Haken hängt an App.slow_var und wirkt sofort.

Wie der N1MM-Dialog ohne eigene tk-Variablen (Abräumen nur im tk-Thread).
"""
import tkinter as tk
from tkinter import ttk

from . import config as config_mod
from .gui_tooltip import attach_tooltip

_LBL_TITLE = "Puffer und Nochmal hören"
_LBL_RING = "Puffer (Sekunden):"
_LBL_SAVE = "Speichern (Sekunden):"
_LBL_REPLAY = "Nochmal hören (Sekunden):"
_LBL_SLOW = "Nochmal hören langsamer (0,7×)"
_LBL_CLOSE = "Schließen"
_MSG_INVALID = "{name}: {value!r} ungültig ({lo}–{hi}), bleibt bei {old}"

_TT_RING = ("So viele Sekunden Audio hält der Decoder im Speicher (10–300). "
            "Gilt ab dem nächsten Start des Decoders.")
_TT_SAVE = ("So viele Sekunden schreibt „Letzte … s speichern“ (Strg+S) als WAV "
            "samt Decodier-Log in den Aufnahmen-Ordner (5 bis Puffergröße).")
_TT_REPLAY = ("So viele Sekunden spielt „Nochmal hören“ (Strg+R) über das "
              "Standard-Ausgabegerät ab (3–30).")
_TT_SLOW = ("„Nochmal hören“ auf 0,7-fache Geschwindigkeit verlangsamen, ohne "
            "dass sich die Tonhöhe ändert.")
_TT_CLOSE = "Dialog schließen; die Werte werden übernommen."

# Schlüssel, Beschriftung, Tooltip
FIELDS = (("ring_seconds", _LBL_RING, _TT_RING),
          ("save_last_s", _LBL_SAVE, _TT_SAVE),
          ("replay_s", _LBL_REPLAY, _TT_REPLAY))


def limits(key, cfg):
    """(min, max) für einen Schlüssel; save_last_s höchstens die Puffergröße."""
    lo, hi = {"ring_seconds": config_mod.RING_SECONDS_RANGE,
              "save_last_s": config_mod.SAVE_LAST_RANGE,
              "replay_s": config_mod.REPLAY_RANGE}[key]
    if key == "save_last_s":
        hi = min(hi, cfg["ring_seconds"])
    return lo, hi


def parse_seconds(text, lo, hi):
    """Ganze Sekunden aus dem Feld oder None, wenn ungültig."""
    try:
        v = int(str(text).strip())
    except ValueError:
        return None
    return v if lo <= v <= hi else None


class RingSettingsDialog(tk.Toplevel):
    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.title(_LBL_TITLE)
        self.resizable(False, False)
        self.transient(app)
        frm = ttk.Frame(self, padding=12)
        frm.pack(fill="both", expand=True)
        self.entries = {}
        for row, (key, label, tip) in enumerate(FIELDS):
            lbl = ttk.Label(frm, text=label)
            lbl.grid(row=row, column=0, sticky="w", pady=2)
            attach_tooltip(lbl, tip)
            lo, hi = limits(key, app.cfg)
            sp = ttk.Spinbox(frm, from_=lo, to=config_mod.SAVE_LAST_RANGE[1]
                             if key == "save_last_s" else hi, width=6,
                             command=self.apply)
            sp.set(str(app.cfg[key]))
            sp.grid(row=row, column=1, sticky="w", padx=(8, 0), pady=2)
            sp.bind("<Return>", lambda _e: self.apply())
            attach_tooltip(sp, tip)
            self.entries[key] = sp
        cb = ttk.Checkbutton(frm, text=_LBL_SLOW, variable=app.slow_var,
                             command=app._slow_changed)
        cb.grid(row=len(FIELDS), column=0, columnspan=2, sticky="w", pady=(6, 0))
        attach_tooltip(cb, _TT_SLOW)
        self.check_slow = cb
        self.note = ttk.Label(frm, text="", foreground="#b03030", wraplength=300)
        self.note.grid(row=len(FIELDS) + 1, column=0, columnspan=2, sticky="w", pady=(4, 0))
        btn = ttk.Button(frm, text=_LBL_CLOSE, command=self.close)
        btn.grid(row=len(FIELDS) + 2, column=0, columnspan=2, sticky="e", pady=(8, 0))
        attach_tooltip(btn, _TT_CLOSE)
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.bind("<Escape>", lambda _e: self.close())
        self.update_idletasks()
        x = app.winfo_rootx() + max((app.winfo_width() - self.winfo_reqwidth()) // 2, 0)
        y = app.winfo_rooty() + max((app.winfo_height() - self.winfo_reqheight()) // 3, 0)
        self.geometry(f"+{x}+{y}")

    def set_text(self, key, text):
        self.entries[key].set(str(text))

    def apply(self) -> bool:
        """Felder prüfen und übernehmen; ungültige springen zurück."""
        changes, notes = {}, []
        cfg = dict(self.app.cfg)
        for key, label, _tip in FIELDS:
            lo, hi = limits(key, cfg)
            text = self.entries[key].get()
            v = parse_seconds(text, lo, hi)
            if v is None:
                notes.append(_MSG_INVALID.format(name=label.rstrip(":"), value=text,
                                                 lo=lo, hi=hi, old=cfg[key]))
                self.set_text(key, cfg[key])
                continue
            cfg[key] = v
            if v != self.app.cfg[key]:
                changes[key] = v
        self.note.configure(text="\n".join(notes))
        if changes:
            self.app.set_ring_settings(**changes)
        return not notes

    def close(self):
        self.apply()
        self.app.ring_dialog = None
        self.destroy()

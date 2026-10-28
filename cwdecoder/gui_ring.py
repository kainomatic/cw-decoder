# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""Dialog „Puffer und Nochmal hören“ (ADR-0024, #19, #25).

Vier ganze Zahlen (Puffergröße, Länge für „Letzte … s speichern“, Länge
für „Nochmal hören“, Frist des Festhaltens), das Starttempo des Reglers
(0,5–1,0) und das Ausgabegerät („Standard“ oder ein Gerät aus der Liste;
gespeichert wird der Name, gefunden wird es später per Namensteil). Die
Werte werden beim Schließen, mit Enter oder bei Auswahl übernommen; ein
ungültiger Wert springt auf den alten zurück.

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
_LBL_HOLD = "Festhalten nach Ende (Sekunden):"
_LBL_RATE = "Tempo beim Start (0,5–1,0):"
_LBL_DEVICE = "Ausgabegerät:"
_LBL_DEVICE_DEFAULT = "Standard"
_LBL_CLOSE = "Schließen"
_MSG_INVALID = "{name}: {value!r} ungültig ({lo}–{hi}), bleibt bei {old}"

_TT_RING = ("So viele Sekunden Audio hält der Decoder im Speicher (10–300). "
            "Gilt ab dem nächsten Start des Decoders.")
_TT_SAVE = ("So viele Sekunden schreibt „Letzte … s speichern“ (Strg+S) als WAV "
            "samt Decodier-Log in den Aufnahmen-Ordner (5 bis Puffergröße).")
_TT_REPLAY = ("So viele Sekunden spielt „Nochmal hören“ (Strg+R) ab (3–30).")
_TT_HOLD = ("So lange nach dem Ende der Wiedergabe bleibt der Ausschnitt "
            "festgehalten (1–60): Strg+R spielt ihn noch einmal, Strg+S speichert "
            "ihn. Danach verfällt er, und Strg+R fasst die letzten Sekunden neu.")
_TT_RATE = ("Mit diesem Tempo beginnt jeder neue Ausschnitt (0,5 = halb so schnell, "
            "1,0 = Original). Der Regler im Hauptfenster ändert es für den "
            "laufenden Ausschnitt; die Tonhöhe bleibt immer gleich.")
_TT_DEVICE = ("Lautsprecher bzw. Kopfhörer für „Nochmal hören“. Fehlt das Gerät "
              "später (abgezogen), spielt der CW Decoder über die Standard-Ausgabe "
              "und sagt es in der Statuszeile.")
_TT_CLOSE = "Dialog schließen; die Werte werden übernommen."

# Schlüssel, Beschriftung, Tooltip (ganze Sekunden)
FIELDS = (("ring_seconds", _LBL_RING, _TT_RING),
          ("save_last_s", _LBL_SAVE, _TT_SAVE),
          ("replay_s", _LBL_REPLAY, _TT_REPLAY),
          ("replay_hold_s", _LBL_HOLD, _TT_HOLD))


def limits(key, cfg):
    """(min, max) für einen Schlüssel; save_last_s höchstens die Puffergröße."""
    lo, hi = {"ring_seconds": config_mod.RING_SECONDS_RANGE,
              "save_last_s": config_mod.SAVE_LAST_RANGE,
              "replay_s": config_mod.REPLAY_RANGE,
              "replay_hold_s": config_mod.REPLAY_HOLD_RANGE}[key]
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


def parse_rate(text):
    """Tempo 0,5–1,0 (Komma oder Punkt) oder None."""
    lo, hi = config_mod.REPLAY_RATE_RANGE
    try:
        v = float(str(text).strip().replace(",", "."))
    except ValueError:
        return None
    return round(v, 2) if lo <= v <= hi else None


def format_rate(v):
    return f"{v:.2f}".replace(".", ",")


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
        row = 0
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
        row += 1
        lbl = ttk.Label(frm, text=_LBL_RATE)
        lbl.grid(row=row, column=0, sticky="w", pady=2)
        attach_tooltip(lbl, _TT_RATE)
        lo, hi = config_mod.REPLAY_RATE_RANGE
        sp = ttk.Spinbox(frm, from_=lo, to=hi, increment=0.05, width=6,
                         format="%.2f", command=self.apply)
        sp.set(format_rate(app.cfg["replay_rate"]))
        sp.grid(row=row, column=1, sticky="w", padx=(8, 0), pady=2)
        sp.bind("<Return>", lambda _e: self.apply())
        attach_tooltip(sp, _TT_RATE)
        self.entry_rate = sp
        row += 1
        lbl = ttk.Label(frm, text=_LBL_DEVICE)
        lbl.grid(row=row, column=0, sticky="w", pady=2)
        attach_tooltip(lbl, _TT_DEVICE)
        from .replay import output_devices
        names = output_devices()
        current = app.cfg["output_device"]
        if current and current not in names:
            names.append(current)       # gewähltes Gerät gerade nicht da: trotzdem zeigen
        self.device_values = [_LBL_DEVICE_DEFAULT] + names
        cb = ttk.Combobox(frm, values=self.device_values, state="readonly", width=34)
        cb.set(current or _LBL_DEVICE_DEFAULT)
        cb.grid(row=row, column=1, sticky="w", padx=(8, 0), pady=2)
        cb.bind("<<ComboboxSelected>>", lambda _e: self.apply())
        attach_tooltip(cb, _TT_DEVICE)
        self.device_box = cb
        row += 1
        self.note = ttk.Label(frm, text="", foreground="#b03030", wraplength=320)
        self.note.grid(row=row, column=0, columnspan=2, sticky="w", pady=(4, 0))
        btn = ttk.Button(frm, text=_LBL_CLOSE, command=self.close)
        btn.grid(row=row + 1, column=0, columnspan=2, sticky="e", pady=(8, 0))
        attach_tooltip(btn, _TT_CLOSE)
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.bind("<Escape>", lambda _e: self.close())
        self.update_idletasks()
        x = app.winfo_rootx() + max((app.winfo_width() - self.winfo_reqwidth()) // 2, 0)
        y = app.winfo_rooty() + max((app.winfo_height() - self.winfo_reqheight()) // 3, 0)
        self.geometry(f"+{x}+{y}")

    def set_text(self, key, text):
        if key == "replay_rate":
            self.entry_rate.set(str(text))
        else:
            self.entries[key].set(str(text))

    def select_device(self, name):
        """Ausgabegerät wählen (Tests); None oder "" = Standard."""
        self.device_box.set(name or _LBL_DEVICE_DEFAULT)
        return self.apply()

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
        text = self.entry_rate.get()
        rate = parse_rate(text)
        if rate is None:
            lo, hi = config_mod.REPLAY_RATE_RANGE
            notes.append(_MSG_INVALID.format(name=_LBL_RATE.split(" (")[0], value=text,
                                             lo=format_rate(lo), hi=format_rate(hi),
                                             old=format_rate(cfg["replay_rate"])))
            self.entry_rate.set(format_rate(cfg["replay_rate"]))
        elif abs(rate - self.app.cfg["replay_rate"]) > 1e-9:
            changes["replay_rate"] = rate
        dev = self.device_box.get()
        dev = None if dev in ("", _LBL_DEVICE_DEFAULT) else dev
        if dev != self.app.cfg["output_device"]:
            changes["output_device"] = dev
        self.note.configure(text="\n".join(notes))
        if changes:
            self.app.set_ring_settings(**changes)
        return not notes

    def close(self):
        self.apply()
        self.app.ring_dialog = None
        self.destroy()

# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""Hover-Tooltips für tk/ttk-Widgets (ADR-0006).

    attach_tooltip(widget, text, delay_ms=500) -> Tooltip

Der Tooltip erscheint nach delay_ms am Widget und verschwindet beim
Verlassen, bei Mausklick oder wenn das Widget zerstört wird. Fehler beim
Anzeigen (Widget schon weg, Fenster geschlossen) werden geschluckt: ein
Tooltip darf das Programm nie abstürzen lassen.

clamp_to_screen() und tooltip_position() sind reine Logik und ohne Display
testbar.
"""
import logging

log = logging.getLogger(__name__)

DELAY_MS = 500
OFFSET_X = 12
OFFSET_Y = 6
MARGIN = 4
WRAP = "285p"            # Umbruchbreite in Punkten (380 px bei 100 %), wächst mit der Skalierung
BG = "#ffffe0"
FG = "#202020"


def clamp_to_screen(x, y, width, height, screen_w, screen_h, margin=MARGIN):
    """Position (x, y) eines width x height großen Fensters so verschieben,
    dass es mit Abstand margin vollständig auf dem Bildschirm liegt.

    Ist das Fenster größer als der Bildschirm, gewinnt die linke/obere Kante.
    """
    x = min(x, screen_w - width - margin)
    y = min(y, screen_h - height - margin)
    return max(int(x), 0), max(int(y), 0)


def tooltip_position(pointer_x, widget_top, widget_bottom, width, height,
                     screen_w, screen_h):
    """Position des Tooltips: unter dem Widget, ab der Mauszeiger-Spalte.

    Passt er unten nicht mehr auf den Bildschirm, kommt er über das Widget,
    damit er das Widget nicht verdeckt (sonst Flackern durch <Leave>).
    """
    y = widget_bottom + OFFSET_Y
    if y + height + MARGIN > screen_h:
        y = widget_top - height - OFFSET_Y
    return clamp_to_screen(pointer_x + OFFSET_X, y, width, height, screen_w, screen_h)


class Tooltip:
    def __init__(self, widget, text, delay_ms=DELAY_MS):
        self.widget = widget
        self.text = text
        self.delay_ms = delay_ms
        self._after = None
        self._win = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._cancel, add="+")
        widget.bind("<ButtonPress>", self._cancel, add="+")
        widget.bind("<Destroy>", self._cancel, add="+")

    def set_text(self, text):
        """Text ändern; wirkt beim nächsten Einblenden."""
        self.text = text

    def schedule(self):
        """Einblenden nach der Verzögerung (z. B. für Text-Tags)."""
        self._schedule()

    def cancel(self):
        """Ausblenden bzw. geplantes Einblenden abbrechen."""
        self._cancel()

    def _schedule(self, _ev=None):
        self._cancel()
        if not self.text:
            return
        try:
            self._after = self.widget.after(self.delay_ms, self._show)
        except Exception:  # noqa: BLE001 - Widget gerade zerstört
            self._after = None

    def _cancel(self, _ev=None):
        if self._after is not None:
            try:
                self.widget.after_cancel(self._after)
            except Exception:  # noqa: BLE001
                pass
            self._after = None
        self._hide()

    def _show(self):
        self._after = None
        if self._win is not None:
            return
        try:
            import tkinter as tk
            if not self.widget.winfo_exists():
                return
            win = tk.Toplevel(self.widget)
            win.wm_overrideredirect(True)
            try:
                win.wm_attributes("-topmost", True)
            except tk.TclError:
                pass
            tk.Label(win, text=self.text, justify="left", background=BG, foreground=FG,
                     relief="solid", borderwidth=1, padx=5, pady=3,
                     wraplength=WRAP).pack()
            win.update_idletasks()
            top = self.widget.winfo_rooty()
            x, y = tooltip_position(self.widget.winfo_pointerx(), top,
                                    top + self.widget.winfo_height(),
                                    win.winfo_reqwidth(), win.winfo_reqheight(),
                                    self.widget.winfo_screenwidth(),
                                    self.widget.winfo_screenheight())
            win.wm_geometry(f"+{x}+{y}")
            self._win = win
        except Exception as e:  # noqa: BLE001 - Tooltip darf nie abstürzen
            log.debug("Tooltip nicht anzeigbar: %s", e)
            self._hide()

    def _hide(self):
        win, self._win = self._win, None
        if win is not None:
            try:
                win.destroy()
            except Exception:  # noqa: BLE001
                pass


def attach_tooltip(widget, text, delay_ms=DELAY_MS):
    """Tooltip an widget hängen. Die Instanz wird am Widget gehalten, damit
    sie nicht vom Garbage Collector abgeräumt wird."""
    tip = Tooltip(widget, text, delay_ms)
    widget._cw_tooltip = tip
    return tip

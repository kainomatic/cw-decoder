# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""Tooltips (ADR-0006): Positionsrechnung ohne Display, Verhalten mit Display."""
import pytest

from conftest import requires_display
from cwdecoder.gui_tooltip import (MARGIN, OFFSET_X, OFFSET_Y, clamp_to_screen,
                                   tooltip_position)

SW, SH = 1920, 1080


def test_clamp_inside_unchanged():
    assert clamp_to_screen(100, 200, 150, 40, SW, SH) == (100, 200)


def test_clamp_right_edge():
    x, y = clamp_to_screen(1850, 200, 150, 40, SW, SH)
    assert x + 150 + MARGIN == SW and y == 200


def test_clamp_bottom_edge():
    x, y = clamp_to_screen(100, 1070, 150, 40, SW, SH)
    assert y + 40 + MARGIN == SH and x == 100


def test_clamp_negative_to_zero():
    assert clamp_to_screen(-30, -5, 150, 40, SW, SH) == (0, 0)


def test_clamp_larger_than_screen_keeps_top_left():
    assert clamp_to_screen(500, 500, 3000, 2000, SW, SH) == (0, 0)


def test_position_below_widget():
    x, y = tooltip_position(300, 100, 130, 200, 40, SW, SH)
    assert (x, y) == (300 + OFFSET_X, 130 + OFFSET_Y)


def test_position_above_widget_at_bottom_of_screen():
    x, y = tooltip_position(300, 1040, 1070, 200, 40, SW, SH)
    assert y == 1040 - 40 - OFFSET_Y          # darüber, Widget bleibt frei
    assert y + 40 <= 1040


def test_position_right_edge_clamped():
    x, _ = tooltip_position(1900, 100, 130, 200, 40, SW, SH)
    assert x + 200 <= SW


@requires_display
@pytest.mark.gui
def test_tooltip_show_hide_and_destroy():
    import tkinter as tk
    from cwdecoder.gui_tooltip import attach_tooltip
    root = tk.Tk()
    try:
        btn = tk.Button(root, text="x")
        btn.pack()
        root.update()
        tip = attach_tooltip(btn, "Hilfe")
        assert btn._cw_tooltip is tip
        tip._show()
        assert tip._win is not None
        tip._cancel()
        assert tip._win is None
        tip._schedule()
        assert tip._after is not None
        tip._show()
        btn.destroy()               # Widget weg, während Tooltip sichtbar ist
        root.update()
        assert tip._win is None
        tip._show()                 # darf nach Zerstörung nicht abstürzen
        assert tip._win is None
        tip.set_text("neu")
        assert tip.text == "neu"
    finally:
        root.destroy()


@requires_display
@pytest.mark.gui
def test_empty_text_never_shows():
    import tkinter as tk
    from cwdecoder.gui_tooltip import attach_tooltip
    root = tk.Tk()
    try:
        lbl = tk.Label(root, text="x")
        lbl.pack()
        tip = attach_tooltip(lbl, "")
        tip._schedule()
        assert tip._after is None
    finally:
        root.destroy()

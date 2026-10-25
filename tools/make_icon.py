# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""Erzeugt assets/cwdecoder.ico (16–256 px) für EXE und Installer.

    python tools/make_icon.py

Motiv ohne Schriftart, damit es überall gleich aussieht: dunkle Kachel mit
"C" (-.-.) und "W" (.--) in Morsezeichen. Braucht Pillow
(requirements-dev.txt), nicht zur Laufzeit.
"""
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
ICO_PATH = ROOT / "assets" / "cwdecoder.ico"
SIZES = [16, 24, 32, 48, 64, 128, 256]

BACKGROUND = (16, 32, 48, 255)
BORDER = (79, 209, 197, 255)
ROW_C = (246, 173, 85, 255)
ROW_W = (79, 209, 197, 255)
CANVAS = 1024   # groß zeichnen, dann verkleinern


def _row(draw, pattern, y, color, unit, height):
    """Morsezeichen als Balken: '.' = 1 Einheit, '-' = 3, Lücke 1."""
    width = sum(1 if ch == "." else 3 for ch in pattern) + len(pattern) - 1
    x = (CANVAS - width * unit) / 2
    for ch in pattern:
        w = unit * (1 if ch == "." else 3)
        draw.rounded_rectangle([x, y, x + w, y + height], radius=height / 2, fill=color)
        x += w + unit


def render() -> Image.Image:
    img = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    m = CANVAS * 0.04
    d.rounded_rectangle([m, m, CANVAS - m, CANVAS - m], radius=CANVAS * 0.18,
                        fill=BACKGROUND, outline=BORDER, width=int(CANVAS * 0.035))
    unit, height = CANVAS * 0.075, CANVAS * 0.13
    _row(d, "-.-.", CANVAS * 0.27, ROW_C, unit, height)
    _row(d, ".--", CANVAS * 0.58, ROW_W, unit, height)
    return img


def main():
    ICO_PATH.parent.mkdir(parents=True, exist_ok=True)
    big = render().resize((256, 256), Image.LANCZOS)
    big.save(ICO_PATH, format="ICO", sizes=[(s, s) for s in SIZES])
    print(f"OK: {ICO_PATH} ({ICO_PATH.stat().st_size} Bytes)")


if __name__ == "__main__":
    main()

# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""Flaggen-PNGs für die Rufzeichen-Knöpfe erzeugen (Dev-Werkzeug, ADR-0021).

    python tools/make_flags.py                     Quelle herunterladen
    python tools/make_flags.py --src PFAD/svg      vorhandene SVGs nehmen

Quelle: hampusborgos/country-flags (Public Domain), SVG je ISO-Code. Die
SVGs rendert ein Headless-Chrome/Edge in eine Rasterseite (ein Aufruf,
6-fach vergrößert), Pillow schneidet aus, verkleinert seitenrichtig auf
höchstens 22x14 px und setzt einen 1-px-Rand: Ergebnis 24x16 px (RGBA,
Flagge zentriert) in cwdecoder/data/flags/<iso>.png – nur für die
ISO-Codes aus cwdecoder/data/dxcc_table.json. Die PNGs werden committet;
zur Laufzeit liest tk.PhotoImage sie direkt (kein Pillow im Programm).
"""
import argparse
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "cwdecoder" / "data"
OUT = DATA / "flags"
SRC_ZIP = "https://github.com/hampusborgos/country-flags/archive/refs/heads/main.zip"
W, H = 24, 16                  # fertiges Bild
INNER_W, INNER_H = W - 2, H - 2
SCALE = 6                      # Render-Vergrößerung
CELL_W, CELL_H = INNER_W * SCALE, INNER_H * SCALE
COLS = 16
BORDER = (40, 40, 40, 255)
BROWSERS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    "google-chrome", "chromium", "chromium-browser", "microsoft-edge",
]


def wanted_isos():
    table = json.loads((DATA / "dxcc_table.json").read_text(encoding="utf-8"))
    return sorted({v["iso"] for v in table.values() if v.get("iso")})


def find_browser(explicit=None):
    for cand in ([explicit] if explicit else BROWSERS):
        path = shutil.which(cand) or (cand if os.path.isfile(cand) else None)
        if path:
            return path
    raise SystemExit("Kein Chrome/Edge gefunden (--browser angeben)")


def download_svgs(tmp: Path) -> Path:
    req = urllib.request.Request(SRC_ZIP, headers={"User-Agent": "cw-decoder-make-flags"})
    with urllib.request.urlopen(req, timeout=120) as r:
        zipfile.ZipFile(io.BytesIO(r.read())).extractall(tmp)
    return next(tmp.glob("*/svg"))


def render_sheet(browser, svg_dir: Path, isos, tmp: Path) -> Image.Image:
    rows = (len(isos) + COLS - 1) // COLS
    cells = "".join(
        f'<div><img src="{(svg_dir / (iso + ".svg")).as_uri()}"></div>' for iso in isos)
    html = (
        "<!doctype html><html><head><style>"
        "html,body{margin:0;padding:0;background:transparent}"
        f"body{{display:grid;grid-template-columns:repeat({COLS},{CELL_W}px);"
        f"grid-auto-rows:{CELL_H}px}}"
        "div{display:flex;align-items:center;justify-content:center;overflow:hidden}"
        "img{max-width:100%;max-height:100%;object-fit:contain}"
        "</style></head><body>" + cells + "</body></html>")
    page = tmp / "sheet.html"
    page.write_text(html, encoding="utf-8")
    shot = tmp / "sheet.png"
    subprocess.run([
        browser, "--headless=new", "--disable-gpu", "--hide-scrollbars",
        "--force-device-scale-factor=1", "--default-background-color=00000000",
        "--allow-file-access-from-files",
        f"--window-size={COLS * CELL_W},{rows * CELL_H}", f"--screenshot={shot}",
        page.as_uri()], check=True, capture_output=True, timeout=120)
    return Image.open(shot).convert("RGBA")


def make_flag(cell: Image.Image) -> Image.Image:
    box = cell.getchannel("A").getbbox()
    if box is None:
        raise ValueError("leere Flagge")
    flag = cell.crop(box)
    fw, fh = flag.size
    s = min(INNER_W / fw, INNER_H / fh)
    w, h = max(1, round(fw * s)), max(1, round(fh * s))
    flag = flag.resize((w, h), Image.LANCZOS)
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    x, y = (W - w) // 2, (H - h) // 2
    ImageDraw.Draw(out).rectangle([x - 1, y - 1, x + w, y + h], outline=BORDER)
    out.alpha_composite(flag, (x, y))
    return out


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--src", help="Ordner mit <iso>.svg (Standard: herunterladen)")
    p.add_argument("--browser", help="Pfad zu Chrome/Edge/Chromium")
    a = p.parse_args(argv)
    isos = wanted_isos()
    browser = find_browser(a.browser)
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        svg_dir = Path(a.src) if a.src else download_svgs(tmp)
        missing = [i for i in isos if not (svg_dir / f"{i}.svg").is_file()]
        if missing:
            raise SystemExit(f"SVG fehlt für: {', '.join(missing)}")
        sheet = render_sheet(browser, svg_dir, isos, tmp)
        OUT.mkdir(parents=True, exist_ok=True)
        for old in OUT.glob("*.png"):
            old.unlink()
        total = 0
        for n, iso in enumerate(isos):
            x, y = (n % COLS) * CELL_W, (n // COLS) * CELL_H
            img = make_flag(sheet.crop((x, y, x + CELL_W, y + CELL_H)))
            path = OUT / f"{iso}.png"
            img.save(path, optimize=True)
            total += path.stat().st_size
    print(f"{len(isos)} Flaggen nach {OUT} geschrieben, zusammen {total / 1024:.0f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())

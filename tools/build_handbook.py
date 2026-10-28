# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""Handbuch als PDF bauen (Dev-/Build-Werkzeug, #24, ADR-0027).

    python tools/build_handbook.py                  -> dist/CW-Decoder-Handbuch.pdf
    python tools/build_handbook.py --version 0.1.0-beta17 --out x.pdf

Quelle: docs/handbuch/handbuch.html (Gestaltung und Text der Desktop-
Session), Bilder in docs/handbuch/img/ (tools/make_docs_images.py),
Schriften in docs/handbuch/fonts/. Gedruckt mit Chromium über Playwright
(nur Build-Abhängigkeit: pip install playwright pypdf; python -m
playwright install chromium). Titelseite ohne Fußzeile, alle anderen
Seiten mit „CW Decoder · Handbuch“ und Seitenzahl.

Prüfung danach (Abbruch mit Fehler): Kapitel 1–3 und 5–9 je genau eine
Seite, Kapitel 4 höchstens zwei – sonst steht irgendwo ein Kasten oder
eine Überschrift allein auf einer Seite. Dann Bilder per max-height
nachjustieren, nicht den Text kürzen.
"""
import argparse
import base64
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "docs" / "handbuch" / "handbuch.html"
FONT = ROOT / "docs" / "handbuch" / "fonts" / "InterVariable.woff2"
OUT_DEFAULT = ROOT / "dist" / "CW-Decoder-Handbuch.pdf"
BUILD_HTML = SRC.with_name("_build.html")       # neben der Vorlage: relative Pfade stimmen

CHAPTERS = ("Worum es geht", "Installieren und aktuell halten", "Das Funkgerät anschließen",
            "Das Fenster auf einen Blick", "Rufzeichen", "Nochmal hören und Stellen sichern",
            "Zusammen mit N1MM Logger+", "Einstellungen", "Wenn etwas komisch aussieht")
MAX_PAGES = {4: 2}                              # sonst je eine Seite


def version_strings(version=None):
    """("0.1.0", " (Beta 17)") aus der Version des Programms bzw. --version."""
    if version is None:
        sys.path.insert(0, str(ROOT))
        from cwdecoder.__version__ import CHANNEL, __version__
        version = __version__ if CHANNEL != "beta" or "beta" in __version__ else \
            __version__ + "-beta"
    m = re.match(r"^v?(\d+\.\d+\.\d+)(?:-beta(\d*))?$", version)
    if not m:
        raise SystemExit(f"Version nicht erkannt: {version!r}")
    base, beta = m.group(1), m.group(2)
    if beta is None:
        return base, ""
    return base, f" (Beta {beta})" if beta else " (Beta)"


def render_html(version=None) -> str:
    base, channel = version_strings(version)
    html = SRC.read_text(encoding="utf-8")
    for key in ("{{VERSION}}", "{{CHANNEL}}"):
        if key not in html:
            raise SystemExit(f"Platzhalter {key} fehlt in {SRC.name}")
    return html.replace("{{VERSION}}", base).replace("{{CHANNEL}}", channel)


def footer_template() -> str:
    font = base64.b64encode(FONT.read_bytes()).decode("ascii")
    return ("<style>@font-face{font-family:F;src:url(data:font/woff2;base64,"
            f"{font}) format('woff2');font-weight:100 900}}</style>"
            "<div style=\"font-family:F;font-size:8pt;color:#4a5868;width:100%;"
            "margin:0 20mm;display:flex;justify-content:space-between\">"
            "<span>CW Decoder · Handbuch</span><span class=\"pageNumber\"></span></div>")


def print_pdfs(html: str, tmpdir: Path):
    """(PDF mit Fußzeile, PDF nur Titelseite) als Pfade."""
    from playwright.sync_api import sync_playwright
    BUILD_HTML.write_text(html, encoding="utf-8")
    full, cover = tmpdir / "full.pdf", tmpdir / "cover.pdf"
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(BUILD_HTML.as_uri(), wait_until="networkidle")
            page.evaluate("document.fonts.ready")
            missing = page.evaluate(
                "[...document.images].filter(i => !i.complete || !i.naturalWidth)"
                ".map(i => i.getAttribute('src'))")
            if missing:
                raise SystemExit(f"Bilder fehlen: {missing}")
            page.pdf(path=str(full), format="A4", print_background=True,
                     prefer_css_page_size=True, display_header_footer=True,
                     header_template="<span></span>", footer_template=footer_template())
            page.add_style_tag(content="body > :not(.cover) { display: none !important; }")
            page.pdf(path=str(cover), format="A4", print_background=True,
                     prefer_css_page_size=True, page_ranges="1")
            browser.close()
    finally:
        BUILD_HTML.unlink(missing_ok=True)
    return full, cover


def merge(full: Path, cover: Path, out: Path):
    from pypdf import PdfReader, PdfWriter
    w = PdfWriter()
    w.add_page(PdfReader(str(cover)).pages[0])
    for pg in PdfReader(str(full)).pages[1:]:
        w.add_page(pg)
    w.add_metadata({"/Title": "CW Decoder – Handbuch", "/Author": "DF1DS"})
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "wb") as f:
        w.write(f)


def chapter_pages(pdf: Path):
    """{Kapitel: Seitenzahl}, Kapitel erkannt an „<Nr><Titel>“ oben auf der Seite."""
    from pypdf import PdfReader
    pages = [p.extract_text() or "" for p in PdfReader(str(pdf)).pages]
    starts = {}
    for nr, title in enumerate(CHAPTERS, 1):
        pat = re.compile(rf"^\s*{nr}\s*{re.escape(title)}", re.M)
        for i, text in enumerate(pages):
            if i >= 2 and pat.search(text[:200]):
                starts[nr] = i
                break
        else:
            raise SystemExit(f"Kapitel {nr} „{title}“ nicht gefunden")
    order = sorted(starts.items(), key=lambda kv: kv[1])
    counts = {}
    for k, (nr, first) in enumerate(order):
        nxt = order[k + 1][1] if k + 1 < len(order) else len(pages)
        counts[nr] = nxt - first
    return counts, len(pages)


def check(pdf: Path):
    counts, total = chapter_pages(pdf)
    bad = {nr: n for nr, n in counts.items() if not 1 <= n <= MAX_PAGES.get(nr, 1)}
    for nr in sorted(counts):
        print(f"  Kapitel {nr}: {counts[nr]} Seite(n)")
    if bad:
        raise SystemExit(f"Seitenprüfung: Kapitel zu lang {bad} (verwaiste Kästen/Überschriften?)")
    return total


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--version", help="z. B. 0.1.0 oder 0.1.0-beta17 (Standard: Programmversion)")
    p.add_argument("--out", default=str(OUT_DEFAULT))
    a = p.parse_args(argv)
    import tempfile
    out = Path(a.out)
    with tempfile.TemporaryDirectory() as tmp:
        full, cover = print_pdfs(render_html(a.version), Path(tmp))
        merge(full, cover, out)
    total = check(out)
    print(f"{out}: {total} Seiten, {out.stat().st_size // 1024} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())

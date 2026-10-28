# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""Hilfe → Handbuch: welches Handbuch geöffnet wird (#24, ADR-0027).

Reihenfolge:
1. installiert: `CW-Decoder-Handbuch.pdf` neben `CWDecoder.exe` (legt der
   Installer dorthin) – passt immer zur laufenden Version;
2. installiert, Datei fehlt: das PDF am GitHub-Release der laufenden
   Version (`…/releases/download/v0.1.0-beta17/CW-Decoder-Handbuch-v0.1.0-beta17.pdf`);
3. aus dem Quelltext: das gebaute `dist/CW-Decoder-Handbuch.pdf`, sonst die
   HTML-Vorlage `docs/handbuch/handbuch.html` (zeigt dieselben Inhalte im
   Browser; ein Quelltext-Stand hat keinen Release-Tag).

Kein tk; manual_target() ist direkt testbar.
"""
import os
import sys
import webbrowser
from pathlib import Path

from .__version__ import REPO_URL, __version__

PDF_NAME = "CW-Decoder-Handbuch.pdf"
ROOT = Path(__file__).resolve().parent.parent


def release_tag(version: str = __version__) -> str:
    """"0.1.0" -> "v0.1.0", "0.1.0-beta17" -> "v0.1.0-beta17"."""
    return version if version.startswith("v") else f"v{version}"


def release_pdf_url(version: str = __version__) -> str:
    tag = release_tag(version)
    return f"{REPO_URL}/releases/download/{tag}/CW-Decoder-Handbuch-{tag}.pdf"


def manual_target(frozen=None, exe=None, root=None, version: str = __version__):
    """("file", Pfad) oder ("url", Adresse)."""
    frozen = getattr(sys, "frozen", False) if frozen is None else frozen
    if frozen:
        pdf = Path(exe or sys.executable).resolve().parent / PDF_NAME
        if pdf.is_file():
            return "file", pdf
        return "url", release_pdf_url(version)
    root = Path(root) if root is not None else ROOT
    built = root / "dist" / PDF_NAME
    if built.is_file():
        return "file", built
    return "file", root / "docs" / "handbuch" / "handbuch.html"


def open_manual() -> str:
    """Handbuch mit dem Standardprogramm bzw. im Browser öffnen; liefert,
    was geöffnet wurde. Wirft OSError, wenn Windows die Datei nicht öffnen
    kann (kein PDF-Programm)."""
    kind, target = manual_target()
    if kind == "url":
        webbrowser.open(target)
        return target
    if sys.platform == "win32":
        os.startfile(str(target))          # noqa: S606 - Standardprogramm für .pdf/.html
    else:
        webbrowser.open(Path(target).as_uri())
    return str(target)

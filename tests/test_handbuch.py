# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""Pflege-Regeln für Handbuch und Doku (#24, ADR-0027).

(a) In Handbuch, README, docs/N1MM.md und docs/VERGLEICH.md stehen nur
    Beispiel-Rufzeichen (DF1DS, DF1DSE, …ABC), keine echten fremden.
(b) Jeder im Handbuch zitierte Bedientext existiert noch im Code.
(c) Jeder Config-Schlüssel hat eine Beschreibung in config.DESCRIPTIONS.
Dazu: Bilder, Schriften und Platzhalter der Vorlage; Ziel von Hilfe → Handbuch.
"""
import re
from pathlib import Path

import pytest

from cwdecoder import config, manual
from cwdecoder.callsign import looks_like_call

ROOT = Path(__file__).resolve().parent.parent
HTML = ROOT / "docs" / "handbuch" / "handbuch.html"
DOCS = [HTML, ROOT / "README.md", ROOT / "docs" / "N1MM.md", ROOT / "docs" / "VERGLEICH.md"]

# erlaubte Wörter in Rufzeichenform: Beispiele und Namen, die keine
# Rufzeichen von Stationen in den Aufnahmen sind
EXAMPLE_RE = re.compile(r"^(DF1DS|DF1DSE|[A-Z0-9]{1,3}[0-9]ABC)$")
ALLOWED = {
    "N1MM", "N1MMS",    # Programmname N1MM Logger+ (auch „N1MMs CW Reader“)
    "AD1C",     # Autor von cty.dat (Quellenangabe)
    "DL1A",     # Bruchstück des Beispiels „DL1A B C“
}

# Bedientexte im Handbuch stehen als <span class="ui">…</span> (Menüpfade mit
# „→“); diese stammen aus Windows bzw. N1MM, nicht aus dem CW Decoder
EXTERNAL_UI = {"Enable", "Path to Fldigi", "Save", "Trotzdem ausführen",
               "Weitere Informationen", "Window", "CW Reader"}


def _labels():
    from cwdecoder import gui, gui_n1mm, gui_ring, gui_update
    out = set()
    for mod in (gui, gui_n1mm, gui_ring, gui_update):
        out |= {v for k, v in vars(mod).items() if k.startswith("_LBL_") and isinstance(v, str)}
    return out


def visible_text(text: str) -> str:
    """Ohne <style> und HTML-Tags (Farbwerte wie 9aa3ad sind keine Wörter)."""
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.S)
    return re.sub(r"<[^>]+>", " ", text)


def foreign_calls(text: str):
    words = set(re.findall(r"[A-Za-z0-9/]+", visible_text(text)))
    return sorted(w for w in words
                  if any(c.isdigit() for c in w) and looks_like_call(w.upper())
                  and not EXAMPLE_RE.match(w.upper()) and w.upper() not in ALLOWED)


@pytest.mark.parametrize("path", DOCS, ids=lambda p: p.name)
def test_nur_beispiel_rufzeichen(path):
    bad = foreign_calls(path.read_text(encoding="utf-8"))
    assert not bad, f"{path.name}: echte Rufzeichen? {bad} (Regel #24: nur DF1DS oder …ABC)"


def test_pruefung_findet_echte_rufzeichen():
    assert foreign_calls("CQ DE OY1CT und oz1hgt, DL1ABC, DF1DS, N1MM") == ["OY1CT", "oz1hgt"]


def quoted_ui(html: str):
    parts = []
    for span in re.findall(r'<span class="ui">([^<]*)</span>', html):
        parts += [p.strip() for p in span.split("→")]
    return sorted(set(parts) - EXTERNAL_UI)


def test_zitierte_beschriftungen_existieren():
    labels = _labels()
    quoted = quoted_ui(HTML.read_text(encoding="utf-8"))
    assert {"Übergabe…", "N1MM-Anbindung", "Alle löschen", "Puffer und Nochmal hören…",
            "Ton automatisch suchen", "Tempo"} <= set(quoted)
    missing = [t for t in quoted if not any(lbl == t or lbl.startswith(t + " ") for lbl in labels)]
    assert not missing, f"im Handbuch zitiert, im Code nicht (mehr) vorhanden: {missing}"


def test_jeder_config_schluessel_beschrieben():
    assert set(config.DESCRIPTIONS) == set(config.DEFAULTS)
    assert all(isinstance(v, str) and len(v) > 10 for v in config.DESCRIPTIONS.values())


def test_vorlage_bilder_schriften_platzhalter():
    html = HTML.read_text(encoding="utf-8")
    for key in ("{{VERSION}}", "{{CHANNEL}}"):
        assert key in html
    srcs = re.findall(r'src="([^"]+)"', html) + re.findall(r'url\("([^"]+)"\)', html)
    assert len([s for s in srcs if s.startswith("img/")]) >= 6
    for s in srcs:
        assert (HTML.parent / s).is_file(), s
    for lic in ("Inter-LICENSE.txt", "DejaVu-LICENSE.txt"):
        assert (HTML.parent / "fonts" / lic).is_file()


def test_versionstext_der_titelseite():
    import sys
    sys.path.insert(0, str(ROOT / "tools"))
    import build_handbook
    assert build_handbook.version_strings("0.1.0") == ("0.1.0", "")
    assert build_handbook.version_strings("0.1.0-beta17") == ("0.1.0", " (Beta 17)")
    assert build_handbook.version_strings("v1.2.3") == ("1.2.3", "")
    html = build_handbook.render_html("0.1.0-beta17")
    assert "Version <b>0.1.0</b> (Beta 17)" in html and "{{" not in html


# -- Hilfe → Handbuch ---------------------------------------------------------
def test_handbuch_installiert(tmp_path):
    exe = tmp_path / "CWDecoder.exe"
    (tmp_path / manual.PDF_NAME).write_bytes(b"%PDF")
    assert manual.manual_target(frozen=True, exe=exe) == ("file", tmp_path / manual.PDF_NAME)


@pytest.mark.parametrize("version,tag", [("0.1.0", "v0.1.0"),
                                         ("0.1.0-beta17", "v0.1.0-beta17")])
def test_handbuch_fehlt_release_url(tmp_path, version, tag):
    kind, url = manual.manual_target(frozen=True, exe=tmp_path / "CWDecoder.exe",
                                     version=version)
    assert kind == "url"
    assert url == ("https://github.com/kainomatic/cw-decoder/releases/download/"
                   f"{tag}/CW-Decoder-Handbuch-{tag}.pdf")


def test_handbuch_aus_dem_quelltext(tmp_path):
    (tmp_path / "docs" / "handbuch").mkdir(parents=True)
    assert manual.manual_target(frozen=False, root=tmp_path) == \
        ("file", tmp_path / "docs" / "handbuch" / "handbuch.html")
    (tmp_path / "dist").mkdir()
    (tmp_path / "dist" / manual.PDF_NAME).write_bytes(b"%PDF")
    assert manual.manual_target(frozen=False, root=tmp_path) == \
        ("file", tmp_path / "dist" / manual.PDF_NAME)


def test_release_und_installer_liefern_handbuch():
    wf = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    assert "tools/build_handbook.py" in wf and "CW-Decoder-Handbuch-${{ github.ref_name }}.pdf" in wf
    for iss in ("cwdecoder.iss", "cwdecoder-beta.iss"):
        text = (ROOT / "installer" / iss).read_text(encoding="utf-8-sig")
        assert 'Source: "..\\dist\\CW-Decoder-Handbuch.pdf"' in text, iss

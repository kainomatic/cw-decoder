# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""Welche Tests die CI für eine Änderung laufen lässt (#28, ADR-0029).

Jede geänderte Datei fällt in genau eine Gruppe (erste passende Regel):

  alles      Workflows, Abhängigkeiten, pytest-Konfiguration -> voller Lauf
  handbuch   README, docs/N1MM.md, docs/VERGLEICH.md, docs/handbuch/**
             -> tests/test_handbuch.py
  doku       übrige *.md, docs/adr/** -> kein Lauf
  decoder    Decoder-Kern, Testdaten, Matrix -> schnelle Tests plus -m decoder
  gui        Oberfläche -> schnelle Tests plus -m gui
  code       alles andere -> schnelle Tests (-m "not decoder and not gui")

Unbekannte Dateien zählen als Code (lieber zu viel testen als zu wenig).
Vor jedem Tag läuft ohnehin alles (release.yml).

Aufruf in der CI:   python tools/ci_select.py --git --github-output "$GITHUB_OUTPUT"
Probe von Hand:     python tools/ci_select.py cwdecoder/dsp.py README.md
"""
from __future__ import annotations

import argparse
import fnmatch
import os
import subprocess
import sys

# fnmatch: "*" passt auch über "/" hinweg ("*.md" trifft jede .md-Datei).
ALL = (
    ".github/workflows/*",
    "requirements*.txt",
    "pytest.ini",
    "pyproject.toml",
    "tests/conftest.py",
    "tools/ci_select.py",
)
HANDBOOK = (
    "README.md",
    "docs/N1MM.md",
    "docs/VERGLEICH.md",
    "docs/handbuch/*",
)
DOCS = (
    "*.md",
    "docs/adr/*",
)
DECODER = (
    # Signalkette (CLAUDE.md "Signalkette")
    "cwdecoder/dsp.py",
    "cwdecoder/timing.py",
    "cwdecoder/decoder.py",
    "cwdecoder/morse.py",
    "cwdecoder/gen.py",
    # weitere Module und Daten, die die decoder-Tests benutzen
    # (tests/test_ci_select.py prüft die Importe)
    "cwdecoder/decode_wav.py",
    "cwdecoder/testtext.py",
    "cwdecoder/callsign.py",
    "cwdecoder/scp.py",
    "cwdecoder/segment.py",
    "cwdecoder/data/master.scp",
    "cwdecoder/data/qso_words.txt",
    "testdata/*",
    "tests/run_matrix.py",
    "tests/real_baseline.json",
    # die decoder-Tests selbst
    "tests/test_matrix.py",
    "tests/test_real.py",
    "tests/test_blockgroesse.py",
    "tests/test_confidence.py",
    "tests/test_erstes_zeichen.py",
)
GUI = (
    "cwdecoder/gui*.py",
    "cwdecoder/engine_request.py",
    "cwdecoder/live.py",
    "cwdecoder/n1mm.py",
    "cwdecoder/fldigi_rpc.py",
    "cwdecoder/replay.py",
    "cwdecoder/ringbuffer.py",
    "tests/gui_smoke.py",
    "tests/test_gui*.py",
)

RULES = (("alles", ALL), ("handbuch", HANDBOOK), ("doku", DOCS),
         ("decoder", DECODER), ("gui", GUI))

FAST = "not decoder and not gui"


def classify(path: str) -> str:
    """Gruppe einer Datei (Pfad relativ zum Repo, mit '/')."""
    p = path.replace("\\", "/").removeprefix("./")
    for group, patterns in RULES:
        if any(fnmatch.fnmatchcase(p, pat) for pat in patterns):
            return group
    return "code"


def select(files, full: bool = False) -> dict:
    """Entscheidung für eine Liste geänderter Dateien.

    Liefert {"mode": "full"|"none"|"handbook"|"tests", "args": str,
    "groups": {Datei: Gruppe}}; "args" sind die pytest-Argumente.
    """
    groups = {f: classify(f) for f in files}
    found = set(groups.values())
    if full or "alles" in found:
        return {"mode": "full", "args": "", "groups": groups}
    if not found - {"doku"}:
        return {"mode": "none", "args": "", "groups": groups}
    if not found - {"doku", "handbuch"}:
        return {"mode": "handbook", "args": "tests/test_handbuch.py", "groups": groups}
    with_decoder = "decoder" in found
    with_gui = "gui" in found
    if with_decoder and with_gui:
        return {"mode": "full", "args": "", "groups": groups}
    if with_decoder:
        expr = "not gui"
    elif with_gui:
        expr = "not decoder"
    else:
        expr = FAST
    return {"mode": "tests", "args": f'-m "{expr}"', "groups": groups}


def _git(*args) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True,
                          text=True).stdout


def changed_files_from_git(before: str, after: str) -> list[str] | None:
    """Geänderte Dateien zwischen zwei Commits; None, wenn nicht bestimmbar
    (erster Push, Force-Push auf fremde Basis) -> voller Lauf."""
    if not before or set(before) == {"0"}:
        return None
    try:
        _git("cat-file", "-e", f"{before}^{{commit}}")
        out = _git("diff", "--name-only", "--no-renames", before, after)
    except (subprocess.CalledProcessError, OSError):
        return None
    return [ln for ln in out.splitlines() if ln.strip()]


def describe(result: dict) -> str:
    mode = result["mode"]
    head = {
        "full": "voller Lauf (alle Marker)",
        "none": "kein Lauf (nur Doku)",
        "handbook": "nur tests/test_handbuch.py",
        "tests": f"pytest {result['args']}",
    }[mode]
    lines = [f"Auswahl: {head}"]
    for f, g in sorted(result["groups"].items()):
        lines.append(f"  {g:9s} {f}")
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("files", nargs="*", help="geänderte Dateien (Probe von Hand)")
    ap.add_argument("--git", action="store_true",
                    help="Dateien per git diff aus CI_BEFORE..CI_AFTER bestimmen")
    ap.add_argument("--full", action="store_true", help="immer voller Lauf")
    ap.add_argument("--github-output", help="Ergebnis an diese Datei anhängen")
    a = ap.parse_args(argv)

    files = list(a.files)
    full = a.full
    if a.git:
        got = changed_files_from_git(os.environ.get("CI_BEFORE", ""),
                                     os.environ.get("CI_AFTER", "HEAD"))
        if got is None:
            full = True
        else:
            files = got
    result = select(files, full=full)
    text = describe(result)
    print(text)
    if a.github_output:
        with open(a.github_output, "a", encoding="utf-8") as fh:
            fh.write(f"run={'false' if result['mode'] == 'none' else 'true'}\n")
            fh.write(f"mode={result['mode']}\n")
            fh.write(f"args={result['args']}\n")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write("```\n" + text + "\n```\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

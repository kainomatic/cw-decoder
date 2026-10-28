# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""Testauswahl der CI nach geänderten Dateien (#28, ADR-0029)."""
import ast
import os
import subprocess
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import ci_select  # noqa: E402

FAST = '-m "not decoder and not gui"'


@pytest.mark.parametrize("files, mode, args", [
    # reine Doku -> kein Lauf
    (["ROADMAP.md"], "none", ""),
    (["CHANGELOG.md", "docs/adr/ADR-0029-x.md", "docs/adr/README.md"], "none", ""),
    (["docs/BUILD.md", "CLAUDE.md"], "none", ""),
    # Handbuch-Doku -> nur test_handbuch
    (["README.md"], "handbook", "tests/test_handbuch.py"),
    (["docs/handbuch/handbuch.html", "docs/handbuch/img/main.png", "ROADMAP.md"],
     "handbook", "tests/test_handbuch.py"),
    (["docs/N1MM.md", "docs/VERGLEICH.md"], "handbook", "tests/test_handbuch.py"),
    # sonstiger Code -> schnelle Tests
    (["cwdecoder/config.py"], "tests", FAST),
    (["tools/release_tools.py", "README.md"], "tests", FAST),
    (["installer/cwdecoder.iss", ".gitignore"], "tests", FAST),
    (["tests/test_scp.py"], "tests", FAST),
    # Decoder -> plus decoder
    (["cwdecoder/dsp.py"], "tests", '-m "not gui"'),
    (["testdata/real/x.wav", "CHANGELOG.md"], "tests", '-m "not gui"'),
    (["tests/real_baseline.json"], "tests", '-m "not gui"'),
    (["cwdecoder/config.py", "cwdecoder/timing.py"], "tests", '-m "not gui"'),
    # GUI -> plus gui
    (["cwdecoder/gui.py"], "tests", '-m "not decoder"'),
    (["cwdecoder/gui_ring.py", "cwdecoder/n1mm.py"], "tests", '-m "not decoder"'),
    (["tests/gui_smoke.py"], "tests", '-m "not decoder"'),
    # Decoder und GUI -> alle Marker
    (["cwdecoder/decoder.py", "cwdecoder/live.py"], "full", ""),
    # Workflow, Abhängigkeiten, pytest-Konfiguration -> alles
    ([".github/workflows/ci.yml"], "full", ""),
    ([".github/workflows/release.yml", "ROADMAP.md"], "full", ""),
    (["requirements-dev.txt"], "full", ""),
    (["pyproject.toml"], "full", ""),
    (["tests/conftest.py"], "full", ""),
    (["tools/ci_select.py"], "full", ""),
    # nichts geändert (z. B. leerer Commit) -> kein Lauf
    ([], "none", ""),
])
def test_auswahl(files, mode, args):
    r = ci_select.select(files)
    assert (r["mode"], r["args"]) == (mode, args), ci_select.describe(r)


def test_volllauf_erzwingen():
    assert ci_select.select(["ROADMAP.md"], full=True)["mode"] == "full"


def test_windows_pfade():
    assert ci_select.classify(r"cwdecoder\dsp.py") == "decoder"
    assert ci_select.classify("./README.md") == "handbuch"


def test_github_output(tmp_path, monkeypatch):
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    out = tmp_path / "out.txt"
    ci_select.main(["cwdecoder/gui.py", "--github-output", str(out)])
    assert out.read_text(encoding="utf-8").splitlines() == [
        "run=true", "mode=tests", 'args=-m "not decoder"']
    out.unlink()
    ci_select.main(["ROADMAP.md", "--github-output", str(out)])
    assert out.read_text(encoding="utf-8").splitlines()[0] == "run=false"


def test_git_ohne_vorgaenger_ist_volllauf():
    assert ci_select.changed_files_from_git("0" * 40, "HEAD") is None
    assert ci_select.changed_files_from_git("", "HEAD") is None
    assert ci_select.changed_files_from_git("f" * 40, "HEAD") is None


def test_git_diff_zwischen_commits(tmp_path):
    def git(*a):
        subprocess.run(["git", *a], cwd=tmp_path, check=True, capture_output=True)
    git("init", "-q")
    git("config", "user.email", "t@example.invalid")
    git("config", "user.name", "t")
    (tmp_path / "a.md").write_text("a", encoding="utf-8")
    git("add", ".")
    git("commit", "-q", "-m", "1")
    first = subprocess.run(["git", "rev-parse", "HEAD"], cwd=tmp_path, check=True,
                           capture_output=True, text=True).stdout.strip()
    (tmp_path / "cwdecoder").mkdir()
    (tmp_path / "cwdecoder" / "dsp.py").write_text("x", encoding="utf-8")
    git("mv", "a.md", "b.md")
    git("add", ".")
    git("commit", "-q", "-m", "2")
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        files = ci_select.changed_files_from_git(first, "HEAD")
    finally:
        os.chdir(cwd)
    assert sorted(files) == ["a.md", "b.md", "cwdecoder/dsp.py"]


# --- versteckte Abhängigkeiten der decoder-Tests --------------------------
# Jedes cwdecoder-Modul, das die decoder-Tests (auch in Funktionen) importieren,
# muss in der Gruppe "decoder" stehen. Sonst testet die CI eine Änderung daran
# nur mit den schnellen Tests. Ausnahmen mit Begründung:
NOT_DECODER = {
    "cwdecoder/__init__.py": "Paket, enthält utf8_console (nur Konsolenausgabe)",
    "cwdecoder/paths.py": "nur Ablageorte; data_path hat eigene schnelle Tests",
    # test_confidence.py importiert live (für einen schnellen Test); live.py
    # gehört zur Gruppe gui, die decoder-Tests darin benutzen es nicht.
    "cwdecoder/live.py": "nur im schnellen Test von test_confidence.py",
}
DECODER_TESTS = ("tests/test_matrix.py", "tests/test_real.py",
                 "tests/test_blockgroesse.py", "tests/test_confidence.py",
                 "tests/test_erstes_zeichen.py", "tests/run_matrix.py")


def _imports(path):
    """cwdecoder-Module (als Pfad), die eine Datei irgendwo importiert."""
    tree = ast.parse(open(path, encoding="utf-8").read())
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            # relative Importe gibt es nur innerhalb des Pakets cwdecoder
            if node.level:
                base = "cwdecoder" + (f".{node.module}" if node.module else "")
            else:
                base = node.module or ""
            names.add(base)
            names |= {f"{base}.{a.name}" for a in node.names}
    out = set()
    for n in names:
        if n == "cwdecoder" or n.startswith("cwdecoder."):
            rel = n.replace(".", "/")
            if os.path.isfile(os.path.join(ROOT, rel + ".py")):
                out.add(rel + ".py")
            elif os.path.isdir(os.path.join(ROOT, rel)):
                out.add(rel + "/__init__.py")
    return out


def test_decoder_gruppe_deckt_importe_ab():
    seen, todo = set(), list(DECODER_TESTS)
    while todo:
        f = todo.pop()
        if f in seen:
            continue
        seen.add(f)
        if f in NOT_DECODER:
            continue
        todo.extend(_imports(os.path.join(ROOT, f)))
    modules = {f for f in seen if f.startswith("cwdecoder/")}
    assert "cwdecoder/decoder.py" in modules and "cwdecoder/callsign.py" in modules
    missing = sorted(m for m in modules
                     if m not in NOT_DECODER and ci_select.classify(m) != "decoder")
    assert not missing, f"decoder-Tests benutzen, aber nicht in Gruppe decoder: {missing}"
    for f in DECODER_TESTS:
        assert ci_select.classify(f) == "decoder", f


def test_decoder_marker_nur_in_decoder_dateien():
    """Wer einen Test mit @pytest.mark.decoder markiert, muss die Datei in
    ci_select.DECODER eintragen (sonst läuft er bei Änderungen daran nicht)."""
    tests_dir = os.path.join(ROOT, "tests")
    for name in sorted(os.listdir(tests_dir)):
        if not name.endswith(".py") or name == os.path.basename(__file__):
            continue
        src = open(os.path.join(tests_dir, name), encoding="utf-8").read()
        if "mark.decoder" in src:
            assert ci_select.classify(f"tests/{name}") == "decoder", name
        if "mark.gui" in src or "requires_display" in src:
            assert ci_select.classify(f"tests/{name}") in ("gui", "decoder", "alles"), name


# --- Workflows -------------------------------------------------------------
def _workflow(name):
    return open(os.path.join(ROOT, ".github", "workflows", name), encoding="utf-8").read()


def test_release_testet_vor_dem_bundle():
    """release.yml: erster Job ist der Volllauf (ci.yml mit full: true),
    Bundle und Installer erst danach."""
    s = _workflow("release.yml")
    jobs = s[s.index("\njobs:"):]
    assert jobs.index("  tests:") < jobs.index("  release:")
    tests = jobs[jobs.index("  tests:"):jobs.index("  release:")]
    assert "uses: ./.github/workflows/ci.yml" in tests and "full: true" in tests
    release = jobs[jobs.index("  release:"):]
    assert release.index("needs: tests") < release.index("steps:")


def test_ci_ruft_die_auswahl_auf():
    s = _workflow("ci.yml")
    assert "workflow_dispatch:" in s and "workflow_call:" in s
    assert "tools/ci_select.py --git" in s
    assert "needs.changes.outputs.run == 'true'" in s
    assert "windows-latest" in s and "ubuntu-latest" in s
    # Trigger-Filter und Skript sind sich bei der Doku einig
    for pat in ("!**.md", "!docs/adr/**", "README.md", "docs/N1MM.md",
                "docs/VERGLEICH.md", "docs/handbuch/**"):
        assert f'- "{pat}"' in s, pat

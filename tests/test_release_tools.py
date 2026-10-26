# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""Release-Hilfen (tools/release_tools.py, ADR-0014)."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import release_tools as rt  # noqa: E402

VERSION_PY = '''"""Doku."""

__version__ = "0.1.0"
CHANNEL = "stable"

APP_NAME = "CW Decoder"
'''

CHANGELOG = """# Changelog

Einleitung.

## [Unreleased]

### Added
- Neu A

### Fixed
- Fehler B

## [0.1.0] - 2026-10-30

### Added
- Erstes Release

## [0.0.9] - 2026-01-01

- Alt
"""


@pytest.mark.parametrize("tag, base, channel, full", [
    ("v0.1.0", "0.1.0", "stable", "0.1.0"),
    ("v0.1.0-beta1", "0.1.0", "beta", "0.1.0-beta1"),
    ("v1.20.3-beta12", "1.20.3", "beta", "1.20.3-beta12"),
])
def test_parse_tag(tag, base, channel, full):
    info = rt.parse_tag(tag)
    assert (info.base, info.channel, info.full_version) == (base, channel, full)


@pytest.mark.parametrize("tag", ["0.1.0", "v0.1", "v0.1.0-rc1", "v0.1.0-beta", "v0.1.0-beta0",
                                 "v0.1.0-beta1x", "", "refs/tags/v0.1.0"])
def test_parse_tag_rejects(tag):
    with pytest.raises(rt.ReleaseError):
        rt.parse_tag(tag)


def test_setup_file_names():
    assert rt.parse_tag("v0.2.0").setup_file.endswith("CWDecoder-Setup-v0.2.0.exe")
    beta = rt.parse_tag("v0.2.0-beta3")
    assert beta.setup_file.endswith("CWDecoder-Beta-Setup-v0.2.0.exe")   # ohne -betaN
    assert beta.iss_file.endswith("cwdecoder-beta.iss")
    assert "IS_PRERELEASE=true" in rt.env_lines(beta)
    assert "APP_VERSION=0.2.0" in rt.env_lines(beta)


def test_version_sync_ok():
    rt.check_version_sync(rt.parse_tag("v0.1.0-beta2"), VERSION_PY)
    rt.check_version_sync(rt.parse_tag("v0.1.0"), VERSION_PY)


def test_version_sync_mismatch():
    with pytest.raises(rt.ReleaseError, match="Versions-Mismatch"):
        rt.check_version_sync(rt.parse_tag("v0.2.0-beta1"), VERSION_PY)


def test_version_sync_requires_stable_channel_in_repo():
    with pytest.raises(rt.ReleaseError, match="CHANNEL"):
        rt.check_version_sync(rt.parse_tag("v0.1.0"), VERSION_PY.replace('"stable"', '"beta"'))


def test_patch_for_beta():
    out = rt.patch_for_beta(VERSION_PY, rt.parse_tag("v0.1.0-beta2"))
    assert '__version__ = "0.1.0-beta2"' in out and 'CHANNEL = "beta"' in out
    assert 'APP_NAME = "CW Decoder"' in out and out.startswith('"""Doku."""')


def test_patch_real_version_file():
    text = rt.VERSION_FILE.read_text(encoding="utf-8")
    info = rt.parse_tag(f"v{rt.read_version(text)}-beta1")
    rt.check_version_sync(info, text)
    ns = {}
    exec(rt.patch_for_beta(text, info), ns)   # noqa: S102 - eigene Datei
    assert ns["CHANNEL"] == "beta" and ns["__version__"] == info.full_version


def test_notes_beta_from_unreleased():
    notes = rt.extract_notes(CHANGELOG, rt.parse_tag("v0.2.0-beta1"))
    assert notes.startswith("### Added") and "Fehler B" in notes
    assert "Erstes Release" not in notes


def test_notes_stable_from_version_section():
    notes = rt.extract_notes(CHANGELOG, rt.parse_tag("v0.1.0"))
    assert notes == "### Added\n- Erstes Release"


def test_notes_last_section():
    assert rt.extract_notes(CHANGELOG, rt.parse_tag("v0.0.9")) == "- Alt"


def test_notes_crlf():
    notes = rt.extract_notes(CHANGELOG.replace("\n", "\r\n"), rt.parse_tag("v0.1.0"))
    assert notes == "### Added\n- Erstes Release"


def test_notes_fallbacks():
    # Stable ohne eigenen Abschnitt -> [Unreleased]
    assert "Neu A" in rt.extract_notes(CHANGELOG, rt.parse_tag("v0.3.0"))
    # nichts brauchbar -> Platzhalter
    empty = "# Changelog\n\n## [Unreleased]\n\n## [0.1.0] - x\n\n- a\n"
    assert rt.extract_notes(empty, rt.parse_tag("v0.2.0-beta1")) == rt.NOTES_PLACEHOLDER
    assert rt.extract_notes("", rt.parse_tag("v0.2.0")) == rt.NOTES_PLACEHOLDER


def test_notes_from_real_changelog():
    text = rt.CHANGELOG.read_text(encoding="utf-8")
    body = rt.release_body(text, rt.parse_tag("v0.1.0-beta1"))
    assert body.startswith("## CW Decoder Beta 0.1.0-beta1")
    assert "### Added" in body and rt.NOTES_PLACEHOLDER not in body


def test_prepare_cli(tmp_path, capsys):
    vf = tmp_path / "__version__.py"
    vf.write_text(VERSION_PY, encoding="utf-8")
    env = tmp_path / "env"
    assert rt.main(["prepare", "--tag", "v0.1.0-beta4", "--version-file", str(vf),
                    "--github-env", str(env)]) == 0
    assert '__version__ = "0.1.0-beta4"' in vf.read_text(encoding="utf-8")
    assert "CHANNEL=beta" in env.read_text(encoding="utf-8").splitlines()
    assert rt.main(["prepare", "--tag", "v9.9.9", "--version-file", str(vf)]) == 1
    assert "::error::" in capsys.readouterr().err


def test_notes_cli(tmp_path):
    cl = tmp_path / "CHANGELOG.md"
    cl.write_text(CHANGELOG, encoding="utf-8")
    out = tmp_path / "notes.md"
    assert rt.main(["notes", "--tag", "v0.1.0", "--changelog", str(cl), "-o", str(out)]) == 0
    assert out.read_text(encoding="utf-8").startswith("## CW Decoder Version 0.1.0")


def test_notes_cli_on_cp1252_console(tmp_path, monkeypatch):
    """Windows-Runner: stdout ist cp1252, die Notes enthalten "→"."""
    import io
    raw = io.BytesIO()
    monkeypatch.setattr(sys, "stdout", io.TextIOWrapper(raw, encoding="cp1252"))
    cl = tmp_path / "CHANGELOG.md"
    cl.write_text("## [Unreleased]\n\n- Hilfe → Nach Updates suchen\n", encoding="utf-8")
    out = tmp_path / "notes.md"
    assert rt.main(["notes", "--tag", "v0.1.0-beta2", "--changelog", str(cl), "-o", str(out)]) == 0
    assert "Hilfe → Nach Updates suchen" in out.read_text(encoding="utf-8")

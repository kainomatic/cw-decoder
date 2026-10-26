# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""Hilfen für den Release-Workflow (.github/workflows/release.yml, ADR-0014).

    python tools/release_tools.py prepare --tag v0.1.0-beta1 [--github-env DATEI]
        Tag prüfen, Versions-Sync gegen cwdecoder/__version__.py, bei Beta
        CHANNEL und __version__ ephemer patchen (kein Commit), Variablen
        CHANNEL, IS_PRERELEASE, APP_VERSION, FULL_VERSION, ISS_FILE,
        SETUP_FILE ausgeben bzw. an GITHUB_ENV anhängen.
    python tools/release_tools.py notes --tag v0.1.0-beta1 -o release_notes.md
        Release-Notes aus CHANGELOG.md: Beta aus [Unreleased], Stable aus
        [X.Y.Z], sonst Rückfall auf [Unreleased], dann Platzhalter.

Die Funktionen sind rein (Text rein, Text raus) und in
tests/test_release_tools.py getestet.
"""
import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERSION_FILE = ROOT / "cwdecoder" / "__version__.py"
CHANGELOG = ROOT / "CHANGELOG.md"

NOTES_PLACEHOLDER = "Die Änderungen stehen in CHANGELOG.md im Repository."

_TAG_RE = re.compile(r"^v(\d+\.\d+\.\d+)(?:-beta([1-9]\d*))?$")
_VERSION_RE = re.compile(r'^__version__\s*=\s*"([^"]*)"', re.M)
_CHANNEL_RE = re.compile(r'^CHANNEL\s*=\s*"([^"]*)"', re.M)


class ReleaseError(ValueError):
    pass


@dataclass(frozen=True)
class TagInfo:
    tag: str
    base: str            # X.Y.Z
    channel: str         # "stable" | "beta"
    full_version: str    # X.Y.Z bzw. X.Y.Z-betaN

    @property
    def prerelease(self) -> bool:
        return self.channel == "beta"

    @property
    def iss_file(self) -> str:
        return "installer\\cwdecoder-beta.iss" if self.prerelease else "installer\\cwdecoder.iss"

    @property
    def setup_file(self) -> str:
        prefix = "CWDecoder-Beta-Setup" if self.prerelease else "CWDecoder-Setup"
        return f"installer\\Output\\{prefix}-v{self.base}.exe"


def parse_tag(tag: str) -> TagInfo:
    m = _TAG_RE.match(tag or "")
    if not m:
        raise ReleaseError(f"Ungültiger Tag {tag!r}: erwartet vX.Y.Z oder vX.Y.Z-betaN")
    base, beta = m.groups()
    if beta:
        return TagInfo(tag, base, "beta", f"{base}-beta{beta}")
    return TagInfo(tag, base, "stable", base)


def read_version(text: str) -> str:
    m = _VERSION_RE.search(text)
    if not m:
        raise ReleaseError("__version__ nicht in cwdecoder/__version__.py gefunden")
    return m.group(1)


def check_version_sync(info: TagInfo, version_text: str) -> None:
    """Basis des Tags muss __version__ entsprechen."""
    src = read_version(version_text)
    if src != info.base:
        raise ReleaseError(
            f"Versions-Mismatch: Tag {info.tag} hat die Basis {info.base}, "
            f"cwdecoder/__version__.py sagt {src}. Lösung: __version__ auf "
            f'"{info.base}" setzen, committen, pushen und einen neuen Tag setzen '
            f"(Beta-Nummern nicht wiederverwenden).")
    m = _CHANNEL_RE.search(version_text)
    if not m or m.group(1) != "stable":
        raise ReleaseError('Im Repo muss CHANNEL = "stable" stehen (Beta patcht der Workflow).')


def patch_for_beta(version_text: str, info: TagInfo) -> str:
    """CHANNEL auf "beta", __version__ auf die volle Tag-Version (nur im Build)."""
    text, n1 = _CHANNEL_RE.subn('CHANNEL = "beta"', version_text, count=1)
    text, n2 = _VERSION_RE.subn(f'__version__ = "{info.full_version}"', text, count=1)
    if n1 != 1 or n2 != 1:
        raise ReleaseError("__version__.py ließ sich nicht patchen")
    return text


def _section(changelog: str, heading: str):
    """Inhalt unter "## [heading]" bis zur nächsten "## [", sonst None."""
    pattern = re.compile(r"^## \[" + re.escape(heading) + r"\][^\n]*\n(.*?)(?=^## \[|\Z)",
                         re.M | re.S)
    m = pattern.search(changelog.replace("\r\n", "\n"))
    return m.group(1).strip() if m else None


def extract_notes(changelog: str, info: TagInfo) -> str:
    primary = "Unreleased" if info.prerelease else info.base
    notes = _section(changelog, primary)
    if not notes:
        notes = _section(changelog, "Unreleased")
    return notes or NOTES_PLACEHOLDER


def release_body(changelog: str, info: TagInfo) -> str:
    kind = "Beta" if info.prerelease else "Version"
    return f"## CW Decoder {kind} {info.full_version}\n\n{extract_notes(changelog, info)}\n"


def env_lines(info: TagInfo) -> list:
    return [
        f"CHANNEL={info.channel}",
        f"IS_PRERELEASE={'true' if info.prerelease else 'false'}",
        f"APP_VERSION={info.base}",
        f"FULL_VERSION={info.full_version}",
        f"ISS_FILE={info.iss_file}",
        f"SETUP_FILE={info.setup_file}",
    ]


def _cmd_prepare(a) -> None:
    info = parse_tag(a.tag)
    version_file = Path(a.version_file)
    text = version_file.read_text(encoding="utf-8")
    check_version_sync(info, text)
    print(f"OK: Tag {info.tag} passt zu __version__ {info.base} (Kanal {info.channel})")
    if info.prerelease:
        version_file.write_text(patch_for_beta(text, info), encoding="utf-8")
        print(f'Beta-Build: CHANNEL = "beta", __version__ = "{info.full_version}" (ohne Commit)')
    lines = env_lines(info)
    if a.github_env:
        with open(a.github_env, "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    print("\n".join(lines))


def _cmd_notes(a) -> None:
    info = parse_tag(a.tag)
    body = release_body(Path(a.changelog).read_text(encoding="utf-8"), info)
    Path(a.out).write_text(body, encoding="utf-8")
    print(body)


def main(argv=None) -> int:
    # Die Konsole der Windows-Runner ist cp1252; Notes enthalten z. B. "→"
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(description="Hilfen für den Release-Workflow")
    sub = p.add_subparsers(dest="cmd", required=True)
    pp = sub.add_parser("prepare")
    pp.add_argument("--tag", required=True)
    pp.add_argument("--version-file", default=str(VERSION_FILE))
    pp.add_argument("--github-env", default=None)
    pn = sub.add_parser("notes")
    pn.add_argument("--tag", required=True)
    pn.add_argument("--changelog", default=str(CHANGELOG))
    pn.add_argument("-o", "--out", default="release_notes.md")
    a = p.parse_args(argv)
    try:
        (_cmd_prepare if a.cmd == "prepare" else _cmd_notes)(a)
    except ReleaseError as e:
        print(f"::error::{e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

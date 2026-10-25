# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""Fehlerbericht auf Anfrage (ADR-0008). Reine Logik, ohne tk testbar.

build_error_report()  Text aus Version, Kanal, Windows-/Python-Version,
                      Audiogerät/Abtastrate und den letzten Logzeilen.
build_issue_url()     vorausgefüllte GitHub-Issue-URL (Titel, Text).
open_in_browser()     URL im Standardbrowser öffnen.
save_report()         Bericht als UTF-8-Textdatei speichern.

Das Programm sendet selbst nichts: Der Nutzer sieht den Bericht vorher,
und das Absenden passiert im Browser durch ihn.
"""
import os
import platform
import re
import sys
import urllib.parse
import webbrowser
from datetime import datetime
from pathlib import Path

from .__version__ import REPO_URL

DEFAULT_LOG_LINES = 200
# GitHub und Browser vertragen keine beliebig langen URLs; darüber wird der
# Logteil im Link gekürzt (der vollständige Bericht lässt sich speichern).
MAX_URL_LEN = 7000

_LOG_START = "--- Letzte {n} Zeilen aus cwdecoder.log ---"
_LOG_END = "--- Ende Log ---"
_TRUNCATED = "[... ältere Logzeilen gekürzt, vollständiger Bericht: „Lokal speichern“ ...]"
_FILTERED = "[Zeile entfernt: mögliche Zugangsdaten]"
_NO_LOG = "(kein Log vorhanden)"
_EMPTY_LOG = "(Log ist leer)"

# Zeilen mit solchen Wörtern fliegen raus; das Programm kennt zwar keine
# Zugangsdaten, aber Logzeilen können Fremdtexte enthalten (z. B. Fehler-
# meldungen mit URLs).
_SECRET_WORDS = ("password", "passwort", "token", "secret", "apikey", "api_key",
                 "credential")
_URL_USERINFO = re.compile(r"(\w+://)[^/@\s]+@")


def windows_version() -> str:
    if sys.platform == "win32":
        release, version, _csd, _ptype = platform.win32_ver()
        edition = platform.win32_edition() if hasattr(platform, "win32_edition") else ""
        return f"Windows {release} {edition} ({version})".replace("  ", " ")
    return f"{platform.system()} {platform.release()}"


def _home_variants():
    homes = {str(Path.home())}
    for var in ("USERPROFILE", "HOME"):
        if os.environ.get(var):
            homes.add(os.environ[var])
    # längste zuerst, damit kein Teilpfad übrig bleibt
    return sorted((h for h in homes if len(h) > 3), key=len, reverse=True)


def sanitize(text: str) -> str:
    """Nutzerordner durch ~ ersetzen, URL-Zugangsdaten und verdächtige
    Zeilen entfernen."""
    for home in _home_variants():
        text = re.sub(re.escape(home), "~", text, flags=re.IGNORECASE)
    out = []
    for line in text.splitlines():
        line = _URL_USERINFO.sub(r"\1[entfernt]@", line)
        if any(w in line.lower() for w in _SECRET_WORDS):
            out.append(_FILTERED)
        else:
            out.append(line)
    return "\n".join(out)


def read_last_lines(log_path, n: int = DEFAULT_LOG_LINES) -> str:
    try:
        text = Path(log_path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return _NO_LOG
    lines = text.splitlines()
    return "\n".join(lines[-n:]) if lines else _EMPTY_LOG


def build_error_report(version: str, channel: str, log_path, audio: str,
                       n_lines: int = DEFAULT_LOG_LINES, now=None) -> str:
    """Bericht als Text. audio: z. B. "3: USB Audio CODEC, 48000 Hz"."""
    now = now or datetime.now()
    log_text = read_last_lines(log_path, n_lines)
    body = (
        "CW Decoder – Fehlerbericht\n"
        "==========================\n"
        f"Erstellt:      {now:%Y-%m-%d %H:%M:%S}\n"
        f"Version:       {version} ({channel})\n"
        f"System:        {windows_version()} ({platform.machine()})\n"
        f"Python:        {platform.python_version()}\n"
        f"Audio:         {audio}\n"
        "\n"
        "Was ist passiert? (bitte ergänzen)\n"
        "\n"
        "\n"
        f"{_LOG_START.format(n=n_lines)}\n"
        f"{log_text}\n"
        f"{_LOG_END}\n"
    )
    return sanitize(body)


def build_issue_url(title: str, body: str, repo_url: str = REPO_URL,
                    max_len: int = MAX_URL_LEN):
    """GitHub-Issue-URL mit title/body. Liefert (url, gekürzt).

    Ist die URL zu lang, werden die ältesten Logzeilen weggelassen."""
    base = f"{repo_url.rstrip('/')}/issues/new?"

    def make(b):
        return base + urllib.parse.urlencode({"title": title, "body": b})

    url = make(body)
    if len(url) <= max_len:
        return url, False
    lines = body.splitlines()
    try:
        start = next(i for i, ln in enumerate(lines) if ln.startswith("--- Letzte"))
    except StopIteration:
        start = None
    if start is not None:
        head, log_lines = lines[:start + 1], lines[start + 1:]
        while log_lines:
            log_lines = log_lines[1:]
            url = make("\n".join(head + [_TRUNCATED] + log_lines))
            if len(url) <= max_len:
                return url, True
    # notfalls nur noch Kopf mit Hinweis
    cut = body
    while len(make(cut + "\n" + _TRUNCATED)) > max_len and len(cut) > 0:
        cut = cut[: max(len(cut) - 200, 0)]
    return make(cut + "\n" + _TRUNCATED), True


def open_in_browser(url: str) -> bool:
    return webbrowser.open(url)


def default_report_name(now=None) -> str:
    now = now or datetime.now()
    return f"cw-decoder-fehlerbericht-{now:%Y%m%d-%H%M%S}.txt"


def save_report(text: str, path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path

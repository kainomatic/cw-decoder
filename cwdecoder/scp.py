# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""Super Check Partial: bekannte Contest-Rufzeichen (ADR-0026).

    is_known("OY1CT")         -> True
    near("Z4BPF")             -> ["IZ4BPF", …]   (ein Edit entfernt, bekannt)
    scp_version()             -> "2026.10.23"

Daten: cwdecoder/data/master.scp (supercheckpartial.com, ein Rufzeichen je
Zeile, Kommentare mit '#', Kopf '!!…'). Geladen beim ersten Aufruf, danach
gecacht (thread-sicher). Nicht aus gui_start importieren (Startzeit,
ADR-0020). Aktualisieren: python tools/update_scp.py.

SCP ist eine Liste von Rufzeichen, die in Contest-Logs vorkamen. Fehlt ein
Rufzeichen, ist es nicht falsch, nur nicht belegt; ein Treffer macht ein
gehörtes Rufzeichen dagegen deutlich verlässlicher.
"""
import logging
import re
import threading
import time
from typing import Iterable, Optional

from .paths import data_path

log = logging.getLogger(__name__)

SCP_FILE = "master.scp"
NEAR_MAX = 10
_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789/"
# Zusätze ohne Bedeutung für die Identität (OK1XYZ/P = OK1XYZ)
_STRIP_SUFFIXES = ("/P", "/M", "/MM", "/AM", "/QRP")


class ScpDb:
    """Menge bekannter Rufzeichen mit Abfragen; für Tests direkt aus einer
    Menge baubar: ScpDb({"IK2JET", "OY1CT"})."""

    def __init__(self, calls: Iterable[str], version: str = "", load_ms: float = 0.0):
        self.calls = frozenset(c.strip().upper() for c in calls if c and c.strip())
        self.version = version
        self.load_ms = load_ms

    def __len__(self):
        return len(self.calls)

    def is_known(self, call: str) -> bool:
        """Ist das Rufzeichen (oder sein Kern ohne /P, DL/ …) in SCP?"""
        c = (call or "").strip().upper()
        if not c:
            return False
        if c in self.calls:
            return True
        core = _core(c)
        return core != c and core in self.calls

    def near(self, call: str, max_edits: int = 1, limit: int = NEAR_MAX) -> list:
        """Bekannte Rufzeichen, die sich um höchstens max_edits Einfügungen,
        Löschungen oder Ersetzungen unterscheiden (ohne das Rufzeichen
        selbst). Reihenfolge: längster gemeinsamer Anfang zuerst, dann
        gleiche Länge, dann alphabetisch; höchstens limit Treffer."""
        c = (call or "").strip().upper()
        if not c:
            return []
        frontier, seen = {c}, {c}
        for _ in range(max(1, max_edits)):
            nxt = set()
            for w in frontier:
                for v in _edits1(w):
                    if v not in seen:
                        seen.add(v)
                        nxt.add(v)
            frontier = nxt
        hits = [v for v in seen if v != c and v in self.calls]
        hits.sort(key=lambda v: (-_common_prefix(v, c), abs(len(v) - len(c)), v))
        return hits[:limit]


def _core(c: str) -> str:
    for s in _STRIP_SUFFIXES:
        if c.endswith(s):
            c = c[:-len(s)]
            break
    if "/" in c:            # DL/OK1XYZ, OK1XYZ/DL: der längere Teil ist das Rufzeichen
        c = max(c.split("/"), key=len)
    return c


def _edits1(w: str):
    for i in range(len(w) + 1):
        a, b = w[:i], w[i:]
        if b:
            yield a + b[1:]                     # löschen
            for ch in _ALPHABET:
                if ch != b[0]:
                    yield a + ch + b[1:]        # ersetzen
        for ch in _ALPHABET:
            yield a + ch + b                    # einfügen


def _common_prefix(a: str, b: str) -> int:
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n


def parse_scp(text: str) -> ScpDb:
    """Text im MASTER.SCP-Format -> ScpDb."""
    m = re.search(r"Release\s+([0-9.]+)", text)
    calls = [ln.strip() for ln in text.splitlines()
             if ln.strip() and not ln.lstrip().startswith(("#", "!!"))]
    return ScpDb(calls, m.group(1) if m else "unbekannt")


_lock = threading.Lock()
_db: Optional[ScpDb] = None


def db() -> ScpDb:
    """Die mitgelieferte Datenbank (beim ersten Aufruf geladen)."""
    global _db
    with _lock:
        if _db is None:
            t0 = time.perf_counter()
            with open(data_path(SCP_FILE), encoding="ascii", errors="replace") as f:
                d = parse_scp(f.read())
            d.load_ms = (time.perf_counter() - t0) * 1000.0
            _db = d
            log.info("Super Check Partial geladen: Release %s, %d Rufzeichen, %.0f ms",
                     d.version, len(d), d.load_ms)
    return _db


def load() -> float:
    """Daten laden (z. B. vorab im Hintergrund); liefert die Ladezeit in ms."""
    return db().load_ms


def is_known(call: str) -> bool:
    return db().is_known(call)


def near(call: str, max_edits: int = 1, limit: int = NEAR_MAX) -> list:
    return db().near(call, max_edits, limit)


def scp_version() -> str:
    return db().version


def format_check(call: str) -> str:
    """"OY1CT: bekannt" / "Z4BPF: ähnlich: IZ4BPF, …" / "…: unbekannt" (--scp)."""
    c = call.strip().upper()
    if is_known(c):
        return f"{c}: bekannt"
    cands = near(c)
    return f"{c}: ähnlich: {', '.join(cands)}" if cands else f"{c}: unbekannt"


class _Default:
    """Adapter für CallsignSpotter: die mitgelieferte Datenbank, geladen
    beim ersten Zugriff; fehlt die Datei, gilt nichts als bekannt."""

    def __init__(self):
        self._failed = False

    def _db(self):
        if self._failed:
            return None
        try:
            return db()
        except (OSError, ValueError) as e:
            log.warning("Super Check Partial nicht lesbar: %s", e)
            self._failed = True
            return None

    def is_known(self, call: str) -> bool:
        d = self._db()
        return d.is_known(call) if d is not None else False

    def near(self, call: str, max_edits: int = 1, limit: int = NEAR_MAX) -> list:
        d = self._db()
        return d.near(call, max_edits, limit) if d is not None else []


DEFAULT = _Default()


def main(argv=None) -> int:
    """python -m cwdecoder.scp RUFZEICHEN …"""
    import sys
    from . import utf8_console
    utf8_console()
    for call in (sys.argv[1:] if argv is None else argv):
        print(format_check(call))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

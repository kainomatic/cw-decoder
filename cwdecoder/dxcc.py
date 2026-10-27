# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""Rufzeichen -> DXCC-Entität (Land) aus cty.dat (AD1C, ADR-0021).

    lookup("OY1CT")      -> Entity(name="Faroe Islands", short="Färöer",
                                   prefix="OY", iso="fo", continent="EU", ...)
    lookup("W1AW/MM")    -> None (Seefunk, kein Land)
    describe(entity)     -> "Färöer (OY, EU, CQ 14, ITU 18)"
    cty_version()        -> "CTY-3633 (2026-10-23)"

Daten: cwdecoder/data/cty.dat (Format AD1C, country-files.com),
cwdecoder/data/dxcc_table.json (Hauptpräfix -> deutscher Kurzname und
ISO-Code der Flagge). Beides wird beim ersten Aufruf geladen und gecacht
(thread-sicher). Nicht aus gui_start importieren (Startzeit, ADR-0020).

Regeln von lookup():
- Großschreibung; exakte Rufzeichen (=...) vor Präfixen, längster passender
  Präfix gewinnt. Zonen-/Kontinent-Überschreibungen am Eintrag gelten.
- /P, /M, /QRP, /AM u. ä. werden abgetrennt, /MM -> None.
- /1 … /9 ersetzt die Ziffer des Rufzeichens (EA6SX/5 -> EA5SX -> Spanien).
- Zwei Teile (DL/OK1XYZ, OK1XYZ/DL): der kürzere Teil ist der Standort.
"""
import json
import logging
import re
import threading
import time
from dataclasses import dataclass, replace
from typing import Optional

from .paths import data_path

log = logging.getLogger(__name__)

CTY_FILE = "cty.dat"
CTY_COPYRIGHT_FILE = "cty_copyright.txt"
TABLE_FILE = "dxcc_table.json"

# Zusätze ohne Standortbedeutung (werden abgetrennt)
IGNORED_SUFFIXES = {"P", "M", "AM", "QRP", "QRPP", "A", "B", "LH"}
MARITIME_SUFFIX = "MM"

_OVERRIDE_RE = re.compile(r"\((\d+)\)|\[(\d+)\]|<[^>]*>|\{([A-Z]{2})\}|~[^~]*~")
_SUFFIX_RE = re.compile(r"^(.*\d)([A-Z]+)$")      # 4X1AB -> 4X1, AB


@dataclass(frozen=True)
class Entity:
    """DXCC-Entität, ggf. mit den Zonen des passenden Eintrags."""
    name: str               # englisch, wie in cty.dat
    prefix: str             # Hauptpräfix (DL, OY, KH6, …), ohne '*'
    continent: str          # EU, AS, AF, NA, SA, OC
    cq: int
    itu: int
    short: str              # deutscher Kurzname (Fallback: name)
    iso: Optional[str]      # ISO-3166-Code der Flagge (klein) oder None
    wae_only: bool = False  # '*'-Eintrag: nur WAE-Liste (z. B. Sizilien)


class _Data:
    def __init__(self, entities, prefixes, exact, load_ms):
        self.entities = entities        # Hauptpräfix -> Entity
        self.prefixes = prefixes        # Präfix -> Entity (mit Überschreibungen)
        self.exact = exact              # Rufzeichen -> Entity
        self.max_len = max((len(p) for p in prefixes), default=0)
        self.load_ms = load_ms


_lock = threading.Lock()
_data: Optional[_Data] = None


def _apply_overrides(base: Entity, token: str):
    """'K1(5)[8]' -> ('K1', Entity mit CQ 5, ITU 8)."""
    cq, itu, cont = base.cq, base.itu, base.continent
    for m in _OVERRIDE_RE.finditer(token):
        if m.group(1):
            cq = int(m.group(1))
        elif m.group(2):
            itu = int(m.group(2))
        elif m.group(3):
            cont = m.group(3)
    key = _OVERRIDE_RE.sub("", token).strip()
    if (cq, itu, cont) != (base.cq, base.itu, base.continent):
        base = replace(base, cq=cq, itu=itu, continent=cont)
    return key, base


def parse_cty(text: str, table=None):
    """cty.dat-Text -> (entities, prefixes, exact). table: Hauptpräfix ->
    {"name": Kurzname, "iso": Code|None}."""
    table = table or {}
    entities, prefixes, exact = {}, {}, {}
    # Einträge enden mit ';' – Kopfzeile (9 Felder mit ':') plus Präfixliste
    for record in text.split(";"):
        record = record.strip()
        if not record:
            continue
        fields = record.split(":")
        if len(fields) < 9:
            raise ValueError(f"cty.dat: unerwarteter Eintrag {record[:60]!r}")
        name, cq, itu, cont = (f.strip() for f in fields[:4])
        main = fields[7].strip()
        wae = main.startswith("*")
        main = main.lstrip("*")
        info = table.get(main) or {}
        ent = Entity(name=name, prefix=main, continent=cont, cq=int(cq), itu=int(itu),
                     short=info.get("name") or name, iso=info.get("iso"), wae_only=wae)
        entities[main] = ent
        for tok in fields[8].replace("\n", " ").replace("\r", " ").split(","):
            tok = tok.strip()
            if not tok:
                continue
            is_exact = tok.startswith("=")
            key, e = _apply_overrides(ent, tok.lstrip("="))
            (exact if is_exact else prefixes)[key.upper()] = e
    return entities, prefixes, exact


def load_table():
    with open(data_path(TABLE_FILE), encoding="utf-8") as f:
        return json.load(f)


def _load() -> _Data:
    global _data
    with _lock:
        if _data is None:
            t0 = time.perf_counter()
            with open(data_path(CTY_FILE), encoding="latin-1") as f:
                text = f.read()
            try:
                table = load_table()
            except (OSError, ValueError) as e:     # Fallback: englische Namen, keine Flaggen
                log.warning("DXCC-Tabelle nicht lesbar (%s), englische Namen", e)
                table = {}
            ents, pre, ex = parse_cty(text, table)
            ms = (time.perf_counter() - t0) * 1000.0
            _data = _Data(ents, pre, ex, ms)
            log.info("cty.dat geladen: %s, %d Entitäten, %d Präfixe, %d Rufzeichen, %.0f ms",
                     cty_version(), len(ents), len(pre), len(ex), ms)
    return _data


def load():
    """Daten laden (z. B. vorab im Hintergrund); liefert die Ladezeit in ms."""
    return _load().load_ms


def entities():
    """Alle Entitäten (Hauptpräfix -> Entity)."""
    return dict(_load().entities)


def _longest_prefix(d: _Data, s: str) -> Optional[Entity]:
    for n in range(min(len(s), d.max_len), 0, -1):
        e = d.prefixes.get(s[:n])
        if e is not None:
            return e
    return None


def _resolve(d: _Data, call: str) -> Optional[Entity]:
    return d.exact.get(call) or _longest_prefix(d, call)


def _replace_area_digit(call: str, digit: str) -> str:
    m = _SUFFIX_RE.match(call)
    if not m:
        return call
    return m.group(1)[:-1] + digit + m.group(2)


def lookup(call: str) -> Optional[Entity]:
    """Entität zum Rufzeichen oder None (unbekannt, /MM)."""
    call = (call or "").strip().upper()
    if not call:
        return None
    d = _load()
    if call in d.exact:
        return d.exact[call]
    parts = [p for p in call.split("/") if p]
    if MARITIME_SUFFIX in parts[1:]:
        return None
    digit = None
    core = [parts[0]]
    for p in parts[1:]:
        if p in IGNORED_SUFFIXES:
            continue
        if len(p) == 1 and p.isdigit():
            digit = p
            continue
        core.append(p)
    if len(core) == 1:
        c = core[0]
        if digit is not None:
            c = _replace_area_digit(c, digit)
        return _resolve(d, c) if c else None
    joined = "/".join(core)
    if joined in d.exact:
        return d.exact[joined]
    # Standort-Präfix: der kürzere Teil (DL/OK1XYZ, OK1XYZ/DL)
    loc = min(core, key=len)
    others = [p for p in core if p is not loc]
    e = _longest_prefix(d, loc)
    if e is not None:
        return e
    for p in others:
        e = _resolve(d, p)
        if e is not None:
            return e
    return None


def describe(e: Entity) -> str:
    """"Färöer (OY, EU, CQ 14, ITU 18)" – für Tooltip und --dxcc."""
    return f"{e.short} ({e.prefix}, {e.continent}, CQ {e.cq}, ITU {e.itu})"


def short_name(e: Entity, max_len: int) -> str:
    """Kurzname, notfalls mit „…" auf max_len Zeichen gekürzt."""
    s = e.short
    return s if len(s) <= max_len else s[:max_len - 1].rstrip() + "…"


def cty_version() -> str:
    """"CTY-3633 (2026-10-23)" aus der Kopfzeile von cty_copyright.txt;
    "unbekannt", wenn die Datei fehlt."""
    try:
        with open(data_path(CTY_COPYRIGHT_FILE), encoding="utf-8") as f:
            head = f.readline()
    except OSError:
        return "unbekannt"
    m = re.search(r"#(\d+).*?(\d{1,2}) (\w+) (\d{4})", head)
    if not m:
        return head.strip() or "unbekannt"
    months = ["january", "february", "march", "april", "may", "june", "july",
              "august", "september", "october", "november", "december"]
    num, day, month, year = m.groups()
    try:
        mon = months.index(month.lower()) + 1
    except ValueError:
        return f"CTY-{num} ({day} {month} {year})"
    return f"CTY-{num} ({year}-{mon:02d}-{int(day):02d})"


def main(argv=None) -> int:
    """python -m cwdecoder.dxcc RUFZEICHEN …"""
    import sys
    from . import utf8_console
    utf8_console()
    args = list(sys.argv[1:] if argv is None else argv)
    for call in args:
        print(format_lookup(call))
    return 0


def format_lookup(call: str) -> str:
    """"DJ7PR: Deutschland (DL, EU, CQ 14, ITU 28)" bzw. "…: unbekannt"."""
    e = lookup(call)
    return f"{call.upper()}: {describe(e) if e else 'unbekannt'}"


if __name__ == "__main__":
    raise SystemExit(main())

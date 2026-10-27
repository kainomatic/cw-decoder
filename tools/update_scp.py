# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""MASTER.SCP neu laden (Dev-Werkzeug, ADR-0026; kein Download zur Laufzeit).

    python tools/update_scp.py

Holt die Super-Check-Partial-Datenbank von supercheckpartial.com und legt
sie als cwdecoder/data/master.scp ab (Zeilenenden LF). Die Kopfzeilen
(`# Release JJJJ.MM.TT`) bleiben erhalten, daraus liest
scp.scp_version() den Stand. Danach: pytest tests/test_scp.py.
"""
import argparse
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "cwdecoder" / "data"
URL = "https://www.supercheckpartial.com/MASTER.SCP"
UA = {"User-Agent": "cw-decoder-update-scp"}
MIN_CALLS = 10000      # Plausibilität: eine abgeschnittene Datei nicht übernehmen


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--url", default=URL)
    a = p.parse_args(argv)
    req = urllib.request.Request(a.url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        text = r.read().decode("ascii", "replace")
    lines = [ln.strip() for ln in text.splitlines()]
    calls = [ln for ln in lines if ln and not ln.startswith(("#", "!!"))]
    if len(calls) < MIN_CALLS:
        raise SystemExit(f"Nur {len(calls)} Rufzeichen geladen – Datei unvollständig?")
    m = re.search(r"Release\s+([0-9.]+)", text)
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "master.scp").write_text("\n".join(lines).strip() + "\n", encoding="ascii",
                                     newline="\n")
    print(f"master.scp geschrieben: {len(calls)} Rufzeichen, Release "
          f"{m.group(1) if m else 'unbekannt'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

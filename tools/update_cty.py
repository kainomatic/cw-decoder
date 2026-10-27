# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""cty.dat neu laden (Dev-Werkzeug, ADR-0021; kein Download zur Laufzeit).

    python tools/update_cty.py            neueste Version von country-files.com
    python tools/update_cty.py --num 3633 bestimmte Version

Holt das Zip der „Contest Country Files" (AD1C), legt cty.dat und den
Lizenztext (copyright.txt -> cty_copyright.txt, Kopfzeile mit Nummer und
Datum, daraus liest dxcc.cty_version()) nach cwdecoder/data/. Danach:
pytest tests/test_dxcc.py (neue Entitäten brauchen einen Eintrag in
cwdecoder/data/dxcc_table.json) und ggf. python tools/make_flags.py.
"""
import argparse
import io
import re
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "cwdecoder" / "data"
HOME = "https://www.country-files.com/"
ZIP_URL = "https://www.country-files.com/cty/download/{num}/cty-{num}.zip"
UA = {"User-Agent": "cw-decoder-update-cty"}


def _get(url: str) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return r.read()


def latest_number() -> int:
    html = _get(HOME).decode("utf-8", "replace")
    nums = [int(n) for n in re.findall(r"/cty/download/(\d+)/cty-\1\.zip", html)]
    if not nums:
        raise SystemExit("Keine CTY-Version auf country-files.com gefunden")
    return max(nums)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--num", type=int, help="CTY-Nummer (Standard: neueste)")
    a = p.parse_args(argv)
    num = a.num or latest_number()
    z = zipfile.ZipFile(io.BytesIO(_get(ZIP_URL.format(num=num))))
    names = {n.lower(): n for n in z.namelist()}
    cty = z.read(names["cty.dat"])
    lic = z.read(names["copyright.txt"]).decode("utf-8", "replace")
    if f"#{num}" not in lic.splitlines()[0]:
        raise SystemExit(f"copyright.txt passt nicht zu CTY-{num}: {lic.splitlines()[0]!r}")
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "cty.dat").write_bytes(cty)
    (DATA / "cty_copyright.txt").write_text(lic.replace("\r\n", "\n"), encoding="utf-8")
    print(f"CTY-{num}: cty.dat ({len(cty)} Bytes) und cty_copyright.txt geschrieben")
    print(lic.splitlines()[0])
    return 0


if __name__ == "__main__":
    sys.exit(main())

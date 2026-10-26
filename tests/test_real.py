# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""Echte Aufnahmen vom Funkgerät als Regressionsschutz (testdata/real/, #8).

Erwartet werden enthaltene Fragmente, kein Vollvergleich: Bei echten
Signalen ist nicht jedes Zeichen sicher, aber Rufzeichen und typische
Floskeln müssen kommen. Die Tabelle steht in run_matrix.REAL_CASES;
Fragmente in run_matrix.REAL_KNOWN_GAPS sind bekannte Lücken (xfail).
"""
import functools
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))
import run_matrix  # noqa: E402

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(not os.path.isdir(run_matrix.REAL_DIR),
                       reason="testdata/real/ fehlt"),
]


@functools.lru_cache(maxsize=None)
def _text(fname, seconds=None):
    return run_matrix.decode_real(fname, seconds)


def _fragment_params():
    for fname, fragments, _quiet in run_matrix.REAL_CASES:
        for frag in fragments:
            marks = []
            if (fname, frag) in run_matrix.REAL_KNOWN_GAPS:
                marks.append(pytest.mark.xfail(reason="bekannte Lücke (#8)", strict=False))
            yield pytest.param(fname, frag, marks=marks, id=f"{fname[3:18]}-{frag}")


@pytest.mark.parametrize("fname,fragment", list(_fragment_params()))
def test_real_fragment(fname, fragment):
    text = _text(fname)
    assert fragment in text, f"fehlt {fragment!r} in: {text}"


@pytest.mark.parametrize("fname,quiet_s", [(f, q) for f, _, q in run_matrix.REAL_CASES if q],
                         ids=lambda v: str(v)[3:18] if isinstance(v, str) else f"{v:.0f}s")
def test_real_leere_frequenz(fname, quiet_s):
    head = _text(fname, quiet_s)
    n = len(head.replace(" ", ""))
    assert n <= run_matrix.NOISE_MAX_CHARS, \
        f"{n} Zeichen in den ersten {quiet_s:.0f} s (leere Frequenz): {head}"


@pytest.mark.parametrize("fname,calls", list(run_matrix.REAL_SPOTS.items()),
                         ids=lambda v: str(v)[3:18] if isinstance(v, str) else "")
def test_real_rufzeichen(fname, calls):
    got = run_matrix.spot_real(_text(fname))
    missing = [c for c in calls if c not in got]
    assert not missing, f"Spotter fand {got}, es fehlt {missing}"

# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""Zufällige Texte für die Testmatrix (Issue #1).

Damit die Schwellen nicht an zwei festen Sätzen getunt werden, liefert
dieses Modul Rufzeichen aus verschiedenen Präfix-Mustern, Contest-
Exchanges, QSO-Floskeln und Klartextblöcke, die alle Buchstaben, Ziffern
und Prosigns abdecken. Alle Rufzeichen sind fiktiv.
"""
import numpy as np

# Präfix-Muster: (Buchstaben, optionale Ziffer im Präfix) -> wird mit
# Trennziffer und Suffix kombiniert
PREFIXES_2L = ["DL", "DK", "DJ", "OK", "OE", "HB", "SP", "SM", "LA", "OZ", "ON",
               "PA", "EA", "EI", "LZ", "YO", "UA", "UR", "VK", "ZL", "JA", "VE",
               "PY", "LU", "ZS", "CT", "SV", "YU", "OH", "ES", "LY", "YL"]
PREFIXES_1L = ["W", "K", "N", "G", "M", "F", "I"]
PREFIXES_DIGIT = ["9A", "4X", "5B", "3A", "4O", "9H", "5P", "7S", "2E", "2M"]
WORDS = ["CQ", "TEST", "DE", "K", "KN", "TU", "73", "88", "GM", "GA", "GE", "GN",
         "UR", "RST", "599", "5NN", "ENN", "HW", "HW?", "BK", "AGN", "PSE", "QRZ",
         "QSY", "QTH", "NAME", "OP", "WX", "RIG", "ANT", "PWR", "TNX", "FB", "ES",
         "HPE", "CUAGN", "SRI", "QRM", "QSB", "DX", "VY", "NR", "NW", "NIL", "R"]
NAMES = ["STEFAN", "KLAUS", "PETER", "JOHN", "MIKE", "HANS", "JIRI", "PIET",
         "OLE", "JUAN", "IVAN", "JIM", "TOM", "BOB", "DAVE", "FRANK", "UWE"]
QTHS = ["BERLIN", "HAMBURG", "PRAHA", "WIEN", "LONDON", "PARIS", "MADRID",
        "OSLO", "KIEL", "KOELN", "BONN", "LINZ", "GENT", "LYON", "TURKU"]
PROSIGNS = ["<AR>", "<SK>", "<BT>", "<KN>", "<AS>"]
ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"


def random_call(rng: np.random.Generator) -> str:
    kind = rng.random()
    if kind < 0.55:
        pre = rng.choice(PREFIXES_2L)
    elif kind < 0.8:
        pre = rng.choice(PREFIXES_1L)
    else:
        pre = rng.choice(PREFIXES_DIGIT)
    digit = str(rng.integers(0, 10))
    suffix_len = int(rng.choice([1, 2, 3, 3, 3, 4]))
    suffix = "".join(rng.choice(list("ABCDEFGHIJKLMNOPQRSTUVWXYZ"), suffix_len))
    call = pre + digit + suffix
    r = rng.random()
    if r < 0.08:
        call += "/P"
    elif r < 0.12:
        call += "/M"
    elif r < 0.17:
        call = rng.choice(PREFIXES_2L) + "/" + call
    return call


def random_exchange(rng: np.random.Generator) -> str:
    kind = rng.random()
    if kind < 0.4:
        return f"{rng.choice(['599', '5NN'])} {rng.integers(1, 1500):03d}"
    if kind < 0.7:
        return f"{rng.choice(['599', '5NN'])} {rng.integers(1, 99):02d}"
    return f"{rng.choice(['599', '5NN'])} {rng.choice(['DL', 'OK', 'ON', 'SP'])}{rng.integers(1, 9)}"


def contest_qso(rng: np.random.Generator) -> str:
    me, you = random_call(rng), random_call(rng)
    pattern = rng.integers(0, 4)
    if pattern == 0:
        return f"CQ TEST {me} {me} TEST"
    if pattern == 1:
        return f"{you} {random_exchange(rng)}"
    if pattern == 2:
        return f"TU {random_exchange(rng)} {me}"
    return f"{you} DE {me} {random_exchange(rng)} K"


def ragchew(rng: np.random.Generator) -> str:
    me, you = random_call(rng), random_call(rng)
    parts = [f"{you} DE {me}"]
    n = int(rng.integers(2, 5))
    for _ in range(n):
        k = rng.integers(0, 6)
        if k == 0:
            parts.append(f"UR RST {rng.choice(['559', '579', '589', '599', '449'])}")
        elif k == 1:
            parts.append(f"NAME {rng.choice(NAMES)}")
        elif k == 2:
            parts.append(f"QTH {rng.choice(QTHS)}")
        elif k == 3:
            parts.append(f"WX {rng.choice(['SUNNY', 'RAIN', 'CLOUDY', 'SNOW'])} TEMP {rng.integers(-5, 30)} C")
        elif k == 4:
            parts.append(f"PWR {rng.choice([5, 50, 100, 400])} W ANT {rng.choice(['DIPOLE', 'VERT', 'YAGI'])}")
        else:
            parts.append(" ".join(rng.choice(WORDS, 3)))
    parts.append(rng.choice(["HW? " + rng.choice(PROSIGNS), "73 " + rng.choice(PROSIGNS), f"{you} DE {me} K"]))
    return " ".join(parts)


def random_block(rng: np.random.Generator, n_groups: int = 5) -> str:
    """Zufallsgruppen aus allen Zeichen (wie beim Hören von Fünfergruppen)."""
    groups = []
    for _ in range(n_groups):
        groups.append("".join(rng.choice(list(ALPHABET), 5)))
    return " ".join(groups)


def random_text(rng: np.random.Generator, kind: str = None) -> str:
    """kind: 'contest' | 'qso' | 'groups' | 'cq' | None (zufällig)."""
    if kind is None:
        kind = rng.choice(["contest", "qso", "groups", "cq"], p=[0.4, 0.3, 0.15, 0.15])
    if kind == "contest":
        return contest_qso(rng)
    if kind == "qso":
        return ragchew(rng)
    if kind == "groups":
        return random_block(rng)
    me = random_call(rng)
    return f"CQ CQ CQ DE {me} {me} {me} PSE K"

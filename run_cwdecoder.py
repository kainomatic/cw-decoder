# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""Einstieg für PyInstaller (cwdecoder.spec) und zum direkten Start:

    python run_cwdecoder.py                 Oberfläche
    python run_cwdecoder.py --decode x.wav  Offline-Decodierung
    python run_cwdecoder.py --list-devices  Audiogeräte
    python run_cwdecoder.py --version       Version
"""
import sys

from cwdecoder.app_main import main

if __name__ == "__main__":
    sys.exit(main())

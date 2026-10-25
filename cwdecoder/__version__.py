# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""Einzige Quelle für Versionsnummer und Release-Kanal.

CHANNEL ist "stable" oder "beta". Der Kanal trennt App-Ordner (Config, Log,
Lock) von Stable- und Beta-Installation, siehe docs/adr/ADR-0003.
"""

__version__ = "0.1.0"
CHANNEL = "stable"

APP_NAME = "CW Decoder"
REPO_URL = "https://github.com/kainomatic/cw-decoder"

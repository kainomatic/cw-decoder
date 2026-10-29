# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""Anforderung „Engine einschalten“ von der zweiten an die erste Instanz (#30).

Startet N1MMs CW Reader den CW Decoder, während schon einer läuft, und
bietet der laufende die Engine nicht an, legt die zweite Instanz neben
`cwdecoder.lock` die Datei `engine-request.json` an (Port und Fenstertitel
von N1MM) und wartet kurz, bis der Port erreichbar ist. Die erste holt die
Datei in `App._poll` ab (ADR-0009: kein tk aus Threads) und schaltet die
Engine für diesen Lauf ein, ohne etwas zu speichern (ADR-0030).

Nur Standardbibliothek: `gui_start` benutzt das Modul vor den schweren
Imports (ADR-0020).
"""
import json
import logging
import os
import time
from pathlib import Path

log = logging.getLogger(__name__)

REQUEST_FILE = "engine-request.json"
MAX_AGE_S = 30.0        # ältere Anforderungen (z. B. erste Instanz abgestürzt) verfallen


def request_path(app_dir=None) -> Path:
    if app_dir is None:
        from .paths import get_app_dir
        app_dir = get_app_dir()
    return Path(app_dir) / REQUEST_FILE


def write_request(path, port: int, title: str) -> None:
    """Anforderung atomar schreiben (erst .tmp, dann umbenennen)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"port": int(port), "title": title, "pid": os.getpid(), "time": time.time()}
    tmp = path.with_name(path.name + f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(data), encoding="utf-8")
    os.replace(tmp, path)


def take_request(path, now=None, max_age_s: float = MAX_AGE_S):
    """Anforderung lesen und löschen. Liefert (port, title) oder None
    (keine Datei, unlesbar oder veraltet – dann wird sie nur gelöscht)."""
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError as e:
        log.warning("Engine-Anforderung nicht lesbar: %s", e)
        return None
    try:
        path.unlink()
    except OSError:
        pass
    try:
        data = json.loads(text)
        port, title, t = int(data["port"]), str(data["title"]), float(data["time"])
    except (ValueError, KeyError, TypeError) as e:
        log.warning("Engine-Anforderung ungültig, verworfen: %s", e)
        return None
    age = (time.time() if now is None else now) - t
    if age > max_age_s:
        log.info("Engine-Anforderung von vor %.0f s verworfen (veraltet)", age)
        return None
    if not 1024 <= port <= 65535:
        log.warning("Engine-Anforderung mit ungültigem Port %d verworfen", port)
        return None
    return port, title

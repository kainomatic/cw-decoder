# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""Einstellungen als JSON in <App-Ordner>/config.json (ADR-0005).

load()   fehlt die Datei: Defaults. Ist sie kaputt (kein gültiges JSON, kein
         Objekt): wird sie nach config.json.broken-<Zeitstempel> umbenannt,
         Defaults geladen, WARNING geloggt und ein Hinweis für den nächsten
         GUI-Start hinterlegt (pop_broken_notice()). Einzelne Werte mit
         falschem Typ fallen still auf ihren Default zurück (WARNING im Log).
save()   schreibt atomar (temporäre Datei + os.replace).

Unbekannte Schlüssel bleiben beim Laden und Speichern erhalten, damit eine
ältere Version die Einstellungen einer neueren nicht wegwirft.
"""
import json
import logging
import os
import tempfile
import time
from datetime import datetime
from pathlib import Path

log = logging.getLogger(__name__)

CONFIG_FILE = "config.json"
NOTICE_SUFFIX = ".broken-notice"

DEFAULTS = {
    "update_check": True,
    "device_name": None,
    "fixed_freq": None,
    "n1mm_enabled": False,
    "n1mm_wipe": True,
    # Übergabewege an N1MM (ADR-0022): Engine für den CW Reader, Skimmer-Spot,
    # Entry Window tippen, Zwischenablage; Port der Engine wie N1MMs CW Reader 1
    "n1mm_engine": True,
    "n1mm_spot": True,
    "n1mm_type": False,
    "n1mm_clipboard": False,
    "n1mm_rpc_port": 7367,
    "record_default": False,
    # Ringpuffer (ADR-0024): Kapazität, „Letzte … s speichern“, „Nochmal hören“
    "ring_seconds": 60,
    "save_last_s": 30,
    "replay_s": 10,
    # Nochmal hören (#25): Frist des Festhaltens nach dem Ende der
    # Wiedergabe, Starttempo des Reglers (0,5–1,0), Ausgabegerät als
    # Namensteil (None = Standard). Ersetzt replay_slow (True -> 0,7)
    "replay_hold_s": 5,
    "replay_rate": 1.0,
    "output_device": None,
    # Wörterbuch-Zerlegung (ADR-0026): Trenner · im Text; N1MMs CW Reader
    # bekommt die getrennten Wörter mit echten Leerzeichen
    "segment_words": True,
    "n1mm_engine_segmented": True,
}

# Grenzen der Ringpuffer-Werte (Sekunden); save_last_s höchstens ring_seconds
RING_SECONDS_RANGE = (10, 300)
SAVE_LAST_RANGE = (5, 300)
REPLAY_RANGE = (3, 30)
REPLAY_HOLD_RANGE = (1, 60)
REPLAY_RATE_RANGE = (0.5, 1.0)
LEGACY_SLOW_RATE = 0.7      # replay_slow=True aus Versionen bis beta15


class ConfigError(ValueError):
    """Config-Datei vorhanden, aber nicht lesbar (kaputtes JSON o. ä.)."""


def _is_bool(v):
    return isinstance(v, bool)


def _is_opt_str(v):
    return v is None or isinstance(v, str)


def _is_opt_freq(v):
    return v is None or (isinstance(v, (int, float)) and not isinstance(v, bool)
                         and 50.0 <= float(v) <= 4000.0)


def _int_in(lo, hi):
    def check(v):
        return isinstance(v, int) and not isinstance(v, bool) and lo <= v <= hi
    return check


def _float_in(lo, hi):
    def check(v):
        return (isinstance(v, (int, float)) and not isinstance(v, bool)
                and lo <= float(v) <= hi)
    return check


def _is_port(v):
    return isinstance(v, int) and not isinstance(v, bool) and 1024 <= v <= 65535


_VALIDATORS = {
    "update_check": _is_bool,
    "device_name": _is_opt_str,
    "fixed_freq": _is_opt_freq,
    "n1mm_enabled": _is_bool,
    "n1mm_wipe": _is_bool,
    "n1mm_engine": _is_bool,
    "n1mm_spot": _is_bool,
    "n1mm_type": _is_bool,
    "n1mm_clipboard": _is_bool,
    "n1mm_rpc_port": _is_port,
    "record_default": _is_bool,
    "ring_seconds": _int_in(*RING_SECONDS_RANGE),
    "save_last_s": _int_in(*SAVE_LAST_RANGE),
    "replay_s": _int_in(*REPLAY_RANGE),
    "replay_hold_s": _int_in(*REPLAY_HOLD_RANGE),
    "replay_rate": _float_in(*REPLAY_RATE_RANGE),
    "output_device": _is_opt_str,
    "segment_words": _is_bool,
    "n1mm_engine_segmented": _is_bool,
}


def get_config_path() -> Path:
    from .paths import get_app_dir
    return get_app_dir() / CONFIG_FILE


def defaults() -> dict:
    return dict(DEFAULTS)


def parse(text: str) -> dict:
    """JSON-Text in eine vollständige Config wandeln. Wirft ConfigError."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ConfigError(f"kein gültiges JSON ({e})") from e
    if not isinstance(data, dict):
        raise ConfigError("JSON enthält kein Objekt")
    cfg = defaults()
    if "replay_rate" not in data and data.get("replay_slow") is True:
        # bis beta15: Haken „langsamer (0,7×)“ (#25)
        log.info("Config: replay_slow -> replay_rate %.1f", LEGACY_SLOW_RATE)
        data = dict(data, replay_rate=LEGACY_SLOW_RATE)
    for key, value in data.items():
        check = _VALIDATORS.get(key)
        if check is not None and not check(value):
            log.warning("Config: ungültiger Wert für %s (%r), Standard %r wird benutzt",
                        key, value, DEFAULTS[key])
            continue
        cfg[key] = float(value) if key == "replay_rate" else value
    if cfg["save_last_s"] > cfg["ring_seconds"]:
        log.warning("Config: save_last_s %r größer als ring_seconds %r, gekürzt",
                    cfg["save_last_s"], cfg["ring_seconds"])
        cfg["save_last_s"] = cfg["ring_seconds"]
    return cfg


def _notice_path(path: Path) -> Path:
    return path.with_name(path.name + NOTICE_SUFFIX)


def _quarantine(path: Path, reason: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = path.with_name(f"{path.name}.broken-{stamp}")
    n = 1
    while target.exists():
        n += 1
        target = path.with_name(f"{path.name}.broken-{stamp}-{n}")
    os.replace(path, target)
    log.warning("Config ungültig (%s): umbenannt nach %s, Standardwerte geladen",
                reason, target.name)
    try:
        _notice_path(path).write_text(f"{target.name}\n{reason}\n", encoding="utf-8")
    except OSError as e:
        log.warning("Hinweisdatei für die GUI nicht schreibbar: %s", e)
    return target


def load(path=None) -> dict:
    """Config laden; liefert immer eine vollständige Config."""
    path = Path(path) if path is not None else get_config_path()
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        log.info("Keine Config vorhanden, Standardwerte")
        return defaults()
    except (OSError, UnicodeDecodeError) as e:
        if isinstance(e, UnicodeDecodeError):
            try:
                _quarantine(path, "keine UTF-8-Textdatei")
            except OSError as e2:
                log.error("Config nicht umbenennbar: %s", e2)
        else:
            log.error("Config nicht lesbar (%s), Standardwerte", e)
        return defaults()
    try:
        cfg = parse(text)
    except ConfigError as e:
        try:
            _quarantine(path, str(e))
        except OSError as e2:
            log.error("Config ungültig (%s) und nicht umbenennbar: %s", e, e2)
        return defaults()
    log.info("Config geladen: %s", path)
    return cfg


def save(cfg: dict, path=None) -> None:
    """Config atomar schreiben. Wirft OSError, wenn das nicht geht."""
    path = Path(path) if path is not None else get_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(cfg, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        # Unter Windows kann ein Virenscanner die Zieldatei kurz sperren
        for attempt in range(5):
            try:
                os.replace(tmp, path)
                break
            except PermissionError:
                if attempt == 4:
                    raise
                time.sleep(0.05)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    log.debug("Config gespeichert: %s", path)


def pop_broken_notice(path=None):
    """Hinweis auf eine umbenannte, kaputte Config abholen (einmalig).

    Liefert (umbenannter Dateiname, Grund) oder None."""
    path = Path(path) if path is not None else get_config_path()
    notice = _notice_path(path)
    try:
        lines = notice.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    try:
        notice.unlink()
    except OSError:
        pass
    name = lines[0] if lines else "?"
    reason = lines[1] if len(lines) > 1 else ""
    return name, reason

# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""Einstellungen (ADR-0005)."""
import json
import logging
import os

import pytest

from cwdecoder import config


@pytest.fixture
def cfg_path(tmp_path):
    return tmp_path / "config.json"


def test_defaults_match_spec():
    assert config.defaults() == {
        "update_check": True, "device_name": None, "fixed_freq": None,
        "n1mm_enabled": False, "n1mm_wipe": True, "record_default": False,
    }


def test_defaults_are_a_copy():
    d = config.defaults()
    d["n1mm_enabled"] = True
    assert config.DEFAULTS["n1mm_enabled"] is False


def test_missing_file_gives_defaults(cfg_path):
    assert config.load(cfg_path) == config.defaults()
    assert not cfg_path.exists()
    assert config.pop_broken_notice(cfg_path) is None


def test_save_load_roundtrip(cfg_path):
    cfg = config.defaults()
    cfg.update(device_name="USB Audio CODEC", fixed_freq=650.5, n1mm_enabled=True)
    config.save(cfg, cfg_path)
    assert config.load(cfg_path) == cfg
    # keine temporären Dateien übrig
    assert [p.name for p in cfg_path.parent.iterdir()] == ["config.json"]


def test_broken_json_is_renamed_and_noticed(cfg_path, caplog):
    cfg_path.write_text("{kaputt", encoding="utf-8")
    with caplog.at_level(logging.WARNING, logger="cwdecoder"):
        cfg = config.load(cfg_path)
    assert cfg == config.defaults()
    assert not cfg_path.exists()
    broken = [p for p in cfg_path.parent.iterdir() if p.name.startswith("config.json.broken-2")]
    assert len(broken) == 1
    assert broken[0].read_text(encoding="utf-8") == "{kaputt"
    assert any("ungültig" in r.message for r in caplog.records)
    notice = config.pop_broken_notice(cfg_path)
    assert notice is not None and notice[0] == broken[0].name and "JSON" in notice[1]
    # nur einmal
    assert config.pop_broken_notice(cfg_path) is None


def test_two_broken_files_get_distinct_names(cfg_path):
    for _ in range(2):
        cfg_path.write_text("[1, 2", encoding="utf-8")
        config.load(cfg_path)
    broken = [p for p in cfg_path.parent.iterdir() if ".broken-2" in p.name]
    assert len(broken) == 2


def test_json_not_an_object_is_broken(cfg_path):
    cfg_path.write_text("[1, 2, 3]", encoding="utf-8")
    assert config.load(cfg_path) == config.defaults()
    assert config.pop_broken_notice(cfg_path) is not None


def test_non_utf8_is_broken(cfg_path):
    cfg_path.write_bytes(b"\xff\xfe\x00{")
    assert config.load(cfg_path) == config.defaults()
    assert config.pop_broken_notice(cfg_path) is not None


def test_wrong_types_fall_back_per_key(cfg_path):
    cfg_path.write_text(json.dumps({
        "fixed_freq": "abc", "n1mm_enabled": "ja", "device_name": 3,
        "n1mm_wipe": False, "record_default": True,
    }), encoding="utf-8")
    cfg = config.load(cfg_path)
    assert cfg["fixed_freq"] is None
    assert cfg["n1mm_enabled"] is False
    assert cfg["device_name"] is None
    assert cfg["n1mm_wipe"] is False and cfg["record_default"] is True
    assert cfg_path.exists()            # Datei bleibt, nur Werte ersetzt


def test_fixed_freq_out_of_range_and_bool(cfg_path):
    for bad in (5, 99999, True):
        cfg_path.write_text(json.dumps({"fixed_freq": bad}), encoding="utf-8")
        assert config.load(cfg_path)["fixed_freq"] is None
    cfg_path.write_text(json.dumps({"fixed_freq": 700}), encoding="utf-8")
    assert config.load(cfg_path)["fixed_freq"] == 700


def test_unknown_keys_are_kept(cfg_path):
    cfg_path.write_text(json.dumps({"zukunft": {"a": 1}}), encoding="utf-8")
    cfg = config.load(cfg_path)
    assert cfg["zukunft"] == {"a": 1}
    config.save(cfg, cfg_path)
    assert json.loads(cfg_path.read_text(encoding="utf-8"))["zukunft"] == {"a": 1}


def test_save_is_atomic_on_failure(cfg_path, monkeypatch):
    config.save(config.defaults(), cfg_path)
    before = cfg_path.read_text(encoding="utf-8")

    def fail(*_a, **_k):
        raise OSError("Platte voll")
    monkeypatch.setattr(config.os, "replace", fail)
    cfg = config.defaults()
    cfg["n1mm_enabled"] = True
    with pytest.raises(OSError):
        config.save(cfg, cfg_path)
    assert cfg_path.read_text(encoding="utf-8") == before
    assert [p.name for p in cfg_path.parent.iterdir()] == ["config.json"]


def test_save_retries_permission_error(cfg_path, monkeypatch):
    real = os.replace
    calls = {"n": 0}

    def flaky(a, b):
        calls["n"] += 1
        if calls["n"] < 3:
            raise PermissionError("gesperrt")
        return real(a, b)
    monkeypatch.setattr(config.os, "replace", flaky)
    monkeypatch.setattr(config.time, "sleep", lambda s: None)
    config.save(config.defaults(), cfg_path)
    assert calls["n"] == 3 and cfg_path.exists()


def test_default_path_in_app_dir(app_env):
    p = config.get_config_path()
    assert p.name == "config.json"
    assert p.parent.is_dir()
    assert str(app_env) in str(p)

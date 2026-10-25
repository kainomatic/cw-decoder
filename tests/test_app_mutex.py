# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""AppMutex für den Installer (ADR-0013)."""
import sys
import uuid

import pytest

from cwdecoder import app_mutex


def test_names():
    assert app_mutex.mutex_name("stable") == "CWDecoder-Stable"
    assert app_mutex.mutex_name("beta") == "CWDecoder-Beta"


@pytest.mark.skipif(sys.platform != "win32", reason="nur unter Windows")
def test_create_and_close(monkeypatch):
    name = f"CWDecoder-Test-{uuid.uuid4().hex}"
    monkeypatch.setitem(app_mutex.MUTEX_NAMES, "stable", name)
    m = app_mutex.create_app_mutex("stable")
    assert m is not None and app_mutex.mutex_exists(name)
    m.close()
    m.close()   # zweimal schadet nicht
    assert not app_mutex.mutex_exists(name)


@pytest.mark.skipif(sys.platform == "win32", reason="nur außerhalb von Windows")
def test_non_windows_is_noop():
    assert app_mutex.create_app_mutex("stable") is None

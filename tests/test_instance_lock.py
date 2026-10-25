# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""Single-Instance-Lock (ADR-0010)."""
import os
import subprocess
import sys
import textwrap

from cwdecoder.instance_lock import InstanceLock, get_lock_path, pid_alive

ROOT = os.path.join(os.path.dirname(__file__), "..")


def _dead_pid():
    p = subprocess.Popen([sys.executable, "-c", "pass"])
    p.wait()
    return p.pid


def test_pid_alive():
    assert pid_alive(os.getpid())
    assert not pid_alive(_dead_pid())
    assert not pid_alive(0) and not pid_alive(-1)


def test_acquire_and_release(tmp_path):
    lock = InstanceLock(tmp_path / "sub" / "cwdecoder.lock")
    assert lock.acquire()
    assert lock.path.read_text(encoding="ascii") == str(os.getpid())
    lock.release()
    assert not lock.path.exists()
    lock.release()              # doppelt freigeben ist harmlos


def test_second_process_is_blocked(tmp_path):
    path = tmp_path / "cwdecoder.lock"
    holder = subprocess.Popen(
        [sys.executable, "-c", textwrap.dedent(f"""
            import sys, time
            sys.path.insert(0, {ROOT!r})
            from cwdecoder.instance_lock import InstanceLock
            lock = InstanceLock({str(path)!r})
            print(lock.acquire(), flush=True)
            sys.stdin.readline()
            lock.release()
        """)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    try:
        assert holder.stdout.readline().strip() == "True"
        other = InstanceLock(path)
        assert other.acquire() is False
        # unter Windows startet der venv-Python einen Kindprozess, daher nur
        # prüfen, dass es eine fremde PID ist
        assert other.other_pid not in (None, os.getpid())
        assert path.exists()
    finally:
        holder.communicate("\n", timeout=10)
    assert not path.exists()
    assert InstanceLock(path).acquire()


def test_stale_lock_is_taken_over(tmp_path):
    path = tmp_path / "cwdecoder.lock"
    path.write_text(str(_dead_pid()), encoding="ascii")
    lock = InstanceLock(path)
    assert lock.acquire()
    assert path.read_text(encoding="ascii") == str(os.getpid())
    lock.release()


def test_garbage_lock_is_taken_over(tmp_path):
    path = tmp_path / "cwdecoder.lock"
    path.write_text("kein PID", encoding="ascii")
    assert InstanceLock(path).acquire()


def test_release_keeps_foreign_lock(tmp_path):
    path = tmp_path / "cwdecoder.lock"
    lock = InstanceLock(path)
    assert lock.acquire()
    path.write_text("12345", encoding="ascii")   # jemand anderes hat übernommen
    lock.release()
    assert path.read_text(encoding="ascii") == "12345"


def test_context_manager(tmp_path):
    path = tmp_path / "cwdecoder.lock"
    with InstanceLock(path) as ok:
        assert ok and path.exists()
    assert not path.exists()


def test_default_lock_path_in_app_dir(app_env):
    p = get_lock_path()
    assert p.name == "cwdecoder.lock" and str(app_env) in str(p)

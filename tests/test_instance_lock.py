# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""Single-Instance-Lock (ADR-0010, gehärtet ADR-0020)."""
import os
import subprocess
import sys
import textwrap

from cwdecoder.instance_lock import (InstanceLock, get_lock_path, is_our_program,
                                     lock_holder_running, parse_lock, pid_alive)

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
    pid, start, exe = parse_lock(lock.path.read_text(encoding="utf-8"))
    assert pid == os.getpid() and exe
    if sys.platform == "win32":
        assert start and start > 0          # Startzeit des Prozesses (FILETIME)
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
    assert parse_lock(path.read_text(encoding="utf-8"))[0] == os.getpid()
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


# -- Härtung (ADR-0020): Fake-Prozesse über info_fn -----------------------
def _fake(info):
    return lambda pid: info.get(pid)


def test_parse_lock_formats():
    assert parse_lock("123") == (123, None, None)                 # altes Format
    assert parse_lock("123\n456\nCWDecoder.exe\n") == (123, 456, "CWDecoder.exe")
    assert parse_lock("123\n\npython.exe\n") == (123, None, "python.exe")
    assert parse_lock("Müll") == (None, None, None)


def test_is_our_program():
    assert is_our_program(r"C:\Program Files\CW Decoder Beta\CWDecoder.exe")
    assert is_our_program(r"C:\Python312\python.exe")
    assert is_our_program(r"C:\venv\Scripts\pythonw.exe")
    assert not is_our_program(r"C:\Windows\explorer.exe")
    assert not is_our_program(None)


def test_holder_running_needs_same_program_and_start():
    exe = r"C:\Prog\CWDecoder.exe"
    info = _fake({4711: (1000, exe)})
    assert lock_holder_running(4711, 1000, "CWDecoder.exe", info)
    assert not lock_holder_running(4711, 999, "CWDecoder.exe", info)      # PID neu vergeben
    assert not lock_holder_running(4712, 1000, "CWDecoder.exe", info)     # Prozess weg
    other = _fake({4711: (1000, r"C:\Windows\notepad.exe")})
    assert not lock_holder_running(4711, 1000, "CWDecoder.exe", other)    # fremdes Programm
    assert not lock_holder_running(4711, None, None, other)               # altes Format, fremd
    assert lock_holder_running(4711, None, None, info)                    # altes Format, unseres
    assert lock_holder_running(4711, 1000, "CWDecoder.exe", _fake({4711: (None, None)}))


def test_stale_lock_with_reused_pid_is_taken_over(tmp_path):
    path = tmp_path / "cwdecoder.lock"
    path.write_text("4711\n1000\nCWDecoder.exe\n", encoding="utf-8")
    reused = _fake({4711: (2000, r"C:\Windows\svchost.exe")})
    lock = InstanceLock(path, info_fn=reused)
    assert lock.acquire() and lock.other_pid is None
    assert parse_lock(path.read_text(encoding="utf-8"))[0] == os.getpid()
    lock.release()


def test_running_instance_blocks(tmp_path):
    path = tmp_path / "cwdecoder.lock"
    path.write_text("4711\n1000\nCWDecoder.exe\n", encoding="utf-8")
    alive = _fake({4711: (1000, r"C:\Prog\CWDecoder.exe")})
    lock = InstanceLock(path, info_fn=alive)
    assert lock.acquire() is False and lock.other_pid == 4711
    assert path.read_text(encoding="utf-8").startswith("4711")

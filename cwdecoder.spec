# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
# PyInstaller-Spec (ADR-0011): onedir-Bundle dist\CWDecoder\, Fensterprogramm
# ohne Konsole, 64 Bit. Bauen (siehe docs/BUILD.md):
#   python tools/make_icon.py
#   pyinstaller cwdecoder.spec
from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = [], [], []

# sounddevice lädt die PortAudio-DLL zur Laufzeit per ctypes aus dem Paket
# _sounddevice_data; das erkennt die Analyse nicht von selbst.
for pkg in ("sounddevice", "_sounddevice_data"):
    try:
        d, b, h = collect_all(pkg)
    except Exception:   # Paket fehlt (z. B. andere sounddevice-Version)
        continue
    datas += d
    binaries += b
    hiddenimports += h

# numpy und scipy bringen ihre Hooks mit (PyInstaller bzw. hooks-contrib).
# scipy.signal und scipy.io.wavfile laden einige Erweiterungen dynamisch.
hiddenimports += ["scipy.signal", "scipy.io.wavfile", "scipy.special._cdflib"]

a = Analysis(
    ["run_cwdecoder.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "PIL", "matplotlib", "IPython"],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="CWDecoder",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="assets/cwdecoder.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="CWDecoder",
)

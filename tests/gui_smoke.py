# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""GUI-Rauchtest ohne Audiogerät:  python tests/gui_smoke.py

Ersetzt sounddevice durch eine Fake-Soundkarte, die ein mit cwdecoder.gen
erzeugtes CW-Signal (8-fache Echtzeit) liefert, startet die echte
Tk-Oberfläche und klickt Start/Stop, Aufnahme, Spektrum-Klick, Automatik,
N1MM an/aus usw. durch. Jede Exception im Tk-Callback oder in einem Thread
zählt als Fehler. Braucht ein Display (unter Windows immer vorhanden), aber
keine Soundkarte. Aufnahmen landen in einem temporären Ordner.

Absichtlich nicht test_*.py: pytest soll ihn nicht ungefragt einsammeln.
"""
import gc
import os
import shutil
import sys
import tempfile
import threading
import time
import traceback
import types

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from cwdecoder.gen import render  # noqa: E402

TEXT = "CQ TEST DE DL1ABC DL1ABC K   "
SPEEDUP = 8.0


# --------------------------------------------------------------------------
def make_fake_sounddevice(ok_rate, with_input=True):
    """Attrappe für das sounddevice-Modul. Nur ok_rate lässt sich öffnen."""
    sig = {}
    fake = types.ModuleType("sounddevice")
    fake.default = types.SimpleNamespace(device=[1 if with_input else -1, 0])

    def query_devices():
        devs = [{"name": "Fake Out", "max_input_channels": 0}]
        if with_input:
            devs.append({"name": "Fake USB Audio", "max_input_channels": 1})
        return devs

    class InputStream:
        def __init__(self, device, channels, samplerate, blocksize, dtype, callback):
            if samplerate != ok_rate:
                raise RuntimeError(f"Invalid sample rate {samplerate}")
            if samplerate not in sig:
                sig[samplerate] = render(TEXT, fs=samplerate, wpm=25, snr_db=15, seed=1)
            self.fs, self.bs, self.cb = samplerate, blocksize, callback
            self.sig = sig[samplerate]
            self.running = False
            self.t = None

        def start(self):
            self.running = True
            self.t = threading.Thread(target=self._loop, daemon=True)
            self.t.start()

        def _loop(self):
            pos = 0
            while self.running:
                blk = self.sig[pos:pos + self.bs]
                if len(blk) < self.bs:
                    pos = 0
                    continue
                pos += self.bs
                self.cb(blk.reshape(-1, 1).astype(np.float32), self.bs, None, None)
                time.sleep(self.bs / self.fs / SPEEDUP)

        def stop(self):
            self.running = False
            if self.t:
                self.t.join()

        def close(self):
            pass

    fake.query_devices = query_devices
    fake.InputStream = InputStream
    return fake


# --------------------------------------------------------------------------
def run_scenario(ok_rate=48000, with_input=True, slow_recorder=False, n1mm=True):
    """Klickt die GUI durch. Liefert (Fehlerliste, Beobachtungen, Aufnahmen)."""
    sys.modules["sounddevice"] = make_fake_sounddevice(ok_rate, with_input)
    import cwdecoder.live as live
    from cwdecoder.gui import App

    orig_write = live.WavRecorder.write
    if slow_recorder:
        # langsame Platte: provoziert das Rennen Thread schreibt / Stop schließt
        def slow(self, block):
            time.sleep(0.03)
            orig_write(self, block)
        live.WavRecorder.write = slow

    errors, seen = [], {}
    old_hook = threading.excepthook
    threading.excepthook = lambda a: errors.append(
        "Thread: " + "".join(traceback.format_exception(a.exc_type, a.exc_value, a.exc_traceback)))
    rec_dir = tempfile.mkdtemp(prefix="cw_smoke_")

    app = App()
    app.rec_dir = rec_dir
    app.report_callback_exception = lambda *e: errors.append(
        "Tk: " + "".join(traceback.format_exception(*e)))

    def flag_of(parts):
        """ISO-Code des Flaggenbilds im Knopf, "" = Platzhalter, None = kein Bild."""
        if parts["flag"] is None:
            return None
        img = str(parts["flag"]["image"])
        return next((k for k, v in app._flag_cache.items() if k and str(v) == img), "")

    def snap(key):
        seen[key] = {"status": app.status.get(), "btn": str(app.btn_start["text"]),
                     "calls": list(app.calls), "text": app.text.get("1.0", "end"),
                     "dialogs": [(i.title, i.expected) for i in app.shown_errors],
                     "rows": {c: (flag_of(p), p["name"]["text"] if p["name"] else None)
                              for c, p in app.call_rows.items()}}

    steps = [
        (300, app._toggle),                                   # Start
        (1500, lambda: snap("läuft")),
        # Knöpfe mit Flagge (DL1ABC), ohne Flagge (Antarktis), ohne Land (#11)
        (10, lambda: (app._add_call("DP0GVN"), app._add_call("QQ1A"))),
        (50, lambda: snap("knöpfe")),
        (10, lambda: app.canvas.event_generate("<Button-1>", x=100, y=50)),
        (300, lambda: snap("fest")),
        (10, lambda: (app.auto_var.set(True), app._auto_changed())),
        (10, app._toggle),                                    # Stop
        (10, lambda: snap("gestoppt")),
        (10, lambda: app.rec_var.set(True)),
        (10, app._toggle),                                    # Start mit Aufnahme
        (600, lambda: snap("aufnahme")),
        (10, app._toggle),
        (10, lambda: snap("aufnahme gestoppt")),
        (10, app._toggle), (10, app._toggle),                 # sofort Start/Stop
    ] + [(5, app._toggle) for _ in range(6)] + [              # schnell toggeln
        (300, lambda: snap("nach schnell")),
    ]
    if n1mm:
        steps += [
            (10, lambda: (app.n1mm_var.set(True), app._n1mm_changed())),
            (10, lambda: app._send_call(app.calls[0]) if app.calls else None),
            (10, lambda: (app.n1mm_var.set(False), app._n1mm_changed())),
            (10, lambda: (app.n1mm_var.set(True), app._n1mm_changed())),
            (10, lambda: (app.n1mm_var.set(False), app._n1mm_changed())),
        ]
    steps += [(10, app._toggle), (200, app._quit)]           # Beenden während Lauf

    def run(i=0):
        if i >= len(steps):
            return
        delay, fn = steps[i]

        def go():
            try:
                fn()
            except Exception:  # noqa: BLE001
                errors.append(f"Schritt {i}: " + traceback.format_exc())
            run(i + 1)
        app.after(delay, go)

    run()
    app.mainloop()
    time.sleep(0.3)
    # Tk-Objekte des Fensters jetzt im Hauptthread abräumen: sonst kann die
    # zyklische Garbage Collection sie später in einem Hintergrund-Thread
    # des nächsten Szenarios löschen, und Tcl bricht ab
    # ("Tcl_AsyncDelete: async handler deleted by the wrong thread").
    del app, run, steps, snap
    gc.collect()
    threading.excepthook = old_hook
    live.WavRecorder.write = orig_write
    recs = sorted(os.listdir(rec_dir))
    shutil.rmtree(rec_dir, ignore_errors=True)
    return errors, seen, recs


# --------------------------------------------------------------------------
def check(cond, msg, problems):
    if not cond:
        problems.append(msg)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    failed = False
    cases = [
        ("48 kHz", dict(ok_rate=48000)),
        ("8 kHz", dict(ok_rate=8000)),
        ("44,1 kHz, langsame Aufnahme", dict(ok_rate=44100, slow_recorder=True)),
        ("Soundkarte öffnet nicht", dict(ok_rate=12345, n1mm=False)),
        ("kein Eingangsgerät", dict(with_input=False, n1mm=False)),
    ]
    for name, kw in cases:
        errors, seen, recs = run_scenario(**kw)
        problems = list(errors)
        unexpected = [t for st in seen.values() for t, ok in st["dialogs"] if not ok]
        check(not unexpected, f"Dialog 'Unerwarteter Fehler': {unexpected}", problems)
        if kw.get("ok_rate", 48000) == 12345:
            check("nicht geöffnet" in seen["läuft"]["status"],
                  f"keine Fehlermeldung in der Statuszeile: {seen['läuft']['status']!r}", problems)
            check(("Soundkarte nicht verfügbar", True) in seen["läuft"]["dialogs"],
                  f"kein Fehlerdialog zur Soundkarte: {seen['läuft']['dialogs']}", problems)
        elif not kw.get("with_input", True):
            check("kein Audio-Eingangsgerät" in seen["läuft"]["status"],
                  f"kein Hinweis auf fehlendes Gerät: {seen['läuft']['status']!r}", problems)
        else:
            check(seen["läuft"]["btn"] == "Stop", "Button zeigt nach Start nicht 'Stop'", problems)
            check("CQ TEST DE DL1ABC" in seen["läuft"]["text"],
                  f"Text nicht dekodiert: {seen['läuft']['text'][:60]!r}", problems)
            check("DL1ABC" in seen["läuft"]["calls"], "Rufzeichen DL1ABC nicht erkannt", problems)
            rows = seen["knöpfe"]["rows"]
            check(rows.get("DL1ABC") == ("de", "Deutschland"),
                  f"Knopf DL1ABC ohne Flagge/Land: {rows.get('DL1ABC')}", problems)
            check(rows.get("DP0GVN") == ("", "Antarktis"),
                  f"Knopf ohne Flagge falsch: {rows.get('DP0GVN')}", problems)
            check(rows.get("QQ1A") == (None, None),
                  f"Knopf ohne Land falsch: {rows.get('QQ1A')}", problems)
            check(seen["gestoppt"]["status"] == "gestoppt",
                  f"Status nach Stop: {seen['gestoppt']['status']!r}", problems)
            check("REC" in seen["aufnahme"]["status"], "Aufnahme nicht in der Statuszeile", problems)
            check(seen["aufnahme gestoppt"]["status"].startswith("gestoppt – Aufnahme gespeichert"),
                  f"Status nach Aufnahme-Stop: {seen['aufnahme gestoppt']['status']!r}", problems)
            # Starts mit Aufnahme: 1x normal, 1x sofort, 3x schnell, 1x vor Beenden
            wavs = [r for r in recs if r.endswith(".wav")]
            logs = [r for r in recs if r.endswith(".txt")]
            check(len(wavs) == 6 and len(recs) == 12,
                  f"erwartet 6 getrennte Aufnahmen, gefunden: {recs}", problems)
            # zu jeder Aufnahme ein Decodier-Log mit gleichem Namen (#10)
            check(sorted(w[:-4] for w in wavs) == sorted(t[:-4] for t in logs),
                  f"Decodier-Log fehlt: {recs}", problems)
        print(("ok  " if not problems else "FEHLER  ") + name)
        for p in problems:
            print("    " + p.replace("\n", "\n    "))
        failed |= bool(problems)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()

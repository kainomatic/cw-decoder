"""Live-Decoder: hört die Soundkarte ab und gibt den Text im Terminal aus.

    python -m cwdecoder.live --list                 Geräte anzeigen
    python -m cwdecoder.live --device 3             mit Gerät 3 starten
    python -m cwdecoder.live --device "USB Audio"   Gerät per Namensteil
    python -m cwdecoder.live --record qso.wav       Audio nebenbei aufzeichnen
    python -m cwdecoder.live --freq 650             feste Tonfrequenz

Strg+C beendet.
"""
import argparse
import queue
import sys
import threading
import time
import numpy as np

from . import utf8_console
from .decoder import CWDecoder, DecoderConfig
from .callsign import CallsignSpotter


def list_devices():
    import sounddevice as sd
    print(sd.query_devices())
    print("\nStandard-Eingang:", sd.default.device[0])


def pick_device(spec):
    import sounddevice as sd
    if spec is None:
        return None
    try:
        return int(spec)
    except ValueError:
        pass
    spec_l = spec.lower()
    for i, d in enumerate(sd.query_devices()):
        if d["max_input_channels"] > 0 and spec_l in d["name"].lower():
            return i
    raise SystemExit(f"Kein Eingabegerät mit '{spec}' gefunden (siehe --list)")


def open_stream(device, callback, preferred=(8000, 48000, 44100, 16000)):
    """Versucht die Soundkarte mit einer passenden Abtastrate zu öffnen."""
    import sounddevice as sd
    last = None
    for fs in preferred:
        try:
            s = sd.InputStream(device=device, channels=1, samplerate=fs,
                               blocksize=int(fs * 0.02), dtype="float32",
                               callback=callback)
            s.start()
            return s, fs
        except Exception as e:  # noqa: BLE001
            last = e
    raise SystemExit(f"Soundkarte konnte nicht geöffnet werden: {last}")


class LiveDecoder:
    def __init__(self, fs, cfg=None, on_text=None, on_status=None, on_call=None):
        self.q = queue.Queue()
        self.on_text = on_text or (lambda s: None)
        self.on_status = on_status or (lambda d: None)
        self.spotter = CallsignSpotter(on_call=on_call)
        self.dec = CWDecoder(fs, cfg, on_char=self._char, on_space=self._space)
        self.fs = fs
        self.running = False
        self.recorder = None

    def _char(self, ch):
        self.on_text(ch)
        self.spotter.feed(ch)

    def _space(self):
        self.on_text(" ")
        self.spotter.feed(" ")

    def audio_callback(self, indata, frames, t, status):
        if status:
            print(f"[audio] {status}", file=sys.stderr)
        self.q.put(indata[:, 0].copy())

    def run(self, status_interval=1.0):
        self.running = True
        last_status = 0.0
        while self.running:
            try:
                block = self.q.get(timeout=0.1)
            except queue.Empty:
                # auch ohne neue Daten Pausen auswerten (sollte nicht passieren)
                continue
            if self.recorder is not None:
                self.recorder.write(block)
            self.dec.process(block)
            now = time.time()
            if now - last_status >= status_interval:
                last_status = now
                self.on_status(self.dec.status)

    def stop(self):
        self.running = False


class WavRecorder:
    def __init__(self, path, fs):
        import wave
        self.w = wave.open(path, "wb")
        self.w.setnchannels(1)
        self.w.setsampwidth(2)
        self.w.setframerate(fs)

    def write(self, block):
        self.w.writeframes((np.clip(block, -1, 1) * 32767).astype(np.int16).tobytes())

    def close(self):
        self.w.close()


def main():
    utf8_console()
    p = argparse.ArgumentParser(description="CW Live-Decoder")
    p.add_argument("--list", action="store_true", help="Audiogeräte auflisten")
    p.add_argument("--device", default=None, help="Gerätenummer oder Namensteil")
    p.add_argument("--freq", type=float, default=None, help="feste Tonfrequenz (Hz)")
    p.add_argument("--fmin", type=float, default=300)
    p.add_argument("--fmax", type=float, default=1200)
    p.add_argument("--record", default=None, help="Audio in diese WAV-Datei mitschreiben")
    p.add_argument("--no-status", action="store_true")
    a = p.parse_args()

    if a.list:
        list_devices()
        return

    cfg = DecoderConfig()
    cfg.tracker.f_min, cfg.tracker.f_max = a.fmin, a.fmax
    if a.freq:
        cfg.tracker.fixed_freq = a.freq

    device = pick_device(a.device)

    state = {"fs": None, "live": None}

    def cb(indata, frames, t, status):
        if state["live"] is not None:
            state["live"].audio_callback(indata, frames, t, status)

    # Stream zuerst öffnen, damit die tatsächliche Abtastrate bekannt ist
    stream, fs = open_stream(device, cb)
    print(f"Eingang geöffnet mit {fs} Hz. Strg+C beendet.\n", file=sys.stderr)

    line = {"len": 0}

    def on_text(s):
        sys.stdout.write(s)
        sys.stdout.flush()
        line["len"] += len(s)
        if line["len"] > 70 and s == " ":
            sys.stdout.write("\n")
            line["len"] = 0

    def on_status(st):
        if a.no_status:
            return
        lock = "LOCK" if st["locked"] else "----"
        sys.stderr.write(f"\r[{lock} {st['freq_hz']:5.0f} Hz  {st['snr_db']:4.0f} dB  "
                         f"{st['wpm']:3.0f} WPM  BW {st['bw_hz']:3.0f} Hz]  ")
        sys.stderr.flush()

    def on_call(call):
        sys.stderr.write(f"\n[Rufzeichen: {call}]\n")

    live = LiveDecoder(fs, cfg, on_text=on_text, on_status=on_status, on_call=on_call)
    if a.record:
        live.recorder = WavRecorder(a.record, fs)
    state["live"] = live

    try:
        live.run()
    except KeyboardInterrupt:
        pass
    finally:
        stream.stop()
        stream.close()
        if live.recorder:
            live.recorder.close()
            print(f"\nAufnahme gespeichert: {a.record}", file=sys.stderr)
        print()


if __name__ == "__main__":
    main()

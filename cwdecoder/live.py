# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""Live-Decoder: hört die Soundkarte ab und gibt den Text im Terminal aus.

    python -m cwdecoder.live --list                 Geräte anzeigen
    python -m cwdecoder.live --device 3             mit Gerät 3 starten
    python -m cwdecoder.live --device "USB Audio"   Gerät per Namensteil
    python -m cwdecoder.live --record qso.wav       Audio nebenbei aufzeichnen
    python -m cwdecoder.live --freq 650             feste Tonfrequenz

Strg+C beendet.
"""
import argparse
import logging
import os
import queue
import sys
import threading
import time
import numpy as np

from . import utf8_console
from .decoder import CWDecoder, DecoderConfig, UNSURE_CONF
from .callsign import CallsignSpotter
from .segment import SEP as SEGMENT_SEP, WordBuffer
from .ringbuffer import AudioRing, TokenRing

log = logging.getLogger(__name__)

# Meldungen der Soundkarte (Überlauf o. ä.) höchstens so oft ins Log
AUDIO_WARN_INTERVAL_S = 5.0


def call_with_country(call: str) -> str:
    """"DJ7PR – Deutschland"; ohne bekannte Entität nur das Rufzeichen."""
    try:
        from .dxcc import lookup
        e = lookup(call)
    except (OSError, ValueError) as err:
        log.warning("DXCC-Daten nicht lesbar: %s", err)
        e = None
    return f"{call} – {e.short}" if e else call


class AudioDeviceError(RuntimeError):
    """Soundkarte lässt sich nicht öffnen (belegt, abgezogen, falsche Rate)."""


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
    raise AudioDeviceError(f"Kein Eingabegerät mit '{spec}' gefunden (siehe --list)")


def device_name(device):
    """Klarname eines Geräts für Log und Fehlerbericht (None = Standard)."""
    try:
        import sounddevice as sd
        idx = sd.default.device[0] if device is None else device
        return f"{idx}: {sd.query_devices(idx)['name']}"
    except Exception:  # noqa: BLE001
        return str(device)


def open_stream(device, callback, preferred=(8000, 48000, 44100, 16000)):
    """Versucht die Soundkarte mit einer passenden Abtastrate zu öffnen.

    Wirft AudioDeviceError, wenn keine der Raten klappt."""
    import sounddevice as sd
    last = None
    for fs in preferred:
        try:
            s = sd.InputStream(device=device, channels=1, samplerate=fs,
                               blocksize=int(fs * 0.02), dtype="float32",
                               callback=callback)
            s.start()
            log.info("Eingang geöffnet: Gerät %s, %d Hz", device_name(device), fs)
            return s, fs
        except Exception as e:  # noqa: BLE001
            log.debug("Gerät %s mit %d Hz nicht möglich: %s", device, fs, e)
            last = e
    log.error("Soundkarte %s konnte nicht geöffnet werden: %s", device_name(device), last)
    raise AudioDeviceError(f"Soundkarte konnte nicht geöffnet werden: {last}")


class LiveDecoder:
    def __init__(self, fs, cfg=None, on_text=None, on_status=None, on_call=None,
                 on_audio_warning=None, on_call_span=None, on_char_conf=None,
                 ring_seconds=None, on_segment=None, segment=True, scp="default"):
        self.q = queue.Queue()
        # Meldungen der Soundkarte; Terminal gibt sie auf stderr aus
        self.on_audio_warning = on_audio_warning
        self._last_audio_log = -AUDIO_WARN_INTERVAL_S
        self.on_text = on_text or (lambda s: None)
        self.on_status = on_status or (lambda d: None)
        # on_text bekommt jedes Zeichen einzeln (Prosigns als ein Stück),
        # dazu " " und eine Leerzeile als Absatz; on_call_span(call, start,
        # end) zählt nur die Zeichen ohne Leerzeichen/Absätze (Rufzeichen
        # im Text markieren). Mit on_char_conf(ch, conf) gehen die Zeichen
        # samt Vertrauen 0..1 dorthin statt an on_text (ADR-0023);
        # Leerzeichen und Absätze bleiben bei on_text
        self.on_char_conf = on_char_conf
        # Super Check Partial und Wörterbuch-Zerlegung (ADR-0026);
        # on_segment(cuts) kommt am Wortende vor dessen Leerzeichen
        if scp == "default":
            from .scp import DEFAULT as scp
        self.spotter = CallsignSpotter(on_call=on_call, on_span=on_call_span, scp=scp,
                                       segment=segment, on_segment=on_segment)
        self.dec = CWDecoder(fs, cfg, on_char=self._char, on_space=self._space,
                             on_paragraph=self._paragraph)
        self.fs = fs
        self.running = False
        self.recorder = None
        self.decode_log = None   # DecodeLog neben der Aufnahme (optional)
        # Ringpuffer der letzten Sekunden (ADR-0024); None = keiner (Terminal)
        self.ring = AudioRing(fs, ring_seconds) if ring_seconds else None
        self.token_ring = TokenRing(ring_seconds) if ring_seconds else None

    def _log(self, token, conf=None):
        t = self.dec.t_ms / 1000.0
        if self.decode_log is not None:
            self.decode_log.write(t, token, conf)
        if self.token_ring is not None:
            self.token_ring.add(t, token, conf)

    def feed(self, block):
        """Einen Block verarbeiten (Ring, Aufnahme, Decoder); Decoder-Thread."""
        if self.ring is not None:
            self.ring.write(block)
        if self.recorder is not None:
            self.recorder.write(block)
        self.dec.process(block)

    def _char(self, ch):
        conf = self.dec.last_conf      # vor on_char gesetzt
        if self.on_char_conf is not None:
            self.on_char_conf(ch, conf)
        else:
            self.on_text(ch)
        self.spotter.feed(ch)
        self._log(ch, conf)

    def _space(self):
        # Spotter zuerst: Zerlegung und Rufzeichen des Wortes kommen so vor
        # dem Leerzeichen an (Terminal und N1MM geben das Wort erst dann aus)
        self.spotter.feed(" ")
        self.on_text(" ")
        self._log(" ")

    def _paragraph(self):
        # Leerzeile im Textfenster; der Spotter sieht ein Wortende
        self.spotter.feed(" ")
        self.on_text("\n\n")
        self._log(DecodeLog.PARAGRAPH)

    def audio_callback(self, indata, frames, t, status):
        if status:
            if self.on_audio_warning is not None:
                self.on_audio_warning(str(status))
            now = time.monotonic()
            if now - self._last_audio_log >= AUDIO_WARN_INTERVAL_S:
                self._last_audio_log = now
                log.warning("Soundkarte meldet: %s", status)
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
            self.feed(block)
            now = time.time()
            if now - last_status >= status_interval:
                last_status = now
                self.on_status(self.dec.status)

    def stop(self):
        self.running = False


class DecodeLog:
    """Decodier-Log neben einer Aufnahme: je Zeichen eine Zeile
    `sekunde;zeichen;vertrauen` (Sekunde relativ zum Aufnahmebeginn,
    Vertrauen 0..1, beides mit 2 Nachkommastellen; ADR-0023). Wortabstand =
    Leerzeichen, Absatz = `¶`, beide ohne Vertrauen (dritte Spalte leer).
    Dient dazu, eine Stelle im Text der passenden Stelle in der WAV
    zuzuordnen. Zeit = Ausgabezeitpunkt des Zeichens (kurz nach dessen Ende).
    Logs von vor beta12 haben nur zwei Spalten.
    """
    PARAGRAPH = "¶"

    def __init__(self, path):
        self.f = open(path, "w", encoding="utf-8", newline="\n")

    def write(self, t_s: float, token: str, conf: float = None):
        c = "" if conf is None else f"{conf:.2f}"
        self.f.write(f"{t_s:.2f};{token};{c}\n")

    def close(self):
        self.f.close()


def decode_log_path(wav_path: str) -> str:
    """`…_217.wav` -> `…_217.txt`."""
    root, _ext = os.path.splitext(wav_path)
    return root + ".txt"


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
    from .logging_setup import install_exception_hooks, log_startup, setup_logging
    setup_logging()
    install_exception_hooks()
    log_startup("Live-Decoder (Terminal)")
    p = argparse.ArgumentParser(description="CW Live-Decoder")
    p.add_argument("--list", action="store_true", help="Audiogeräte auflisten")
    p.add_argument("--device", default=None, help="Gerätenummer oder Namensteil")
    p.add_argument("--freq", type=float, default=None, help="feste Tonfrequenz (Hz)")
    p.add_argument("--fmin", type=float, default=300)
    p.add_argument("--fmax", type=float, default=1200)
    p.add_argument("--record", default=None, help="Audio in diese WAV-Datei mitschreiben")
    p.add_argument("--no-status", action="store_true")
    p.add_argument("--no-segment", action="store_true",
                   help="zusammengeklebte Wörter nicht zerlegen (sonst Trenner ·)")
    a = p.parse_args()

    if a.list:
        list_devices()
        return

    cfg = DecoderConfig()
    cfg.tracker.f_min, cfg.tracker.f_max = a.fmin, a.fmax
    if a.freq:
        cfg.tracker.fixed_freq = a.freq

    try:
        device = pick_device(a.device)
        log.info("Gerät gewählt: %s", device_name(device))
    except AudioDeviceError as e:
        log.error("%s", e)
        raise SystemExit(str(e)) from None

    state = {"fs": None, "live": None}

    def cb(indata, frames, t, status):
        if state["live"] is not None:
            state["live"].audio_callback(indata, frames, t, status)

    # Stream zuerst öffnen, damit die tatsächliche Abtastrate bekannt ist
    try:
        stream, fs = open_stream(device, cb)
    except AudioDeviceError as e:
        raise SystemExit(str(e)) from None
    print(f"Eingang geöffnet mit {fs} Hz. Strg+C beendet.\n", file=sys.stderr)

    line = {"len": 0, "pos": 0}

    def write(s):
        sys.stdout.write(s)
        sys.stdout.flush()
        line["len"] += len(s)
        if line["len"] > 70 and s.endswith(" "):
            sys.stdout.write("\n")
            line["len"] = 0

    # Mit Zerlegung erscheint jedes Wort erst an seinem Ende, dann mit
    # Trennern · an den Zerlegestellen (ADR-0026)
    words = None if a.no_segment else WordBuffer(write, SEGMENT_SEP)

    def on_text(s):
        if words is None:
            write(s)
        elif s.strip():
            words.add(s, line["pos"])
            line["pos"] += 1
        else:
            words.end(s)

    def on_status(st):
        if a.no_status:
            return
        lock = "LOCK" if st["locked"] else "----"
        sys.stderr.write(f"\r[{lock} {st['freq_hz']:5.0f} Hz  {st['snr_db']:4.0f} dB  "
                         f"{st['wpm']:3.0f} WPM  BW {st['bw_hz']:3.0f} Hz]  ")
        sys.stderr.flush()

    def on_char_conf(ch, conf):
        # unsichere Zeichen klein (ADR-0023)
        on_text(ch.lower() if conf < UNSURE_CONF else ch)

    def on_call(call):
        sys.stderr.write(f"\n[Rufzeichen: {call_with_country(call)}]\n")

    live = LiveDecoder(fs, cfg, on_text=on_text, on_status=on_status, on_call=on_call,
                       on_audio_warning=lambda m: print(f"[audio] {m}", file=sys.stderr),
                       on_char_conf=on_char_conf, segment=not a.no_segment,
                       on_segment=words.cut if words is not None else None)
    if a.record:
        log.info("Aufnahme: %s", a.record)
        live.recorder = WavRecorder(a.record, fs)
        live.decode_log = DecodeLog(decode_log_path(a.record))
    state["live"] = live

    try:
        live.run()
    except KeyboardInterrupt:
        pass
    finally:
        log.info("Live-Decoder beendet")
        stream.stop()
        stream.close()
        if live.recorder:
            live.recorder.close()
            print(f"\nAufnahme gespeichert: {a.record}", file=sys.stderr)
        if live.decode_log:
            live.decode_log.close()
        if words is not None:
            words.end()
        print()


if __name__ == "__main__":
    main()

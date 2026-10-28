# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""Ringpuffer der letzten Sekunden Audio und Decoder-Ausgabe (ADR-0024).

AudioRing    die letzten `seconds` Sekunden Audio (float32, feste Größe).
             `write` läuft im Decoder-Thread (LiveDecoder.run), `snapshot`
             bzw. `last` aus jedem Thread; beides unter einem Lock.
TokenRing    die Decoder-Ausgaben `(t_s, token, conf)` im gleichen
             Zeitfenster; Zeit = Sekunden seit Decoderstart, wie im
             Decodier-Log (live.DecodeLog).
save_excerpt Ausschnitt als WAV plus Decodier-Log daneben schreiben
             (`…_letzte30s.wav` / `…_letzte30s.txt`).
save_clip    festgehaltenen Ausschnitt von „Nochmal hören“ ebenso
             schreiben (`…_festgehalten.wav`, #25).

Kein tk, damit alles direkt testbar ist.
"""
import collections
import os
import threading
import wave
from datetime import datetime

import numpy as np

PARAGRAPH = "¶"            # wie live.DecodeLog.PARAGRAPH


class SaveLastError(OSError):
    """Ausschnitt ließ sich nicht schreiben (Aufnahmen-Ordner nicht
    beschreibbar, Platte voll …)."""


class AudioRing:
    """Feste Kapazität `seconds·fs` Samples; Älteres wird überschrieben."""

    def __init__(self, fs: int, seconds: float):
        self.fs = int(fs)
        self.capacity = max(1, int(round(seconds * self.fs)))
        self._buf = np.zeros(self.capacity, dtype=np.float32)
        self._pos = 0          # nächste Schreibstelle
        self._total = 0        # insgesamt geschriebene Samples
        self._lock = threading.Lock()

    def write(self, block) -> None:
        """Block anhängen. Allokiert nichts (Kopie per Slice in den Puffer)."""
        n = len(block)
        if n == 0:
            return
        cap = self.capacity
        with self._lock:
            if n >= cap:
                # nur das Ende passt hinein
                self._buf[:] = block[n - cap:]
                self._pos = 0
            else:
                first = min(n, cap - self._pos)
                self._buf[self._pos:self._pos + first] = block[:first]
                if first < n:
                    self._buf[:n - first] = block[first:]
                self._pos = (self._pos + n) % cap
            self._total += n

    @property
    def duration_s(self) -> float:
        """So viele Sekunden stehen im Puffer."""
        with self._lock:
            return min(self._total, self.capacity) / self.fs

    @property
    def total_s(self) -> float:
        """Sekunden seit dem ersten write (Zeitbasis der Tokens)."""
        with self._lock:
            return self._total / self.fs

    def snapshot(self, seconds: float):
        """(Kopie der letzten `seconds` Sekunden, Endzeit in Sekunden seit
        Beginn). Liefert höchstens so viel, wie schon da ist."""
        with self._lock:
            n = min(int(round(seconds * self.fs)), self._total, self.capacity)
            out = np.empty(n, dtype=np.float32)
            start = (self._pos - n) % self.capacity
            first = min(n, self.capacity - start)
            out[:first] = self._buf[start:start + first]
            out[first:] = self._buf[:n - first]
            return out, self._total / self.fs

    def last(self, seconds: float) -> np.ndarray:
        return self.snapshot(seconds)[0]


class TokenRing:
    """Decoder-Ausgaben der letzten `seconds` Sekunden."""

    def __init__(self, seconds: float):
        self.seconds = float(seconds)
        self._items = collections.deque()
        self._lock = threading.Lock()

    def add(self, t_s: float, token: str, conf: float = None) -> None:
        with self._lock:
            self._items.append((float(t_s), token, conf))
            # Puffer etwas länger als das Audio halten: Zeichen werden erst
            # kurz nach ihrem Ende ausgegeben
            limit = t_s - self.seconds - 5.0
            while self._items and self._items[0][0] < limit:
                self._items.popleft()

    def window(self, t_start: float, t_end: float):
        """Tokens mit t_start <= t <= t_end, Zeit relativ zu t_start.

        Das erste Zeichen kann vor t_start begonnen haben (Ausgabe kommt erst
        nach dem Zeichenende); in der WAV steht es dann nur zum Teil."""
        with self._lock:
            return [(t - t_start, tok, c) for t, tok, c in self._items
                    if t_start <= t <= t_end]


HELD_SUFFIX = "festgehalten"


def excerpt_name(save_s: int, now: datetime = None, suffix: str = None) -> str:
    """`cw_JJJJMMTT_HHMMSS_NNN_letzte30s.wav` (Schema der Aufnahmen, ADR-0003);
    mit suffix `…_festgehalten.wav`."""
    now = now or datetime.now()
    tail = suffix if suffix else f"letzte{int(save_s)}s"
    return now.strftime("cw_%Y%m%d_%H%M%S_%f")[:-3] + f"_{tail}.wav"


def write_wav(path, samples, fs) -> None:
    """Mono, 16 Bit, wie live.WavRecorder."""
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(int(fs))
        w.writeframes((np.clip(samples, -1, 1) * 32767).astype(np.int16).tobytes())


def write_tokens(path, tokens) -> None:
    """Decodier-Log `sekunde;zeichen;vertrauen` (Format seit #18)."""
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for t, tok, conf in tokens:
            c = "" if conf is None else f"{conf:.2f}"
            f.write(f"{t:.2f};{tok};{c}\n")


def tokens_text(tokens) -> str:
    """Text aus den Tokens, wie ihn das Textfenster zeigt (Absatz = Leerzeile)."""
    return "".join("\n\n" if tok == PARAGRAPH else tok for _t, tok, _c in tokens)


def save_excerpt(directory, audio: AudioRing, tokens: TokenRing, save_s: float,
                 now: datetime = None):
    """Die letzten `save_s` Sekunden als WAV + TXT in `directory` schreiben.

    Liefert (Pfad der WAV, gespeicherte Sekunden). Wirft SaveLastError."""
    samples, t_end = audio.snapshot(save_s)
    secs = len(samples) / audio.fs
    t_start = t_end - secs
    toks = tokens.window(t_start, t_end) if tokens is not None else []
    return _write_pair(directory, excerpt_name(save_s, now), samples, audio.fs, toks), secs


def save_clip(directory, clip, now: datetime = None):
    """Festgehaltenen Ausschnitt (replay.HeldClip) als `…_festgehalten.wav`
    + TXT mit den Tokens seines Zeitfensters schreiben.

    Liefert (Pfad der WAV, Sekunden). Wirft SaveLastError."""
    name = excerpt_name(0, now, HELD_SUFFIX)
    return _write_pair(directory, name, clip.samples, clip.fs, clip.token_window()), clip.seconds


def _write_pair(directory, name, samples, fs, toks):
    try:
        os.makedirs(directory, exist_ok=True)
        wav = os.path.join(str(directory), name)
        write_wav(wav, samples, fs)
        write_tokens(os.path.splitext(wav)[0] + ".txt", toks)
    except OSError as e:
        raise SaveLastError(f"{directory}: {e}") from e
    return wav

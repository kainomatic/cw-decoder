# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""„Nochmal hören“: Ausschnitt aus dem Ringpuffer abspielen (ADR-0024).

prepare(samples, fs, slow)  Lautstärke angleichen, Ein-/Ausblenden, bei
                            slow=True auf 1/0,7 der Länge dehnen.
stretch(x, fs, rate)        Zeitdehnung ohne Tonhöhenänderung (WSOLA).
Player                      spielt in einem eigenen Thread über
                            sounddevice.OutputStream (Standard-Ausgabe).

Kein tk: Der Player meldet das Ende über `on_done(fehler_oder_None)`, die
GUI legt das in ihre Queue (ADR-0009).
"""
import logging
import threading

import numpy as np

log = logging.getLogger(__name__)

SLOW_RATE = 0.7             # „langsamer (0,7×)“
TARGET_PEAK = 0.5           # Spitzenpegel der Wiedergabe
MAX_GAIN = 30.0             # leise Eingänge höchstens so stark anheben
FADE_MS = 5.0               # gegen Knacken am Anfang/Ende
CHUNK_S = 0.05              # Blockgröße beim Schreiben (Abbruch-Latenz)
FALLBACK_RATES = (48000, 44100)


class ReplayError(RuntimeError):
    """Wiedergabe nicht möglich (kein Ausgabegerät, Gerät belegt …)."""


def stretch(x, fs, rate=SLOW_RATE, frame_ms=40.0, tol_ms=4.0):
    """`x` auf len(x)/rate Samples dehnen, Tonhöhe bleibt (WSOLA).

    Fenster mit 50 % Überlappung; jedes Fenster wird im Eingang ±tol_ms um
    seine Sollposition so verschoben, dass es am besten an das vorige
    anschließt. Bei einem getasteten Ton liegen die Sprünge damit phasenrichtig,
    und Tastpausen bleiben Pausen (nur 1/rate länger). tol_ms deckt eine
    Periode ab 250 Hz ab."""
    x = np.asarray(x, dtype=np.float32)
    n = max(2, int(fs * frame_ms / 1000.0) // 2 * 2)
    hs = n // 2
    ha = hs * rate
    tol = max(1, int(fs * tol_ms / 1000.0))
    n_out = int(len(x) / rate)
    win = (0.5 - 0.5 * np.cos(2 * np.pi * np.arange(n) / n)).astype(np.float32)
    xp = np.concatenate([np.zeros(tol, np.float32), x,
                         np.zeros(2 * n + 2 * tol, np.float32)])
    out = np.zeros(n_out + n, dtype=np.float32)
    prev = 0
    for k in range(n_out // hs + 1):
        nominal = min(int(k * ha), len(x))
        if k == 0:
            pos = nominal
        else:
            # natürliche Fortsetzung des vorigen Fensters
            target = xp[prev + tol + hs:prev + tol + hs + n]
            cand = xp[nominal:nominal + n + 2 * tol]
            pos = nominal - tol + int(np.argmax(np.correlate(cand, target, "valid")))
        out[k * hs:k * hs + n] += win * xp[pos + tol:pos + tol + n]
        prev = pos
    return out[:n_out]


def prepare(samples, fs, slow=False):
    """Ausschnitt für die Wiedergabe: optional gedehnt, Pegel angeglichen
    (Spitze TARGET_PEAK, höchstens MAX_GAIN), kurz ein- und ausgeblendet."""
    x = np.asarray(samples, dtype=np.float32)
    if slow and len(x):
        x = stretch(x, fs)
    peak = float(np.max(np.abs(x))) if len(x) else 0.0
    if peak > 0:
        x = x * min(TARGET_PEAK / peak, MAX_GAIN)
    else:
        x = x.copy()
    k = min(int(fs * FADE_MS / 1000.0), len(x) // 2)
    if k > 0:
        ramp = np.linspace(0.0, 1.0, k, dtype=np.float32)
        x[:k] *= ramp
        x[-k:] *= ramp[::-1]
    return x.astype(np.float32)


def _resample(x, fs, fs_new):
    from math import gcd
    from scipy.signal import resample_poly
    g = gcd(int(fs), int(fs_new))
    return resample_poly(x, int(fs_new) // g, int(fs) // g).astype(np.float32)


def open_output(samples, fs, sd=None):
    """OutputStream öffnen und starten; kann das Gerät `fs` nicht, wird auf
    48/44,1 kHz umgerechnet (gleiche Dauer und Tonhöhe). Liefert
    (Stream, Samples). Wirft ReplayError."""
    if sd is None:
        try:
            import sounddevice as sd
        except Exception as e:  # noqa: BLE001
            raise ReplayError(f"sounddevice nicht verfügbar: {e}") from e
    last = None
    for rate in (fs,) + tuple(r for r in FALLBACK_RATES if r != fs):
        try:
            s = sd.OutputStream(samplerate=rate, channels=1, dtype="float32")
            s.start()
        except Exception as e:  # noqa: BLE001 - PortAudioError u. a.
            log.debug("Ausgabe mit %d Hz nicht möglich: %s", rate, e)
            last = e
            continue
        data = samples if rate == fs else _resample(samples, fs, rate)
        log.info("Wiedergabe geöffnet: Standard-Ausgabe, %d Hz", rate)
        return s, data
    raise ReplayError(f"Ausgabegerät ließ sich nicht öffnen: {last}")


class Player:
    """Spielt einen Ausschnitt ab, immer nur einen zur Zeit."""

    def __init__(self, sd=None):
        self._sd = sd               # Tests geben eine Attrappe mit
        self._thread = None
        self._stop = threading.Event()

    @property
    def playing(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self, samples, fs, on_done=None, slow=False) -> bool:
        """Wiedergabe im Hintergrund starten (Aufbereitung mit prepare() im
        Thread). False, wenn schon eine läuft."""
        if self.playing:
            log.info("Wiedergabe läuft schon, zweiter Start abgelehnt")
            return False
        self._stop = threading.Event()
        data = np.array(samples, dtype=np.float32)      # eigene Kopie
        self._thread = threading.Thread(target=self._run, args=(data, int(fs), on_done,
                                                                self._stop, slow),
                                        daemon=True, name="replay")
        self._thread.start()
        return True

    @property
    def stop_requested(self) -> bool:
        """True, wenn die (letzte) Wiedergabe per stop() abgebrochen wurde."""
        return self._stop.is_set()

    def stop(self) -> None:
        self._stop.set()

    def join(self, timeout=None) -> None:
        if self._thread is not None:
            self._thread.join(timeout)

    def _run(self, data, fs, on_done, stop, slow=False):
        """Läuft im Wiedergabe-Thread: kein tk."""
        err = None
        stream = None
        try:
            data = prepare(data, fs, slow)
            stream, data = open_output(data, fs, self._sd)
            rate = stream.samplerate if hasattr(stream, "samplerate") else fs
            step = max(1, int(rate * CHUNK_S))
            for i in range(0, len(data), step):
                if stop.is_set():
                    break
                stream.write(data[i:i + step].reshape(-1, 1))
        except ReplayError as e:
            err = e
        except Exception as e:  # noqa: BLE001 - Gerät während der Wiedergabe weg
            err = ReplayError(str(e))
        finally:
            if stream is not None:
                try:
                    if stop.is_set():
                        stream.abort()
                    else:
                        stream.stop()       # wartet, bis alles gespielt ist
                    stream.close()
                except Exception as e:  # noqa: BLE001
                    log.debug("Ausgabe schließen: %s", e)
            if err is not None:
                log.warning("Wiedergabe abgebrochen: %s", err)
            if on_done is not None:
                on_done(err)

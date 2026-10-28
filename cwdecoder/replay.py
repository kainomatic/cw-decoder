# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""„Nochmal hören“: Ausschnitt aus dem Ringpuffer abspielen (ADR-0024).

prepare(samples, fs)        Lautstärke angleichen, Ein-/Ausblenden.
Stretcher                   Zeitdehnung ohne Tonhöhenänderung (WSOLA) als
                            Strom: je Block ein eigenes Tempo (Regler wirkt
                            mitten in der Wiedergabe).
stretch(x, fs, rate)        dasselbe in einem Stück, festes Tempo.
Player                      spielt in einem eigenen Thread über
                            sounddevice.OutputStream; Ausgabegerät per
                            Namensteil, Rückfall auf die Standard-Ausgabe.
ReplayHold                  Festhalten mit Verfall: derselbe Ausschnitt,
                            solange Strg+R innerhalb der Frist kommt.

Kein tk: Der Player meldet das Ende über `on_done(fehler_oder_None)`, die
GUI legt das in ihre Queue (ADR-0009). Das Tempo liest der Player je Block
über eine Funktion, die nur eine Zahl liefert.
"""
import logging
import threading
import time

import numpy as np

log = logging.getLogger(__name__)

SLOW_RATE = 0.7             # früher „langsamer (0,7×)“; Migration replay_slow
RATE_RANGE = (0.5, 1.0)     # Tempo-Regler
TARGET_PEAK = 0.5           # Spitzenpegel der Wiedergabe
MAX_GAIN = 30.0             # leise Eingänge höchstens so stark anheben
FADE_MS = 5.0               # gegen Knacken am Anfang/Ende
FRAME_MS = 40.0             # Fenster der Dehnung; ein Block = halbes Fenster
FALLBACK_RATES = (48000, 44100)


class ReplayError(RuntimeError):
    """Wiedergabe nicht möglich (kein Ausgabegerät, Gerät belegt …)."""


class OutputDeviceMissingError(ReplayError):
    """Gewähltes Ausgabegerät fehlt oder lässt sich nicht öffnen; die
    Wiedergabe lief über die Standard-Ausgabe."""


def clamp_rate(rate) -> float:
    lo, hi = RATE_RANGE
    try:
        r = float(rate)
    except (TypeError, ValueError):
        return hi
    return min(hi, max(lo, r))


class Stretcher:
    """WSOLA als Strom. `read(rate)` liefert den nächsten Block (halbes
    Fenster, der letzte kürzer, am Ende ein leeres Array); `rate` darf sich
    von Block zu Block ändern (1,0 = Original, 0,5 = halbes Tempo).

    Fenster mit 50 % Überlappung; jedes Fenster wird im Eingang ±tol_ms um
    seine Sollposition so verschoben, dass es am besten an das vorige
    anschließt. Bei einem getasteten Ton liegen die Sprünge damit
    phasenrichtig, Tastpausen bleiben Pausen (nur 1/rate länger), die
    Tonhöhe bleibt. Bei Tempo 1,0 wird das Original unverändert
    durchgereicht. tol_ms deckt eine Periode ab 250 Hz ab."""

    def __init__(self, x, fs, frame_ms=FRAME_MS, tol_ms=4.0):
        x = np.asarray(x, dtype=np.float32)
        self.n = n = max(2, int(fs * frame_ms / 1000.0) // 2 * 2)
        self.hs = hs = n // 2
        self.tol = tol = max(1, int(fs * tol_ms / 1000.0))
        self.length = len(x)
        # Eingang: tol Nullen für die Suche, hs Nullen, damit schon der erste
        # ausgegebene Block die volle Fenstersumme hat, Nullen am Ende
        self._xp = np.concatenate([np.zeros(tol + hs, np.float32), x,
                                   np.zeros(2 * n + 2 * tol, np.float32)])
        self._win = (0.5 - 0.5 * np.cos(2 * np.pi * np.arange(n) / n)).astype(np.float32)
        self._acc = np.zeros(n, dtype=np.float32)
        self._k = 0             # verarbeitete Fenster
        self._ipos = 0.0        # Sollposition des nächsten Fensters
        self._prev = 0          # Lage des vorigen Fensters
        self._consumed = 0.0    # Eingang (Samples), den die Ausgabe bisher abdeckt
        self.done = self.length == 0

    def _frame(self, rate):
        hs, n, tol, xp = self.hs, self.n, self.tol, self._xp
        if self._k == 0:
            pos = 0
        else:
            self._ipos += hs * rate
            if rate >= 1.0:
                pos = self._prev + hs            # Original: nahtlos weiter
                self._ipos = float(pos)
            else:
                nominal = min(int(round(self._ipos)), self.length + hs)
                target = xp[self._prev + tol + hs:self._prev + tol + hs + n]
                cand = xp[nominal:nominal + n + 2 * tol]
                pos = nominal - tol + int(np.argmax(np.correlate(cand, target, "valid")))
                pos = max(pos, 0)
        self._acc += self._win * xp[pos + tol:pos + tol + n]
        out = self._acc[:hs].copy()
        self._acc[:hs] = self._acc[hs:]
        self._acc[hs:] = 0.0
        self._prev = pos
        self._k += 1
        return out

    def read(self, rate=1.0) -> np.ndarray:
        if self.done:
            return np.zeros(0, dtype=np.float32)
        rate = clamp_rate(rate)
        if self._k == 0:
            self._frame(rate)                  # erster Block: nur Vorlauf
        out = self._frame(rate)
        step = self.hs * rate
        remaining = self.length - self._consumed
        if remaining <= step + 1e-9:
            out = out[:max(0, int(round(remaining / rate)))]
            self.done = True
        self._consumed += step
        return out


def stretch(x, fs, rate=SLOW_RATE, frame_ms=FRAME_MS, tol_ms=4.0):
    """`x` auf len(x)/rate Samples dehnen, Tonhöhe bleibt (WSOLA, festes Tempo)."""
    st = Stretcher(x, fs, frame_ms, tol_ms)
    parts = []
    while not st.done:
        parts.append(st.read(rate))
    return np.concatenate(parts) if parts else np.zeros(0, dtype=np.float32)


def prepare(samples, fs):
    """Ausschnitt für die Wiedergabe: Pegel angeglichen (Spitze TARGET_PEAK,
    höchstens MAX_GAIN), kurz ein- und ausgeblendet."""
    x = np.array(samples, dtype=np.float32)
    peak = float(np.max(np.abs(x))) if len(x) else 0.0
    if peak > 0:
        x = x * min(TARGET_PEAK / peak, MAX_GAIN)
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


def _sd(sd=None):
    if sd is not None:
        return sd
    try:
        import sounddevice
    except Exception as e:  # noqa: BLE001
        raise ReplayError(f"sounddevice nicht verfügbar: {e}") from e
    return sounddevice


def output_devices(sd=None):
    """Namen der Ausgabegeräte (für die Auswahl in den Einstellungen)."""
    try:
        devs = _sd(sd).query_devices()
    except Exception as e:  # noqa: BLE001 - dann eben nur „Standard“
        log.warning("Ausgabegeräte nicht abfragbar: %s", e)
        return []
    names = []
    for d in devs:
        name = d.get("name", "")
        if d.get("max_output_channels", 0) > 0 and name and name not in names:
            names.append(name)
    return names


def find_output(spec, sd=None):
    """Index des Ausgabegeräts, dessen Name `spec` enthält (Groß/klein egal),
    None für „Standard“. Wirft OutputDeviceMissingError, wenn keines passt
    (Gerät abgezogen, Name geändert)."""
    if not spec:
        return None
    s = spec.lower()
    for i, d in enumerate(_sd(sd).query_devices()):
        if d.get("max_output_channels", 0) > 0 and s in d.get("name", "").lower():
            return i
    raise OutputDeviceMissingError(f"Ausgabegerät „{spec}“ nicht gefunden")


def open_output(fs, sd=None, device=None):
    """OutputStream öffnen und starten; kann das Gerät `fs` nicht, wird
    48/44,1 kHz versucht. Liefert (Stream, Abtastrate). Wirft ReplayError."""
    sd = _sd(sd)
    last = None
    for rate in (fs,) + tuple(r for r in FALLBACK_RATES if r != fs):
        try:
            kw = {} if device is None else {"device": device}
            s = sd.OutputStream(samplerate=rate, channels=1, dtype="float32", **kw)
            s.start()
        except Exception as e:  # noqa: BLE001 - PortAudioError u. a.
            log.debug("Ausgabe %s mit %d Hz nicht möglich: %s", device, rate, e)
            last = e
            continue
        log.info("Wiedergabe geöffnet: %s, %d Hz",
                 "Standard-Ausgabe" if device is None else f"Gerät {device}", rate)
        return s, rate
    raise ReplayError(f"Ausgabegerät ließ sich nicht öffnen: {last}")


class Player:
    """Spielt einen Ausschnitt ab, immer nur einen zur Zeit."""

    def __init__(self, sd=None):
        self._sd = sd               # Tests geben eine Attrappe mit
        self._thread = None
        self._stop = threading.Event()
        # Ausgabegerät fehlte, Standard benutzt (OutputDeviceMissingError)
        self.fallback = None

    @property
    def playing(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self, samples, fs, on_done=None, rate=1.0, device=None) -> bool:
        """Wiedergabe im Hintergrund starten. `rate`: Zahl oder Funktion
        ohne Argumente, die je Block das Tempo liefert (0,5–1,0); `device`:
        Namensteil des Ausgabegeräts oder None. False, wenn schon eine läuft."""
        if self.playing:
            log.info("Wiedergabe läuft schon, zweiter Start abgelehnt")
            return False
        self._stop = threading.Event()
        self.fallback = None
        data = np.array(samples, dtype=np.float32)      # eigene Kopie
        rate_fn = rate if callable(rate) else (lambda r=rate: r)
        self._thread = threading.Thread(target=self._run,
                                        args=(data, int(fs), on_done, self._stop, rate_fn,
                                              device),
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

    def _open(self, fs, device):
        """Gewähltes Gerät, bei Fehler Standard-Ausgabe (merkt den Grund)."""
        if device:
            try:
                return open_output(fs, self._sd, find_output(device, self._sd))
            except ReplayError as e:
                self.fallback = (e if isinstance(e, OutputDeviceMissingError)
                                 else OutputDeviceMissingError(f"„{device}“: {e}"))
                log.warning("Ausgabegerät %r nicht nutzbar (%s), Standard-Ausgabe", device, e)
        return open_output(fs, self._sd, None)

    def _run(self, data, fs, on_done, stop, rate_fn, device=None):
        """Läuft im Wiedergabe-Thread: kein tk."""
        err = None
        stream = None
        try:
            data = prepare(data, fs)
            stream, out_fs = self._open(fs, device)
            if out_fs != fs:
                data = _resample(data, fs, out_fs)
            st = Stretcher(data, out_fs)
            while not st.done and not stop.is_set():
                block = st.read(rate_fn())
                if len(block):
                    stream.write(block.reshape(-1, 1))
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


class HeldClip:
    """Festgehaltener Ausschnitt: Audio, Abtastrate, Zeitfenster im
    Decoder-Lauf und der TokenRing für den Text dazu."""

    def __init__(self, samples, fs, t_end, tokens=None):
        self.samples = samples
        self.fs = int(fs)
        self.t_end = float(t_end)
        self.t_start = self.t_end - len(samples) / self.fs
        self.tokens = tokens

    @property
    def seconds(self) -> float:
        return len(self.samples) / self.fs

    def token_window(self):
        return self.tokens.window(self.t_start, self.t_end) if self.tokens is not None else []


class ReplayHold:
    """Festhalten mit Verfall (#25).

    grab() fasst die letzten Sekunden aus dem Ring – oder liefert den
    festgehaltenen Ausschnitt, solange er gilt: während der Wiedergabe und
    bis `hold_s` Sekunden nach deren Ende. Danach verfällt er, das nächste
    grab() fasst neu. Die Uhr ist austauschbar (Tests)."""

    def __init__(self, hold_s=5.0, clock=time.monotonic):
        self.hold_s = float(hold_s)
        self.clock = clock
        self.clip = None
        self.playing = False
        self._until = None

    def active(self) -> bool:
        if self.clip is None:
            return False
        return self.playing or (self._until is not None and self.clock() < self._until)

    def remaining(self) -> float:
        """Sekunden bis zum Verfall (während der Wiedergabe: die volle Frist)."""
        if not self.active():
            return 0.0
        return self.hold_s if self.playing else max(0.0, self._until - self.clock())

    def grab(self, ring, seconds, tokens=None):
        """(Ausschnitt, neu gefasst?) – None, wenn der Ring leer ist."""
        if self.active():
            return self.clip, False
        samples, t_end = ring.snapshot(seconds)          # Kopie, Ring läuft weiter
        if len(samples) == 0:
            self.clip = None
            return None, True
        self.clip = HeldClip(samples, ring.fs, t_end, tokens)
        self._until = None
        return self.clip, True

    def started(self) -> None:
        self.playing = True

    def finished(self) -> None:
        """Wiedergabe zu Ende (auch abgebrochen): Frist läuft ab jetzt."""
        self.playing = False
        if self.clip is not None:
            self._until = self.clock() + self.hold_s

    def expire_if_due(self) -> bool:
        """Verfallenen Ausschnitt verwerfen; True, wenn das gerade geschah."""
        if self.clip is not None and not self.active():
            self.clip = None
            self._until = None
            return True
        return False

    def release(self) -> None:
        self.clip = None
        self._until = None
        self.playing = False

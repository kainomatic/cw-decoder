# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""Signalverarbeitung: Tonverfolgung, Quadraturdetektor, adaptive Schwelle.

Alles arbeitet blockweise und mit internem Zustand, damit es sowohl offline
(ganze WAV-Datei) als auch live (kleine Soundkarten-Blöcke) identisch läuft.

Kette:
    Audio (fs, z. B. 8 kHz)
      -> ToneTracker     : findet und verfolgt die CW-Tonhöhe per FFT (Max-Hold)
      -> Envelope        : Mischen auf 0 Hz + Tiefpass => Hüllkurve des Tons
                           (sehr schmalbandig, deshalb wird das Rauschen stark
                           unterdrückt; Bandbreite skaliert mit Geschwindigkeit)
      -> Thresholder     : Rauschteppich/Peak-Verfolgung, Hysterese, Squelch,
                           Entprellung => Folge von (Ton an/aus, Dauer in ms)
"""
from dataclasses import dataclass, field
import numpy as np
from scipy.signal import butter, lfilter, lfilter_zi, firwin


# --------------------------------------------------------------------------
# Abtastraten-Umsetzung (z. B. 48 kHz -> 8 kHz) mit Zustand für Blockbetrieb
# --------------------------------------------------------------------------
class Decimator:
    def __init__(self, fs_in: int, fs_out: int = 8000):
        # ganzzahliger Faktor; bei 44.1 kHz wird intern mit 8820 Hz gearbeitet
        self.factor = max(1, int(fs_in // fs_out))
        self.fs_out = fs_in / self.factor
        if self.factor == 1:
            self.taps = None
            return
        # FIR-Tiefpass knapp unter der neuen Nyquist-Frequenz
        self.taps = firwin(numtaps=16 * self.factor + 1, cutoff=0.42 * fs_out, fs=fs_in)
        self.zi = np.zeros(len(self.taps) - 1)
        self.phase = 0  # Rest-Offset zwischen Blöcken

    def process(self, x: np.ndarray) -> np.ndarray:
        if self.taps is None:
            return x
        y, self.zi = lfilter(self.taps, [1.0], x, zi=self.zi)
        out = y[self.phase::self.factor]
        self.phase = (self.phase - len(x)) % self.factor
        return out


# --------------------------------------------------------------------------
# Tonverfolgung
# --------------------------------------------------------------------------
@dataclass
class TrackerConfig:
    f_min: float = 300.0        # Suchbereich für den CW-Ton
    f_max: float = 1200.0
    nfft: int = 1024            # 128 ms bei 8 kHz -> ~8 Hz Auflösung
    hop: int = 128              # Aktualisierung alle 16 ms
    hold_decay: float = 0.985   # Max-Hold-Abklingen pro Hop (überbrückt Pausen)
    min_peak_db: float = 8.0    # Peak muss so weit über dem Band-Median liegen
    # Ein CW-Ton ist eine schmale Linie. Rauschen durch ein schmales
    # Empfängerfilter (100-250 Hz) bildet dagegen einen breiten Buckel, der
    # über dem Band-Median liegt, aber keine Linie ist. Deshalb zusätzlich:
    # Peak muss gegenüber dem Umfeld in ±line_win_hz (ohne ±line_core_hz)
    # um min_line_db herausragen.
    min_line_db: float = 9.0
    line_core_hz: float = 20.0
    line_win_hz: float = 40.0
    line_off_db: float = 6.0        # Gate schließt erst unter diesem Wert ...
    line_off_s: float = 0.6         # ... und wenn das so lange anhält (Drift überbrücken)
    smooth: float = 0.25        # Nachführung der Frequenz (0..1, 1 = sofort)
    track_window_hz: float = 60.0   # im Lock: Peak-Suche nur in diesem Fenster
    switch_margin_db: float = 3.0   # andere Linie nur, wenn so viel stärker
    fixed_freq: float = None    # feste Frequenz statt Suche


class ToneTracker:
    """Findet die stärkste schmalbandige Linie im CW-Band und folgt ihr.

    Liefert die aktuelle Schätzung der Tonfrequenz und eine SNR-Angabe.
    Max-Hold mit Abklingen sorgt dafür, dass der Ton auch während der
    Tastpausen "im Gedächtnis" bleibt und nicht bei jedem Zeichenabstand
    verloren geht.
    """

    def __init__(self, fs: int, cfg: TrackerConfig = None):
        self.fs = fs
        self.cfg = cfg or TrackerConfig()
        c = self.cfg
        self.buf = np.zeros(c.nfft)
        self.pending = np.zeros(0)
        self.window = np.hanning(c.nfft)
        self.freqs = np.fft.rfftfreq(c.nfft, 1 / fs)
        self.band = (self.freqs >= c.f_min) & (self.freqs <= c.f_max)
        self.hold = np.zeros(self.band.sum())
        self.freq = c.fixed_freq if c.fixed_freq else 0.5 * (c.f_min + c.f_max)
        self.locked = bool(c.fixed_freq)
        self.peak_db = 0.0
        self.line_db = 0.0
        self.tone_present = False   # schmale Linie vorhanden (Squelch-Gate)
        self._weak_frames = 0
        self.spectrum_db = None  # für Anzeige

    def set_fixed(self, f: float = None):
        """Feste Frequenz setzen; None = zurück auf automatische Suche."""
        self.cfg.fixed_freq = f
        if f:
            self.freq = f
            self.locked = True
        else:
            # Automatik neu starten: Max-Hold leeren, damit nicht die alte
            # Linie weiter "nachhallt", und Lock aufheben
            self.locked = False
            self.hold[:] = 0.0

    def process(self, x: np.ndarray):
        c = self.cfg
        self.pending = np.concatenate([self.pending, x])
        while len(self.pending) >= c.hop:
            chunk, self.pending = self.pending[:c.hop], self.pending[c.hop:]
            self.buf = np.concatenate([self.buf[c.hop:], chunk])
            self._analyze()

    def _analyze(self):
        c = self.cfg
        spec = np.abs(np.fft.rfft(self.buf * self.window)) ** 2
        band = spec[self.band]
        self.hold = np.maximum(band, self.hold * c.hold_decay)
        hold_db = 10 * np.log10(self.hold + 1e-20)
        self.spectrum_db = hold_db
        med = np.median(hold_db)
        bf = self.freqs[self.band]
        k_glob = int(np.argmax(hold_db))
        if self.locked:
            # Im Fenster um die aktuelle Frequenz bleiben (folgt Drift); auf
            # eine andere Linie nur wechseln, wenn sie klar stärker ist
            win = np.abs(bf - self.freq) <= c.track_window_hz
            k_loc = int(np.argmax(np.where(win, hold_db, -np.inf)))
            if hold_db[k_glob] > hold_db[k_loc] + c.switch_margin_db:
                k = k_glob
            else:
                k = k_loc
        else:
            k = k_glob
        self.peak_db = float(hold_db[k] - med)
        ring = (np.abs(bf - bf[k]) >= c.line_core_hz) & (np.abs(bf - bf[k]) <= c.line_win_hz)
        self.line_db = float(hold_db[k] - np.median(hold_db[ring])) if ring.any() else self.peak_db
        if c.fixed_freq:
            # feste Frequenz: Linie dort beurteilen
            kf = int(np.argmin(np.abs(bf - c.fixed_freq)))
            ringf = (np.abs(bf - bf[kf]) >= c.line_core_hz) & (np.abs(bf - bf[kf]) <= c.line_win_hz)
            self.line_db = float(hold_db[kf] - np.median(hold_db[ringf])) if ringf.any() else 0.0
            self.tone_present = self.line_db >= c.min_line_db
            return
        weak = self.peak_db < c.min_peak_db or self.line_db < c.min_line_db
        if weak:
            # Gate mit Hysterese: Lock und Ton erst aufgeben, wenn die Linie
            # line_off_s lang unter line_off_db bleibt (Drift/QSB überbrücken)
            if self.line_db < c.line_off_db:
                self._weak_frames += 1
            else:
                self._weak_frames = 0
            if self._weak_frames * c.hop / self.fs >= c.line_off_s:
                self.tone_present = False
                self.locked = False
            return
        # Parabolische Interpolation für Sub-Bin-Genauigkeit
        if 0 < k < len(hold_db) - 1:
            a, b, g = hold_db[k - 1], hold_db[k], hold_db[k + 1]
            denom = (a - 2 * b + g)
            delta = 0.5 * (a - g) / denom if denom != 0 else 0.0
            delta = float(np.clip(delta, -1, 1))
        else:
            delta = 0.0
        f_peak = bf[k] + delta * (bf[1] - bf[0])
        self.tone_present = True
        self._weak_frames = 0
        if not self.locked:
            self.freq = f_peak
            self.locked = True
        else:
            # Wechsel auf eine andere Linie: sofort übernehmen, sonst weich
            # nachführen
            if abs(f_peak - self.freq) > c.track_window_hz:
                self.freq = f_peak
                self.hold[:] = 0.0   # Gedächtnis der alten Linie löschen
            else:
                self.freq += c.smooth * (f_peak - self.freq)


# --------------------------------------------------------------------------
# Hüllkurve per Quadraturmischer + Tiefpass
# --------------------------------------------------------------------------
class Envelope:
    """Mischt das Signal mit e^{-j2πft} auf 0 Hz und filtert tief.

    Das Ergebnis ist die Amplitude der Komponente bei f, mit einstellbarer
    Bandbreite. Die Hüllkurve wird auf env_rate (Standard 1 kHz, also
    1 ms Raster) dezimiert.
    """

    def __init__(self, fs: int, cutoff_hz: float = 50.0, env_rate: int = 1000):
        self.fs = fs
        self.dec = max(1, int(round(fs / env_rate)))
        self.env_rate = fs / self.dec
        self.phase = 0.0
        self.freq = 700.0
        self.cutoff = None
        self.last_r = 0.0
        self.last_i = 0.0
        self.set_cutoff(cutoff_hz)
        self.dec_phase = 0

    def set_cutoff(self, cutoff_hz: float):
        cutoff_hz = float(np.clip(cutoff_hz, 15.0, 250.0))
        if self.cutoff is not None and abs(cutoff_hz / self.cutoff - 1.0) < 0.15:
            return
        self.cutoff = cutoff_hz
        self.b, self.a = butter(3, cutoff_hz / (self.fs / 2))
        zi = lfilter_zi(self.b, self.a)
        # Filterzustand so setzen, dass der Ausgang stetig beim letzten Wert
        # weiterläuft (lfilter_zi liefert den Zustand für Gleichanteil 1)
        self.zi_r = zi * self.last_r
        self.zi_i = zi * self.last_i

    def process(self, x: np.ndarray, freq: float) -> np.ndarray:
        n = len(x)
        if n == 0:
            return np.zeros(0)
        # Phasenakkumulator, stetig auch bei Frequenzwechsel
        ph = self.phase + 2 * np.pi * freq / self.fs * np.arange(1, n + 1)
        self.phase = float(ph[-1] % (2 * np.pi))
        mixed_r = x * np.cos(ph)
        mixed_i = -x * np.sin(ph)
        yr, self.zi_r = lfilter(self.b, self.a, mixed_r, zi=self.zi_r)
        yi, self.zi_i = lfilter(self.b, self.a, mixed_i, zi=self.zi_i)
        self.last_r, self.last_i = float(yr[-1]), float(yi[-1])
        mag = np.sqrt(yr * yr + yi * yi) * 2.0
        out = mag[self.dec_phase::self.dec]
        self.dec_phase = (self.dec_phase - n) % self.dec
        return out


# --------------------------------------------------------------------------
# Adaptive Schwelle -> Tastereignisse
# --------------------------------------------------------------------------
@dataclass
class ThresholdConfig:
    peak_decay_db_s: float = 8.0      # Signalpegel-Schätzung fällt so schnell (Pause)
    peak_decay_on_db_s: float = 40.0  # ... bzw. so schnell während eines Tons (QSB)
    peak_attack: float = 0.08         # ... und steigt mit dieser Glättung (pro ms)
    on_frac: float = 0.65             # Einschaltschwelle zwischen Floor und Peak
    off_frac: float = 0.45            # Ausschaltschwelle (Hysterese)
    on_below_peak_db: float = 6.0     # ... aber höchstens so weit unter dem Signalpegel
    off_below_peak_db: float = 10.0
    min_snr_db: float = 10.0          # Squelch: darunter kein Ton
    # Zweites Squelch-Kriterium: Dynamik der Hüllkurve (98.–10. Perzentil)
    # über die letzten dyn_window_s. Getastetes CW hat > 22 dB, Rauschen
    # durch ein schmales Empfängerfilter nur ~15 dB (Rayleigh), obwohl es
    # nach einer "Linie" aussieht.
    min_dyn_db: float = 19.0
    dyn_window_s: float = 2.0
    debounce_ms: float = 4.0          # Grund-Entprellzeit (wird mit Punktlänge skaliert)
    smooth_ms: float = 2.0            # kurze Glättung der Hüllkurve


@dataclass
class KeyEvent:
    on: bool
    duration_ms: float
    t_ms: float      # Zeitstempel des Beginns


class Thresholder:
    """Verfolgt Rauschteppich und Signalpegel in dB und erzeugt Tastereignisse."""

    def __init__(self, env_rate: int = 1000, cfg: ThresholdConfig = None):
        self.rate = env_rate
        self.dt = 1000.0 / env_rate
        self.cfg = cfg or ThresholdConfig()
        self.floor_db = -60.0
        self.floor_lin = 1e-3
        self.peak_db = -50.0
        self.state = False
        self.run_ms = 0.0
        self.candidate = None   # (state, ms) für Entprellung
        self.t_ms = 0.0
        self.last_env_db = -60.0
        self.debounce_ms = self.cfg.debounce_ms
        self._sm = None
        self.snr_db = 0.0
        self.gate = True   # von außen: False = kein Ton vorhanden, Squelch zu
        self._ring = np.full(max(10, int(self.cfg.dyn_window_s * env_rate)), -60.0)
        self._ring_i = 0
        self._ring_filled = 0
        self._dyn_db = 0.0
        self._dyn_count = 0
        self._init = False
        self._warm = 0

    def set_debounce(self, ms: float):
        self.debounce_ms = float(np.clip(ms, 2.0, 40.0))

    def process(self, env: np.ndarray):
        """Liefert eine Liste abgeschlossener KeyEvents."""
        c = self.cfg
        events = []
        if len(env) == 0:
            return events
        # kurze Glättung (gleitender Mittelwert über smooth_ms)
        env_lin = np.asarray(env, dtype=float)
        k = max(1, int(round(c.smooth_ms / self.dt)))
        if k > 1:
            if self._sm is None:
                self._sm = np.full(k - 1, env_lin[0])
            buf = np.concatenate([self._sm, env_lin])
            env_lin = np.convolve(buf, np.ones(k) / k, mode="valid")
            self._sm = buf[-(k - 1):]
        env_db = 20 * np.log10(env_lin + 1e-9)

        decay_off = c.peak_decay_db_s * self.dt / 1000.0
        decay_on = c.peak_decay_on_db_s * self.dt / 1000.0
        # Rauschteppich wird im linearen Bereich als Mittelwert verfolgt
        # (im dB-Bereich würden die tiefen Einbrüche des Rauschens den
        # Schätzwert viel zu weit nach unten ziehen)
        a_dn = 0.02 * self.dt
        a_up_off = 0.006 * self.dt
        a_up_on = 0.00005 * self.dt   # während eines Tons praktisch eingefroren
        if not self._init:
            # Einschwingen des Filters abwarten, dann auf den Pegel setzen
            self._warm += len(env_db)
            if self._warm < 0.1 * self.rate:
                self.t_ms += len(env_db) * self.dt
                return events
            self.floor_lin = float(np.median(env_lin))
            self.floor_db = 20 * np.log10(self.floor_lin + 1e-9)
            self.peak_db = self.floor_db + 1.0
            self._init = True
        # Dynamik-Fenster blockweise füllen, Perzentile alle 100 ms
        n = len(env_db)
        idx = (self._ring_i + np.arange(n)) % len(self._ring)
        self._ring[idx] = env_db
        self._ring_i = (self._ring_i + n) % len(self._ring)
        self._ring_filled = min(len(self._ring), self._ring_filled + n)
        self._dyn_count += n
        if self._dyn_count >= 0.1 * self.rate:
            self._dyn_count = 0
            if self._ring_filled >= len(self._ring) // 2:
                # erst bewerten, wenn das Fenster mindestens halb voll ist
                r = self._ring if self._ring_filled == len(self._ring) else self._ring[:self._ring_filled]
                p10, p98 = np.percentile(r, [10, 98])
                self._dyn_db = float(p98 - p10)
        for e, el in zip(env_db, env_lin):
            if el < self.floor_lin:
                self.floor_lin += a_dn * (el - self.floor_lin)
            else:
                # Dauerträger (> 3 s am Stück) ist kein CW: dann darf der
                # Teppich auch bei "an" steigen, sonst bleibt er eingefroren
                a_up = a_up_off if (not self.state or self.run_ms > 3000.0) else a_up_on
                self.floor_lin += a_up * (el - self.floor_lin)
            self.floor_db = 20 * np.log10(self.floor_lin + 1e-9)
            # Signalpegel: zügig rauf, langsam runter
            if e > self.peak_db:
                self.peak_db += c.peak_attack * (e - self.peak_db)
            else:
                # Fading während der Tastung: schnell folgen; in Pausen halten
                self.peak_db -= decay_on if self.state else decay_off
            if self.peak_db < self.floor_db + 1.0:
                self.peak_db = self.floor_db + 1.0

            span = self.peak_db - self.floor_db
            self.snr_db = span
            squelch_open = self.gate and span >= c.min_snr_db and self._dyn_db >= c.min_dyn_db
            # Schwellen: nahe am Signalpegel (-6/-10 dB), bei schwachem
            # Signal aber mindestens als Bruchteil des Abstands zum Rauschen
            on_thr = max(self.peak_db - c.on_below_peak_db, self.floor_db + c.on_frac * span)
            off_thr = max(self.peak_db - c.off_below_peak_db, self.floor_db + c.off_frac * span)

            if not squelch_open:
                raw = False
            elif self.state:
                raw = e > off_thr
            else:
                raw = e > on_thr

            # Entprellung: Zustandswechsel erst, wenn er debounce_ms anhält
            if raw != self.state:
                if self.candidate is None:
                    self.candidate = self.dt
                else:
                    self.candidate += self.dt
                if self.candidate >= self.debounce_ms:
                    # Wechsel bestätigen; der Kandidat zählt zum neuen Zustand
                    dur = self.run_ms - self.candidate + self.dt
                    events.append(KeyEvent(self.state, max(dur, 0.0),
                                           self.t_ms - dur))
                    self.state = raw
                    self.run_ms = self.candidate - self.dt  # wird unten um dt erhöht
                    self.candidate = None
            else:
                self.candidate = None
            self.run_ms += self.dt
            self.t_ms += self.dt
            self.last_env_db = e
        return events

    def current_run_ms(self) -> float:
        return self.run_ms

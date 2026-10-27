# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""Komplette Decoder-Kette: Audio-Blöcke rein, Text raus."""
from dataclasses import dataclass, field
import numpy as np

from .dsp import (Decimator, ToneTracker, TrackerConfig, Envelope,
                  Thresholder, ThresholdConfig)
from .timing import TimingDecoder, TimingConfig

# Zeichen mit Vertrauen darunter gelten als unsicher (GUI grau, Terminal
# klein geschrieben; ADR-0023)
UNSURE_CONF = 0.5


def mark_unsure(chars, confs, thr: float = UNSURE_CONF) -> str:
    """Text aus Zeichen und Vertrauen; unsichere Zeichen klein geschrieben
    (Ziffern und Satzzeichen haben keine Kleinform und bleiben gleich).
    confs[i] None = kein Zeichen (Leerzeichen, Absatz)."""
    return "".join(ch.lower() if conf is not None and conf < thr else ch
                   for ch, conf in zip(chars, confs))


@dataclass
class DecoderConfig:
    fs_internal: int = 8000
    env_rate: int = 1000
    tracker: TrackerConfig = field(default_factory=TrackerConfig)
    threshold: ThresholdConfig = field(default_factory=ThresholdConfig)
    timing: TimingConfig = field(default_factory=TimingConfig)
    # Bandbreite des Detektors als Vielfaches von 1/Punktlänge. 0.6 bedeutet
    # bei 60 ms Punkt (20 WPM) eine Grenzfrequenz von 10 Hz ... das ist zu
    # träge; deshalb gilt zusätzlich eine Untergrenze.
    bw_factor: float = 1.5
    bw_min_hz: float = 25.0
    bw_max_hz: float = 150.0
    # Absatz im Live-Text nach so langer Pause (oder bei Tonverlust)
    paragraph_gap_ms: float = 3000.0
    # Vertrauen je Zeichen (ADR-0023): Abschlag bei geringem Pegelabstand.
    # Unter conf_snr_full_db (Thresholder.snr_db) sinkt der Faktor linear
    # bis conf_snr_min bei conf_snr_low_db (= Squelch-Schwelle)
    conf_snr_low_db: float = 10.0
    conf_snr_full_db: float = 16.0
    conf_snr_min: float = 0.7


class CWDecoder:
    """Verbindet alle Stufen. Aufruf: process(samples) beliebig oft.

    Callbacks:
        on_char(ch)     neues Zeichen (Buchstabe, Ziffer, '*' für unbekannt, <AR> usw.)
        on_space()      Wortende
        on_paragraph()  Absatz: Pause > paragraph_gap_ms oder Tonverlust, und
                        seit dem letzten Absatz kam Text (nur für die
                        Anzeige; get_text() enthält keine Absätze)
        on_char_conf(ch, conf)  zusätzlich zu on_char: dasselbe Zeichen mit
                        Vertrauen 0..1 (ADR-0023); last_conf ist schon vor
                        on_char gesetzt
    """

    def __init__(self, fs_in: int, cfg: DecoderConfig = None, on_char=None, on_space=None,
                 on_paragraph=None, on_char_conf=None):
        self.cfg = cfg or DecoderConfig()
        c = self.cfg
        self.fs_in = fs_in
        self.decim = Decimator(fs_in, c.fs_internal)
        self.fs = self.decim.fs_out
        self.tracker = ToneTracker(self.fs, c.tracker)
        self.envelope = Envelope(self.fs, cutoff_hz=50.0, env_rate=c.env_rate)
        self.thresh = Thresholder(self.envelope.env_rate, c.threshold)
        self.text = []
        self.confs = []          # Vertrauen je Eintrag in text (None = Leerzeichen)
        self.last_conf = 1.0     # Vertrauen des zuletzt ausgegebenen Zeichens
        self.t_ms = 0.0
        self._out_char = on_char or self._append_char
        self._out_char_conf = on_char_conf or (lambda ch, conf: None)
        self._out_space = on_space or self._append_space
        self._out_paragraph = on_paragraph or (lambda: None)
        self._since_paragraph = False   # Text seit dem letzten Absatz?
        self.timing = TimingDecoder(c.timing, on_char=self._on_char, on_space=self._out_space)
        self._update_bandwidth()

    # ------------------------------------------------------------------
    def _append_char(self, ch):
        self.text.append(ch)
        self.confs.append(self.last_conf)

    def _append_space(self):
        self.text.append(" ")
        self.confs.append(None)

    def char_confidence(self) -> float:
        """Vertrauen des gerade ausgegebenen Zeichens: Timing-Maß mal
        Pegel-Abschlag (ADR-0023). Beeinflusst die Decodierung nicht."""
        c = self.cfg
        conf = self.timing.last_conf
        span = c.conf_snr_full_db - c.conf_snr_low_db
        if span > 0:
            frac = float(np.clip((self.thresh.snr_db - c.conf_snr_low_db) / span, 0.0, 1.0))
            conf *= c.conf_snr_min + (1.0 - c.conf_snr_min) * frac
        return conf

    def _on_char(self, ch):
        self._since_paragraph = True
        self.last_conf = self.char_confidence()
        self._out_char(ch)
        self._out_char_conf(ch, self.last_conf)

    def _paragraph(self):
        if self._since_paragraph:
            self._since_paragraph = False
            self._out_paragraph()

    def _update_bandwidth(self):
        c = self.cfg
        dit = self.timing.dit_ms
        cutoff = c.bw_factor * 1000.0 / dit
        cutoff = float(np.clip(cutoff, c.bw_min_hz, c.bw_max_hz))
        if not self.tracker.locked and not self.cfg.tracker.fixed_freq:
            # Frequenz noch nicht gefunden: breiter hören, damit das erste
            # Element nicht verschluckt wird
            cutoff = max(cutoff, 80.0)
        self.envelope.set_cutoff(cutoff)
        self.thresh.set_debounce(max(3.0, 0.15 * dit))

    def set_fixed_frequency(self, f: float = None):
        self.tracker.set_fixed(f)
        self._update_bandwidth()

    # ------------------------------------------------------------------
    def process(self, samples: np.ndarray):
        x = np.asarray(samples, dtype=np.float64)
        if x.ndim > 1:
            x = x.mean(axis=1)
        x = self.decim.process(x)
        if len(x) == 0:
            return
        was_locked = self.tracker.locked
        gate_fs = self.tracker.process(x)
        if self.tracker.locked != was_locked:
            self._update_bandwidth()
        env = self.envelope.process(x, self.tracker.freq)
        # Gate auf das Hüllkurven-Raster bringen (hop-genau reicht)
        if len(env):
            pos = np.linspace(0, len(gate_fs) - 1, len(env)).astype(int)
            gate_env = gate_fs[pos]
        else:
            gate_env = gate_fs[:0]
        if self.thresh.gate and not self.tracker.tone_present:
            # Ton ist weg: laufendes Zeichen abschließen und das Tempo-
            # Gedächtnis verwerfen, damit die nächste Station frisch
            # eingemessen wird statt mit einem verschleppten Tempo
            self.timing.force_flush()
            self.timing.reset_tempo()
            self._update_bandwidth()
            self._paragraph()
        self.thresh.gate = self.tracker.tone_present
        events = self.thresh.process(env, gate_env)
        for ev in events:
            if ev.on:
                self.timing.mark(ev.duration_ms)
                self._update_bandwidth()
            else:
                self.timing.gap(ev.duration_ms)
        # Live-Ausgabe von Zeichen/Wortabstand während einer laufenden Pause
        if not self.thresh.state:
            self.timing.poll(self.thresh.current_run_ms())
            if self.thresh.current_run_ms() > self.cfg.paragraph_gap_ms:
                self._paragraph()
        self.t_ms += 1000.0 * len(x) / self.fs

    def flush(self):
        for ev in self.thresh.flush():
            if ev.on:
                self.timing.mark(ev.duration_ms)
            else:
                self.timing.gap(ev.duration_ms)
        self.timing.force_flush()

    # ------------------------------------------------------------------
    @property
    def status(self) -> dict:
        return {
            "freq_hz": self.tracker.freq,
            "locked": self.tracker.locked,
            "line_db": self.tracker.line_db,
            "peak_db": self.tracker.peak_db,
            "snr_db": self.thresh.snr_db,
            "wpm": self.timing.wpm,
            "dit_ms": self.timing.dit_ms,
            "key": self.thresh.state,
            "bw_hz": self.envelope.cutoff,
        }

    def get_text(self) -> str:
        return "".join(self.text)

    def get_text_marked(self) -> str:
        """Wie get_text(), unsichere Zeichen klein (Terminal, ADR-0023)."""
        return mark_unsure(self.text, self.confs)

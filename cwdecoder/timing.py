# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""Timing-Analyse: Punktlänge (Geschwindigkeit) schätzen, Elemente klassifizieren,
Zeichen und Wörter live ausgeben.

Kernidee gegenüber einfachen Decodern: Die Punktlänge wird nicht aus einem
einzelnen Element abgeleitet, sondern laufend aus einem Fenster der letzten
Ton- und Pausenlängen per Clusterung (Punkte/Striche bzw. Element-/Zeichen-
pausen) neu geschätzt. Dadurch rastet der Decoder innerhalb weniger Zeichen
auf die Gebegeschwindigkeit ein und folgt Tempowechseln, ohne bei einem
einzelnen verlängerten Strich oder einem kurzen Punkt aus dem Tritt zu
kommen.
"""
from collections import deque
from dataclasses import dataclass
import numpy as np

from .morse import decode_symbol


@dataclass
class TimingConfig:
    dit_min_ms: float = 12.0      # ~100 WPM
    dit_max_ms: float = 240.0     # ~5 WPM
    dash_thr: float = 2.0         # Ton länger als dash_thr * dit => Strich
    char_thr: float = 2.2         # Pause länger als char_thr * dit => Zeichenende
    word_thr: float = 5.0         # Pause länger als word_thr * dit => Wortende
    history: int = 24             # Fenster für die Geschwindigkeitsschätzung
    adapt: float = 0.35           # Nachführung der Punktlänge (0..1)
    initial_dit_ms: float = 60.0  # Startwert (20 WPM), bis genug Daten da sind


class TimingDecoder:
    def __init__(self, cfg: TimingConfig = None, on_char=None, on_space=None):
        self.cfg = cfg or TimingConfig()
        self.on_char = on_char or (lambda ch: None)
        self.on_space = on_space or (lambda: None)
        self.marks = deque(maxlen=self.cfg.history)
        self.gaps = deque(maxlen=self.cfg.history)
        self.char_gaps = deque(maxlen=12)   # Pausen zwischen Zeichen (für Farnsworth)
        self.word_thr_ms = self.cfg.word_thr * self.cfg.initial_dit_ms
        self.dit_ms = self.cfg.initial_dit_ms
        self._dash_thr_ms = None     # adaptive Strich-Schwelle (aus Clustern)
        self.confident = False
        self.symbol = ""           # aktuelle Punkt/Strich-Folge (Anzeige)
        self.cur_marks = []        # Tondauern des laufenden Zeichens
        self.char_emitted = True   # wurde das Zeichen für die aktuelle Pause schon ausgegeben?
        self.space_emitted = True
        self.n_marks = 0

    # ------------------------------------------------------------------
    @property
    def wpm(self) -> float:
        return 1200.0 / self.dit_ms

    def reset_text(self):
        self.symbol = ""
        self.cur_marks = []
        self.char_emitted = True
        self.space_emitted = True

    # ------------------------------------------------------------------
    def _estimate_dit(self) -> float:
        """Punktlänge aus den letzten Tönen und Pausen schätzen.

        Töne werden in Punkte/Striche geteilt: In logarithmischer Skala wird
        die sortierte Liste an der größten Lücke gespalten, wenn das
        Verhältnis der Cluster deutlich > 1 ist. Pausen innerhalb von Zeichen
        liefern eine zweite, unabhängige Schätzung der Punktlänge.
        """
        c = self.cfg
        est = []
        weights = []

        marks = np.array(self.marks, dtype=float)
        if len(marks) >= 2:
            s = np.sort(marks)
            ls = np.log(s)
            d = np.diff(ls)
            k = int(np.argmax(d))
            if d[k] > np.log(1.6) and k + 1 < len(s):
                lo, hi = s[:k + 1], s[k + 1:]
                dit_from_lo = np.median(lo)
                dit_from_hi = np.median(hi) / 3.0
                # beide Cluster müssen zueinander passen (Verhältnis ~3;
                # leichte/schwere Gewichtung liefert 2..4.5)
                ratio = np.median(hi) / dit_from_lo
                if 1.8 <= ratio <= 5.0:
                    est.append(0.5 * (dit_from_lo + dit_from_hi))
                    weights.append(2.0 + len(marks))
                    # Strich-Schwelle zwischen die Cluster legen (geometrisches
                    # Mittel), damit die Gewichtung des Gebers egal ist
                    self._dash_thr_ms = float(np.sqrt(np.median(lo) * np.median(hi)))
                elif ratio > 5.0:
                    # zu großer Abstand: eines der Cluster passt nicht zum CW.
                    # Das kleinere Cluster ist meist die Störung (kurze
                    # Rauschimpulse bzw. ein einzelner langer Träger)
                    if len(lo) < len(hi):
                        est.append(dit_from_hi)
                        weights.append(1.0 + len(hi))
                    else:
                        est.append(dit_from_lo)
                        weights.append(1.0 + len(lo))
                else:
                    est.append(dit_from_lo)
                    weights.append(1.0)
            else:
                # nur ein Cluster: alles Punkte oder alles Striche?
                m = float(np.median(s))
                gaps = np.array(self.gaps, dtype=float)
                if len(gaps) >= 1:
                    g = float(np.median(gaps))
                    # Elementpausen ~ Punkt. Wenn Töne ~ Pausen -> Punkte,
                    # wenn Töne ~ 3x Pausen -> Striche.
                    if m > 2.2 * g:
                        est.append(m / 3.0)
                    else:
                        est.append(m)
                    weights.append(1.0 + len(marks))
                else:
                    # ohne Pauseninfo: eher Punkt annehmen, wenn nah am
                    # bisherigen Wert, sonst Strich
                    if m > 2.0 * self.dit_ms:
                        est.append(m / 3.0)
                    else:
                        est.append(m)
                    weights.append(1.0)

        gaps = np.array(self.gaps, dtype=float)
        if len(gaps) >= 2:
            # Elementpausen = kürzestes Cluster der Pausen
            s = np.sort(gaps)
            ls = np.log(s)
            d = np.diff(ls)
            k = int(np.argmax(d))
            lo = s[:k + 1] if d[k] > np.log(1.7) else s
            est.append(float(np.median(lo)))
            weights.append(1.0 + 0.5 * len(lo))

        if not est:
            return self.dit_ms
        est = np.array(est)
        weights = np.array(weights)
        val = float(np.exp(np.sum(weights * np.log(est)) / np.sum(weights)))
        return float(np.clip(val, c.dit_min_ms, c.dit_max_ms))

    # ------------------------------------------------------------------
    def mark(self, duration_ms: float):
        """Ein Ton (Tastung an) ist zu Ende."""
        c = self.cfg
        if duration_ms < c.dit_min_ms * 0.5:
            return  # Störimpuls
        if self.confident and duration_ms < 0.35 * self.dit_ms:
            return  # viel kürzer als ein Punkt beim aktuellen Tempo: Rauschen
        # Plausibilität: extrem lange Töne (Träger, Störung) nicht lernen
        if duration_ms > 12 * c.dit_max_ms:
            self.symbol = ""
            self.cur_marks = []
            return
        self.marks.append(duration_ms)
        self.n_marks += 1
        new = self._estimate_dit()
        a = c.adapt if self.n_marks > 4 else 0.7
        self.dit_ms = float(np.exp(np.log(self.dit_ms) + a * (np.log(new) - np.log(self.dit_ms))))
        self.confident = self.n_marks >= 4
        # Die Elemente des laufenden Zeichens werden erst beim Zeichenende
        # klassifiziert (siehe _flush), damit die bis dahin verbesserte
        # Tempo-Schätzung auch für die ersten Elemente gilt (Issue #5)
        self.cur_marks.append(duration_ms)
        self.symbol = self._classify(self.cur_marks)
        self.char_emitted = False
        self.space_emitted = False

    def _dash_threshold(self) -> float:
        thr = self.cfg.dash_thr * self.dit_ms
        if self._dash_thr_ms is not None:
            # adaptiv, aber in sinnvollen Grenzen um die feste Schwelle
            thr = float(np.clip(self._dash_thr_ms, 1.4 * self.dit_ms, 2.6 * self.dit_ms))
        return thr

    def _classify(self, marks) -> str:
        thr = self._dash_threshold()
        return "".join("." if m < thr else "-" for m in marks)

    def gap(self, duration_ms: float):
        """Eine Pause (Tastung aus) ist zu Ende, weil ein neuer Ton beginnt."""
        c = self.cfg
        if duration_ms < c.dit_min_ms * 0.5:
            return
        if duration_ms < c.char_thr * self.dit_ms:
            self.gaps.append(duration_ms)
            return
        # Zeichen-/Wortende; falls per Timeout noch nicht ausgegeben:
        self._flush(duration_ms)
        if duration_ms < 12 * self.dit_ms:
            self.char_gaps.append(duration_ms)
            self._update_word_threshold()

    def _update_word_threshold(self):
        """Wortschwelle aus den beobachteten Zeichen-/Wortpausen ableiten.

        Normal: Zeichenpause 3 Punkte, Wortpause 7 -> Schwelle 5 Punkte.
        Bei Farnsworth/gedehnten Abständen sind die Zeichenpausen länger;
        dann wird die Schwelle über das untere Pausen-Cluster gelegt.
        """
        c = self.cfg
        base = c.word_thr * self.dit_ms
        g = np.sort(np.array(self.char_gaps, dtype=float))
        if len(g) < 3:
            self.word_thr_ms = base
            return
        lg = np.log(g)
        d = np.diff(lg)
        k = int(np.argmax(d))
        if d[k] > np.log(1.6):
            lo, hi = g[:k + 1], g[k + 1:]
            thr = float(np.sqrt(np.median(lo) * np.median(hi)))
        else:
            # nur ein Cluster -> das sind Zeichenpausen; Wortpause ist länger
            thr = float(np.median(g)) * 1.7
        self.word_thr_ms = max(base, thr)

    def poll(self, gap_so_far_ms: float):
        """Wird regelmäßig aufgerufen, solange kein Ton anliegt (Live-Ausgabe
        ohne auf den nächsten Ton zu warten)."""
        self._flush(gap_so_far_ms)

    def _flush(self, gap_ms: float):
        c = self.cfg
        if not self.char_emitted and gap_ms >= c.char_thr * self.dit_ms:
            self.symbol = self._classify(self.cur_marks)
            ch = decode_symbol(self.symbol)
            self.symbol = ""
            self.cur_marks = []
            self.char_emitted = True
            if ch:
                self.on_char(ch)
        if not self.space_emitted and gap_ms >= max(self.word_thr_ms, c.word_thr * self.dit_ms):
            self.space_emitted = True
            self.on_space()

    def force_flush(self):
        """Am Ende einer Datei alles ausgeben."""
        self._flush(1e9)

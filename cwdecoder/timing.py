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


# Tempo-Suchbereich. Punktlänge in ms = 1200 / WPM. Schneller als 60 WPM
# gibt niemand; die Grenzen dienen nur der Robustheit gegen Störimpulse
# und Träger.
DIT_MIN_MS = 20.0   # 60 WPM
DIT_MAX_MS = 240.0  # 5 WPM


@dataclass
class TimingConfig:
    dit_min_ms: float = DIT_MIN_MS
    dit_max_ms: float = DIT_MAX_MS
    dash_thr: float = 2.0         # Ton länger als dash_thr * dit => Strich
    char_thr: float = 2.2         # Pause länger als char_thr * dit => Zeichenende
    # Adaptive Zeichenschwelle (ADR-0025): Die Pausen des laufenden Verkehrs
    # werden in Element- und Zeichenpausen geclustert, die Schwelle liegt
    # geometrisch dazwischen, geklemmt auf char_thr_min..max Punkte. Zu
    # wenige Daten oder nur ein Cluster: feste Schwelle char_thr
    char_thr_adaptive: bool = True
    char_thr_min: float = 1.0
    char_thr_max: float = 3.0
    # ... und nie unter diesem Vielfachen der Punktlänge, die die Töne des
    # laufenden Zeichens zeigen (Schutz bei Stationswechsel, solange das
    # Fenster noch die Pausen der vorigen Station enthält)
    char_thr_dot_floor: float = 1.2
    # Mindestverhältnis der Cluster-Mediane Zeichen-/Elementpause
    char_cluster_ratio: float = 1.4
    # Ergibt ein Symbol kein gültiges Zeichen ('*'), an seiner längsten
    # inneren Pause trennen, wenn diese mindestens char_split_ratio mal so
    # lang ist wie der Median der übrigen und beide Teile gültig sind
    # (Stationswechsel, bevor die Zeichenschwelle nachgelernt hat)
    char_split: bool = True
    char_split_ratio: float = 1.5
    word_thr: float = 5.0         # Pause länger als word_thr * dit => Wortende
    history: int = 24             # Fenster für die Geschwindigkeitsschätzung
    adapt: float = 0.5            # Nachführung der Punktlänge (0..1)
    initial_dit_ms: float = 60.0  # Startwert (20 WPM), bis genug Daten da sind
    # Vertrauen je Zeichen (ADR-0023), nur Metadaten, ändert keine Entscheidung:
    # Ein Element ist voll sicher, wenn seine Länge mindestens um diesen
    # Faktor von der Strich-Schwelle entfernt ist (log. Abstand)
    conf_margin_ref: float = 1.6
    # Tempo noch nicht eingemessen: so viele Töne seit reset_tempo vor dem
    # Zeichen, bis kein Abschlag mehr gilt; Faktor beim ersten Zeichen
    conf_warmup_marks: int = 8
    conf_warmup_min: float = 0.6


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
        self.all_gaps = deque(maxlen=self.cfg.history)  # Element- und Zeichenpausen
        self._char_thr_ms = None     # adaptive Zeichenschwelle (aus Clustern)
        self.confident = False
        self.symbol = ""           # aktuelle Punkt/Strich-Folge (Anzeige)
        self.cur_marks = []        # Tondauern des laufenden Zeichens
        self.cur_gaps = []         # Pausen zwischen diesen Tönen
        self._dropped_ms = 0.0     # zuletzt verworfener Störimpuls
        self.char_emitted = True   # wurde das Zeichen für die aktuelle Pause schon ausgegeben?
        self.space_emitted = True
        self.n_marks = 0
        self.last_conf = 1.0       # Vertrauen des zuletzt ausgegebenen Zeichens

    # ------------------------------------------------------------------
    @property
    def wpm(self) -> float:
        return 1200.0 / self.dit_ms

    def reset_tempo(self):
        """Tempo-Gedächtnis verwerfen (z. B. wenn der Ton weg war).

        dit_ms bleibt als Startwert, aber die nächsten Elemente ziehen die
        Schätzung wieder schnell nach (wie am Anfang).
        """
        self.marks.clear()
        self.gaps.clear()
        self.char_gaps.clear()
        self.all_gaps.clear()
        self._dash_thr_ms = None
        self._char_thr_ms = None
        self.n_marks = 0
        self.confident = False
        self.dit_ms = float(np.clip(self.dit_ms, 30.0, 150.0))  # 8..40 WPM als Start

    def reset_text(self):
        self.symbol = ""
        self.cur_marks = []
        self.cur_gaps = []
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
        # Ausreißer abtrennen (Störimpulse, verschliffene Elemente, Träger):
        # Teilt die sortierten Längen an der größten Lücke; ist das kleinere
        # Teilcluster winzig (< 2 Werte bzw. < 20 %) oder das Verhältnis
        # unplausibel (> 5), fliegt es raus. Höchstens dreimal.
        for _ in range(3):
            if len(marks) < 4:
                break
            s_ = np.sort(marks)
            d_ = np.diff(np.log(s_))
            k_ = int(np.argmax(d_))
            if d_[k_] <= np.log(1.6):
                break
            lo_, hi_ = s_[:k_ + 1], s_[k_ + 1:]
            small, big = (lo_, hi_) if len(lo_) <= len(hi_) else (hi_, lo_)
            tiny = len(small) < max(2, 0.2 * len(marks))
            # Ausnahme: Sind die neuesten Elemente alle im kleinen Cluster,
            # ist das kein Ausreißer, sondern ein Tempowechsel
            recent = np.array(list(self.marks)[-3:], dtype=float)
            if len(recent) == 3 and np.all((recent >= small.min()) & (recent <= small.max())):
                break
            if tiny or np.median(hi_) / np.median(lo_) > 5.0:
                marks = big
            else:
                break
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
        if duration_ms < max(c.dit_min_ms * 0.5, 0.3 * self.dit_ms):
            self._dropped_ms = duration_ms
            return  # Störimpuls: viel kürzer als ein Punkt beim aktuellen Tempo
        # Plausibilität: extrem lange Töne (Träger, Störung) nicht lernen
        if duration_ms > 12 * c.dit_max_ms:
            self.symbol = ""
            self.cur_marks = []
            self.cur_gaps = []
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

    def confidence(self, marks, ch: str) -> float:
        """Vertrauen 0..1 in ein Zeichen aus seinen Tondauern (ADR-0023).

        Hauptmaß ist der kleinste logarithmische Abstand eines Elements zur
        Strich-Schwelle (knapp an der Schwelle = unsicher). Solange das Tempo
        nach reset_tempo noch nicht eingemessen ist, gilt ein Abschlag.
        Unbekannte Symbole ('*') haben 0. Liest nur, ändert keinen Zustand.
        """
        c = self.cfg
        if not marks or ch == "*":
            return 0.0
        thr = self._dash_threshold()
        dist = min(abs(np.log(m / thr)) for m in marks)
        conf = float(np.clip(dist / np.log(c.conf_margin_ref), 0.0, 1.0))
        prior = self.n_marks - len(marks)   # Töne vor diesem Zeichen
        if c.conf_warmup_marks > 0 and prior < c.conf_warmup_marks:
            frac = max(prior, 0) / c.conf_warmup_marks
            conf *= c.conf_warmup_min + (1.0 - c.conf_warmup_min) * frac
        return conf

    def gap(self, duration_ms: float):
        """Eine Pause (Tastung aus) ist zu Ende, weil ein neuer Ton beginnt."""
        c = self.cfg
        if duration_ms < c.dit_min_ms * 0.5:
            return
        # erst mit der bisherigen Schwelle entscheiden (dieselbe, mit der
        # poll() in dieser Pause schon ausgegeben haben kann), dann lernen
        char_thr = self._char_threshold()
        if duration_ms < self._word_threshold():
            self.all_gaps.append(duration_ms)
            self._update_char_threshold()
        if duration_ms < char_thr:
            self.gaps.append(duration_ms)
            if self.cur_marks:
                if len(self.cur_gaps) == len(self.cur_marks):
                    # Pause nach einem verworfenen Störimpuls: zählt mit ihm
                    # und der Pause davor als eine Pause
                    self.cur_gaps[-1] += self._dropped_ms + duration_ms
                else:
                    self.cur_gaps.append(duration_ms)
            return
        # Zeichen-/Wortende; falls per Timeout noch nicht ausgegeben:
        self._flush(duration_ms, char_thr)
        if duration_ms < 12 * self.dit_ms:
            self.char_gaps.append(duration_ms)
            self._update_word_threshold()

    def _char_threshold(self) -> float:
        c = self.cfg
        if c.char_thr_adaptive and self._char_thr_ms is not None:
            thr = self._char_thr_ms
            if self.cur_marks:
                dash = self._dash_threshold()
                dot = min(m if m < dash else m / 3.0 for m in self.cur_marks)
                thr = max(thr, c.char_thr_dot_floor * dot)
            return float(np.clip(thr, c.char_thr_min * self.dit_ms,
                                 c.char_thr_max * self.dit_ms))
        return c.char_thr * self.dit_ms

    def _word_threshold(self) -> float:
        # nie unter der Zeichenschwelle (bei den Grenzen oben ohnehin nicht)
        return max(self.word_thr_ms, self.cfg.word_thr * self.dit_ms,
                   self._char_threshold())

    def _update_char_threshold(self):
        """Zeichenschwelle aus den Pausen des laufenden Verkehrs (ADR-0025).

        Die Pausen zwischen 0,5 Punkt und der Wortschwelle werden im
        log-Bereich in zwei Cluster geteilt (kleinste Streuung innerhalb der
        Cluster, Otsu), nur an Stellen mit einer echten Lücke (Faktor 1,3).
        Gültig nur mit mindestens 8 Pausen, je 3 pro Cluster, Mediane im
        Verhältnis >= char_cluster_ratio und einem unteren Cluster, das nach
        Elementpausen aussieht (Median höchstens 1,6 Punkte). Die Schwelle
        ist das geometrische Mittel der Mediane, aber nie außerhalb der
        mittleren Hälfte der leeren Strecke zwischen den Clustern, damit sie
        die Pausen genauso einteilt wie die Clusterung. Wird nur bei einem
        Pausen-Ereignis neu berechnet, nie in poll() (Blockgröße egal).
        """
        self._char_thr_ms = None
        g = np.array(self.all_gaps, dtype=float)
        # Aussetzer und Prellen (< 0,5 Punkt) sind keine Elementpausen und
        # bildeten sonst ein eigenes unteres Cluster
        g = np.sort(g[g >= 0.5 * self.dit_ms])
        n = len(g)
        if n < 8:
            return
        lg = np.log(g)
        best_k, best_sse = None, None
        for k in range(3, n - 2):     # unten und oben je >= 3 Werte
            if g[k] < 1.3 * g[k - 1]:
                continue              # keine echte Lücke zwischen den Clustern
            lo, hi = lg[:k], lg[k:]
            sse = float(np.sum((lo - lo.mean()) ** 2) + np.sum((hi - hi.mean()) ** 2))
            if best_sse is None or sse < best_sse:
                best_k, best_sse = k, sse
        if best_k is None:
            return
        lo, hi = g[:best_k], g[best_k:]
        m_lo, m_hi = float(np.median(lo)), float(np.median(hi))
        if m_hi / m_lo < self.cfg.char_cluster_ratio or m_lo > 1.6 * self.dit_ms:
            return
        thr = float(np.sqrt(m_lo * m_hi))
        r = hi[0] / lo[-1]
        self._char_thr_ms = float(np.clip(thr, lo[-1] * r ** 0.25, lo[-1] * r ** 0.75))

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
            # nur ein Cluster, d. h. Wort- und Zeichenpausen liegen zu nah
            # beieinander (Geber mit weiten Zeichenabständen, Verhältnis
            # Wort/Zeichen nur ~1,4 statt 2,3): Schwelle knapp über die
            # typische Zeichenpause legen; lieber ein Wort zu viel trennen
            # als Rufzeichen zusammenkleben (Aufnahme 231339, Issue #10)
            thr = float(np.median(g)) * 1.35
        self.word_thr_ms = max(base, thr)

    def poll(self, gap_so_far_ms: float):
        """Wird regelmäßig aufgerufen, solange kein Ton anliegt (Live-Ausgabe
        ohne auf den nächsten Ton zu warten)."""
        self._flush(gap_so_far_ms)

    def _flush(self, gap_ms: float, char_thr: float = None):
        if char_thr is None:
            char_thr = self._char_threshold()
        if not self.char_emitted and gap_ms >= char_thr:
            parts = self._split_invalid(self.cur_marks, self.cur_gaps)
            self.symbol = ""
            self.cur_marks = []
            self.cur_gaps = []
            self.char_emitted = True
            for marks in parts:
                ch = decode_symbol(self._classify(marks))
                if ch:
                    # vor dem Aufruf setzen: on_char liest es (CWDecoder.last_conf)
                    self.last_conf = self.confidence(marks, ch)
                    self.on_char(ch)
        if not self.space_emitted and gap_ms >= self._word_threshold():
            self.space_emitted = True
            self.on_space()

    def _split_invalid(self, marks, gaps):
        """Tondauern eines Zeichens, bei ungültigem Symbol ggf. in zwei
        Zeichen geteilt (ADR-0025). Liefert eine Liste von Tondauer-Listen."""
        c = self.cfg
        if (not c.char_split or len(marks) < 2 or len(gaps) != len(marks) - 1
                or decode_symbol(self._classify(marks)) != "*"):
            return [marks]
        j = int(np.argmax(gaps))
        rest = [g for i, g in enumerate(gaps) if i != j]
        if rest and gaps[j] < c.char_split_ratio * float(np.median(rest)):
            return [marks]
        a, b = marks[:j + 1], marks[j + 1:]
        if "*" in (decode_symbol(self._classify(a)), decode_symbol(self._classify(b))):
            return [marks]
        return [a, b]

    def force_flush(self):
        """Am Ende einer Datei alles ausgeben."""
        self._flush(1e9)

# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""Wörterbuch-Segmentierung zusammengeklebter Wörter (ADR-0026).

Geber mit engen Wortabständen liefern `TNXFERFBCALL` statt
`TNX FER FB CALL`. Der Zerleger sucht per dynamischer Programmierung die
billigste Zerlegung eines Wortes in bekannte Teile:

    Teil                                  Kosten  zählt als bekannt
    Wort aus data/qso_words.txt (≥ 2)     1       1
    Rapport 599 / 5NN / ENN / 4T9         0,6     1
    Rufzeichen, in SCP                    1       2 (unter 5 Zeichen: 1)
    Rufzeichen, nicht in SCP (≥ 5 Z.)     3       1
    Zahl (1–4 Ziffern; eine nur am Rand)  1       0
    abgekürzte Zahl mit Ziffer (T01)      1,1     0
    Einzelbuchstabe K, R, W               1       0
    unbekannter Rest (≥ 2 Zeichen)        2 je Zeichen

Übernommen wird eine Zerlegung nur mit höchstens einem unbekannten Rest
und mindestens zwei bekannten Teilen. Einzelbuchstaben, Zahlen, kurze
Rufzeichen ohne SCP und abgekürzte Zahlen zählen nicht, weil sie in Zufallsgruppen
ständig vorkommen. Nicht zerlegt werden Wörter unter 5 Zeichen, Wörter
aus Ziffern, Wörter, die selbst bekannt oder ein Muster sind, und Wörter
in Rufzeichenform mit langem Suffix (`DJ7PRRFB`: ob das R noch zum
Rufzeichen gehört, weiß nur SCP – der Spotter findet DJ7PR ohnehin).

Der rohe Decodertext bleibt unverändert; die Zerlegung ist nur Anzeige
(`·`) und Eingabe für die N1MM-Engine und den Spotter.
"""
import re
import threading
from typing import List, Optional

from .callsign import looks_like_call
from .paths import data_path

WORDS_FILE = "qso_words.txt"
MIN_LEN = 5                 # kürzere Wörter bleiben ganz
SEP = "·"                   # Anzeige eines eingefügten Trenners
MAX_PART = 12               # längster bekannter Teil (Rufzeichen mit /P o. ä.)

COST_WORD = 1.0
COST_CALL_SCP = 1.0
COST_CALL = 3.0
COST_RST = 0.6
COST_NUMBER = 1.0
COST_CUT_NUMBER = 1.1
COST_UNKNOWN_CHAR = 2.0
CALL_MIN_LEN = 5            # kürzere Rufzeichen zählen nur mit SCP

# Rapport (Lesbarkeit 3–5, Stärke 3–9), abgekürzt N = 9, E = 5 nur vorn
RST_RE = re.compile(r"^(?:[3-5E][3-9N][1-9N])$")
NUMBER_RE = re.compile(r"^\d{1,4}$")
# abgekürzte Laufnummer: T = 0, N = 9, A = 1, O = 0; mindestens eine Ziffer
CUT_NUMBER_RE = re.compile(r"^(?=.*\d)[0-9TNAO]{2,3}$")
# "5NN5NN" sieht wie ein Rufzeichen aus (Präfix 5N), ist aber zweimal Rapport
RST_THEN_DIGIT_RE = re.compile(r"^[3-5E][3-9N][1-9N][0-9]")
# Rufzeichenform mit beliebig langem Suffix: Präfix, Ziffer, nur Buchstaben
CALL_SHAPE_RE = re.compile(r"^(?:[A-Z]{1,2}|[0-9][A-Z]{1,2}|[A-Z][0-9])[0-9][A-Z]+$")
# Zeichen, die ein Teil-Wort tragen kann; alles andere (Prosigns, '*', '?')
# trennt das Wort in unabhängig zerlegte Stücke
_PART_CHARS = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789/")
_TOKEN_RE = re.compile(r"<[^>]*>|.", re.S)

_lock = threading.Lock()
_words: Optional[frozenset] = None


def load_words(path=None) -> frozenset:
    """Wortschatz aus qso_words.txt (gecacht, wenn ohne path)."""
    global _words
    if path is None:
        with _lock:
            if _words is None:
                _words = _read_words(data_path(WORDS_FILE))
            return _words
    return _read_words(path)


def _read_words(path) -> frozenset:
    with open(path, encoding="utf-8") as f:
        return frozenset(ln.split("#")[0].strip().upper() for ln in f
                         if ln.split("#")[0].strip())


def _is_pattern(s: str) -> bool:
    return bool(RST_RE.match(s) or NUMBER_RE.match(s) or CUT_NUMBER_RE.match(s))


class Segmenter:
    def __init__(self, words=None, scp=None):
        """words: Menge bekannter Wörter (Standard: qso_words.txt);
        scp: Objekt mit is_known(call) oder None (ohne SCP)."""
        self.words = frozenset(words) if words is not None else load_words()
        self.scp = scp

    def _known(self, call: str) -> bool:
        if self.scp is None:
            return False
        try:
            return bool(self.scp.is_known(call))
        except (OSError, ValueError):
            return False

    def _part(self, s: str):
        """(Kosten, bekannte Teile) eines bekannten Teils oder None (Tabelle
        im Modulkopf)."""
        if s in self.words:
            return COST_WORD, (1 if len(s) >= 2 else 0)
        if RST_RE.match(s):
            return COST_RST, 1
        if NUMBER_RE.match(s):
            return COST_NUMBER, 0
        if CUT_NUMBER_RE.match(s):
            return COST_CUT_NUMBER, 0
        if looks_like_call(s) and not RST_THEN_DIGIT_RE.match(s):
            if self._known(s):
                return COST_CALL_SCP, 2 if len(s) >= CALL_MIN_LEN else 1
            if len(s) >= CALL_MIN_LEN:
                return COST_CALL, 1
        return None

    def whole_ok(self, s: str) -> bool:
        """Bleibt das Stück ganz (kurz, Ziffern, bekannt, Muster, Rufzeichen)?"""
        return (len(s) < MIN_LEN or s.isdigit() or s in self.words or _is_pattern(s)
                or looks_like_call(s) or self._known(s) or bool(CALL_SHAPE_RE.match(s)))

    def cuts(self, chunk: str) -> List[int]:
        """Trennstellen (Indizes 1..len-1) in einem Stück aus Buchstaben,
        Ziffern und '/'; leer, wenn es ganz bleibt."""
        s = chunk.upper()
        if self.whole_ok(s):
            return []
        n = len(s)
        INF = (float("inf"), 0, 0, 0)
        # best[j] = (Kosten, unbekannte Teile, -bekannte Teile, Teile), Vorgänger
        best = [INF] * (n + 1)
        prev = [None] * (n + 1)
        best[0] = (0.0, 0, 0, 0)
        for j in range(1, n + 1):
            for i in range(j):
                if best[i][0] == float("inf"):
                    continue
                part = self._part(s[i:j]) if j - i <= MAX_PART else None
                if part is not None and j - i == 1 and s[i].isdigit() and 0 < i and j < n:
                    part = None     # Einzelziffer nur am Rand (3TU73TU), nie K 1 AR
                c, unk, neg_known, parts = best[i]
                if part is not None:
                    cand = (c + part[0], unk, neg_known - part[1], parts + 1)
                elif j - i >= 2:
                    cand = (c + COST_UNKNOWN_CHAR * (j - i), unk + 1, neg_known, parts + 1)
                else:
                    continue
                if cand < best[j]:
                    best[j], prev[j] = cand, i
        _cost, unk, neg_known, parts = best[n]
        if parts < 2 or unk > 1 or -neg_known < 2:
            return []
        out, j = [], n
        while j and prev[j] is not None:
            j = prev[j]
            if j:
                out.append(j)
        return sorted(out)

    def word_cuts(self, word: str) -> List[int]:
        """Trennstellen in einem Wort, dessen Zeichen je ein Token sind
        (Prosigns usw. als ein beliebiges Nicht-Buchstaben-Zeichen, wie im
        Strom des Spotters). Positionen zählen Tokens ab 0."""
        out, start = [], 0
        s = word.upper()
        for i in range(len(s) + 1):
            if i == len(s) or s[i] not in _PART_CHARS:
                if i - start >= MIN_LEN:
                    out += [start + k for k in self.cuts(s[start:i])]
                start = i + 1
        return out

    def segment_word(self, word: str, sep: str = SEP) -> str:
        """Ein Wort aus Text (Prosigns als <XX>) zerlegt, mit sep zwischen
        den Teilen; Groß-/Kleinschreibung bleibt erhalten."""
        toks = _TOKEN_RE.findall(word)
        flat = "".join(t if (len(t) == 1 and t.upper() in _PART_CHARS) else "|"
                       for t in toks)
        cuts = set(self.word_cuts(flat))
        return "".join((sep if i in cuts else "") + t for i, t in enumerate(toks))

    def segment_text(self, text: str, sep: str = SEP) -> str:
        """Ganzer Text, Wort für Wort; Leerzeichen und Zeilen bleiben."""
        return re.sub(r"\S+", lambda m: self.segment_word(m.group(0), sep), text)


_default: Optional[Segmenter] = None


def default() -> Segmenter:
    """Segmenter mit qso_words.txt und der mitgelieferten SCP."""
    global _default
    if _default is None:
        from . import scp
        _default = Segmenter(scp=scp.DEFAULT)
    return _default


def segment_text(text: str, sep: str = SEP) -> str:
    return default().segment_text(text, sep)


class WordBuffer:
    """Hält die Zeichen des laufenden Wortes zurück, bis das Wortende
    feststeht, und gibt das Wort dann mit Trennern an den Zerlegestellen aus
    (Terminal mit `·`, N1MM-Engine mit echten Leerzeichen).

    add(token, pos): ein Zeichen (Prosign als ein Token) an Stromposition pos
    (wie CallsignSpotter: n-tes Zeichen ohne Leerzeichen); cut(positions):
    Trennstellen vom Spotter; end(ws): Wortende, gibt Wort + ws aus.
    """

    def __init__(self, emit, sep: str = SEP):
        self.emit = emit
        self.sep = sep
        self._toks = []         # (pos, token)
        self._cuts = set()

    def add(self, token: str, pos: int):
        self._toks.append((pos, token))

    def cut(self, positions):
        self._cuts.update(positions)

    def end(self, ws: str = ""):
        first = self._toks[0][0] if self._toks else None
        word = "".join((self.sep if (p in self._cuts and p != first) else "") + t
                       for p, t in self._toks)
        self._toks, self._cuts = [], set()
        if word or ws:
            self.emit(word + ws)

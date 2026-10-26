# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""Rufzeichen im decodierten Textstrom erkennen (ADR-0019).

Zwei Wege:
- **Wörter:** Ein Wort, das ganz wie ein Rufzeichen aussieht.
- **Zeichenstrom ohne Wortgrenzen:** Bei Gebern mit weiten Zeichenabständen
  kleben Rufzeichen an Nachbarwörtern (`DEDJ7PR`, `IK2ULVDEOY1CT`) oder
  werden zerrissen (`OY 1 CT`). Ein *neues* Rufzeichen wird nur
  angenommen, wenn es innerhalb eines Wortes an einer Grenze beginnt und
  endet (Wortanfang/-ende, `DE` davor/danach, Prosign); Treffer direkt nach
  `DE` haben Vorrang. Ein *bereits erkanntes* Rufzeichen wird zusätzlich
  überall im Zeichenstrom ohne Leerzeichen wiedergefunden (`DJ7PRRFB`,
  `OY 1 CT`) und zählt dann mit.
"""
import re
import time
from collections import OrderedDict

# Präfix: 1-2 Buchstaben, oder Ziffer+Buchstabe (z. B. 4X, 9A), oder Buchstabe+Ziffer
# (z. B. A4), dann Trennziffer, dann 1-4 Buchstaben Suffix. Optional /P, /M, /QRP,
# oder ein Länderpräfix davor (DL/OK1XYZ).
CALL_RE = re.compile(
    r"^(?:[A-Z0-9]{1,3}/)?"
    r"(?:[A-Z]{1,2}|[0-9][A-Z]{1,2}|[A-Z][0-9])"
    r"[0-9][A-Z]{1,4}"
    r"(?:/(?:P|M|MM|AM|QRP|[0-9]))?$"
)

# Wörter, die wie Rufzeichen aussehen, aber keine sind
NOT_CALLS = {"5NN", "599", "73", "88", "TU", "DE", "CQ", "TEST", "AGN", "PSE", "QRZ", "QRL"}

STREAM_CHARS = 40     # so viele Zeichen (ohne Leerzeichen) durchsucht der Strom-Weg
SEP = "|"             # Platzhalter im Strom für Prosigns, '*', '?' usw.
MIN_LEN, MAX_LEN = 3, 10
GLUED_MAX_SUFFIX = 3  # Suffix-Buchstaben eines neuen Rufzeichens in einem zusammengeklebten Wort
_SUFFIX_RE = re.compile(r"[0-9]([A-Z]+)(?:/[A-Z0-9]+)?$")


def _suffix_len(call: str) -> int:
    m = _SUFFIX_RE.search(call)
    return len(m.group(1)) if m else 0


def looks_like_call(word: str) -> bool:
    w = word.strip().upper()
    if len(w) < 3 or w in NOT_CALLS:
        return False
    if "*" in w:
        return False
    core = w.split("/")[-1] if "/" in w and not w.endswith(("/P", "/M", "/MM", "/AM", "/QRP")) else w
    if not any(c.isalpha() for c in core) or not any(c.isdigit() for c in core):
        return False
    return bool(CALL_RE.match(w))


def calls_in_word(word: str):
    """Rufzeichen innerhalb eines (evtl. zusammengeklebten) Wortes.

    Ein Treffer muss an einer Grenze beginnen und enden: Wortanfang/-ende,
    ein Prosign o. ä. (SEP) oder ein `DE` davor bzw. danach. Überlappende
    Treffer: der direkt nach `DE` gewinnt, sonst der längere.
    """
    s = word.upper()
    found = []
    for a in range(len(s)):
        de_before = a >= 2 and s[a - 2:a] == "DE"
        if not (a == 0 or s[a - 1] == SEP or de_before):
            continue
        for b in range(a + MIN_LEN, min(len(s), a + MAX_LEN) + 1):
            if not (b == len(s) or s[b] == SEP or s[b:b + 2] == "DE"):
                continue
            cand = s[a:b]
            if SEP in cand or not looks_like_call(cand):
                continue
            if (a, b) != (0, len(s)) and _suffix_len(cand) > GLUED_MAX_SUFFIX:
                # zusammengeklebt: langer Suffix ist meist das Nachbarwort
                # (DJ7PRKM = DJ7PR + KM); bekannte Rufzeichen findet der
                # Strom-Weg trotzdem
                continue
            found.append((not de_before, -(b - a), a, b, cand))
    chosen, used = [], []
    for _de, _neg_len, a, b, cand in sorted(found):
        if all(b <= ua or a >= ub for ua, ub in used):
            used.append((a, b))
            chosen.append((a, cand))
    return [cand for _a, cand in sorted(chosen)]


class CallsignSpotter:
    """Sammelt den Zeichenstrom und meldet erkannte Rufzeichen.

    Geprüft wird jeweils am Wortende (Wortabstand). Wiederholungen innerhalb
    von `repeat_s` Sekunden werden nicht erneut gemeldet, aber mitgezählt
    (ein zweimal gehörtes Rufzeichen ist verlässlicher).
    """

    def __init__(self, on_call=None, repeat_s: float = 30.0, keep: int = 20, on_span=None):
        self.on_call = on_call or (lambda call: None)
        # on_span(call, start, end): jedes gezählte Vorkommen mit seiner Lage
        # im Zeichenstrom (n-tes Zeichen ohne Leerzeichen, ab 0; end exklusiv),
        # damit die GUI es im Text markieren kann
        self.on_span = on_span or (lambda call, start, end: None)
        self.repeat_s = repeat_s
        self.word = ""
        self.recent = OrderedDict()   # call -> (last_time, count)
        self.keep = keep
        # Zeichenstrom ohne Leerzeichen; _off = absolute Position von _s[0]
        self._s = ""
        self._off = 0
        self._word_start = 0          # absolute Position des laufenden Wortes
        self._bounds = set()          # absolute Positionen mit Wortgrenze davor
        self._seen = set()            # (call, abs_start) bereits gezählt

    def feed(self, ch: str):
        if ch == " ":
            self._end_word()
            return
        c = ch.upper() if len(ch) == 1 and (ch.isalnum() or ch == "/") else SEP
        self.word += c
        self._s += c
        cut = len(self._s) - STREAM_CHARS
        if cut > 0:
            self._s = self._s[cut:]
            self._off += cut
            self._bounds = {p for p in self._bounds if p >= self._off}
            self._seen = {k for k in self._seen if k[1] >= self._off}

    def _end_word(self):
        w, self.word = self.word, ""
        end = self._off + len(self._s)
        start = self._word_start
        self._word_start = end
        if not w:
            return
        self._bounds.add(start)
        self._bounds.add(end)
        hits = []
        # 1) neue Rufzeichen im Wort (auch zusammengeklebt)
        i = 0
        for cand in calls_in_word(w):
            i = w.upper().find(cand, i)
            # verlängert der Kandidat nur ein bekanntes Rufzeichen um
            # Buchstaben (DJ7PR + KM), zählt das bekannte (Weg 2 unten)
            if not any(cand != k and cand.startswith(k) and cand[len(k):].isalpha()
                       for k in self.recent):
                hits.append((cand, start + i))
            i += len(cand)
        # 2) bekannte Rufzeichen im Strom ohne Leerzeichen, die im gerade
        #    beendeten Wort enden (zusammengeklebt oder zerrissen)
        for call in list(self.recent):
            pos = self._s.find(call)
            while pos >= 0:
                a = self._off + pos
                b = a + len(call)
                if start < b <= end and self._starts_ok(pos):
                    hits.append((call, a))
                pos = self._s.find(call, pos + 1)
        for call, a in hits:
            if (call, a) not in self._seen:
                self._seen.add((call, a))
                self._hit(call)
                self.on_span(call, a, a + len(call))

    def _starts_ok(self, pos: int) -> bool:
        """Beginnt der Treffer im Strom an einer Grenze?"""
        return (pos == 0 or self._s[pos - 1] == SEP or (self._off + pos) in self._bounds
                or (pos >= 2 and self._s[pos - 2:pos] == "DE"))

    def _hit(self, w: str):
        now = time.time()
        last, cnt = self.recent.get(w, (0.0, 0))
        self.recent[w] = (now, cnt + 1)
        self.recent.move_to_end(w)
        while len(self.recent) > self.keep:
            self.recent.popitem(last=False)
        if now - last > self.repeat_s or cnt == 0:
            self.on_call(w)

    def flush(self):
        self._end_word()

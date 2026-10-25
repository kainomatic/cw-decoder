"""Rufzeichen im decodierten Textstrom erkennen."""
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


class CallsignSpotter:
    """Sammelt Wörter aus dem Zeichenstrom und meldet erkannte Rufzeichen.

    Ein Rufzeichen wird gemeldet, sobald das Wort abgeschlossen ist (Wortabstand).
    Wiederholungen innerhalb von `repeat_s` Sekunden werden nicht erneut gemeldet,
    aber mitgezählt (ein zweimal gehörtes Rufzeichen ist verlässlicher).
    """

    def __init__(self, on_call=None, repeat_s: float = 30.0, keep: int = 20):
        self.on_call = on_call or (lambda call: None)
        self.repeat_s = repeat_s
        self.word = ""
        self.recent = OrderedDict()   # call -> (last_time, count)
        self.keep = keep

    def feed(self, ch: str):
        if ch == " ":
            self._end_word()
        else:
            self.word += ch

    def _end_word(self):
        w, self.word = self.word, ""
        if not looks_like_call(w):
            return
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

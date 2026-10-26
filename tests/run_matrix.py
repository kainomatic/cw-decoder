# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""Testmatrix: zufällige Texte und gestreute Störungen, nach Kategorien.

    python tests/run_matrix.py            Kategorien-Mittel und Gesamtmittel
    python tests/run_matrix.py --verbose  dazu jeden Fall mit erkanntem Text
    python tests/run_matrix.py --legacy   die alte Matrix mit zwei festen Sätzen
    python tests/run_matrix.py --n 20     Fälle pro Kategorie (Standard 10)

Die Texte kommen aus cwdecoder.testtext (zufällige Rufzeichen, Exchanges,
QSO-Floskeln, Fünfergruppen); Tempo, Tonhöhe und Störparameter werden je
Fall aus einem Bereich gezogen. Die Seeds sind fest, der Lauf ist
reproduzierbar. Die Matrix ist Sicherheitsnetz gegen Rückschritte, kein
Ziel, das auf 100 % getrieben werden soll (ROADMAP, Leitlinie).

Die Kategorie "Rauschen" enthält kein Signal; dort zählt, dass der Decoder
nichts ausgibt (Müll bei reinem Rauschen stört mehr als eine Lücke).
"""
import sys
import os
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from cwdecoder import utf8_console  # noqa: E402
from cwdecoder.gen import render  # noqa: E402
from cwdecoder.decode_wav import decode_signal, similarity  # noqa: E402
from cwdecoder.testtext import random_text  # noqa: E402

# ---------------------------------------------------------------------------
# Alte Matrix (zwei feste Sätze), nur noch zum Vergleich mit --legacy
# ---------------------------------------------------------------------------
TEXT = "CQ TEST DE DL1ABC DL1ABC K"
TEXT2 = "UR RST 599 599 TU 73 DE OK1XYZ <SK>"
LEGACY_CASES = [
    ("sauber 20 WPM", TEXT, dict(wpm=20, snr_db=30)),
    ("sauber 35 WPM", TEXT, dict(wpm=35, snr_db=30)),
    ("sauber 12 WPM", TEXT, dict(wpm=12, snr_db=30)),
    ("45 WPM", TEXT, dict(wpm=45, snr_db=25)),
    ("Farnsworth 15/8", TEXT, dict(wpm=15, farnsworth_wpm=8, snr_db=25)),
    ("Pitch 450 Hz", TEXT, dict(wpm=25, pitch=450, snr_db=20)),
    ("Pitch 1000 Hz", TEXT, dict(wpm=25, pitch=1000, snr_db=20)),
    ("Drift ±80 Hz", TEXT, dict(wpm=25, drift_hz=80, snr_db=20)),
    ("SNR 10 dB", TEXT, dict(wpm=25, snr_db=10)),
    ("SNR 6 dB", TEXT, dict(wpm=25, snr_db=6)),
    ("SNR 3 dB", TEXT, dict(wpm=25, snr_db=3)),
    ("SNR 0 dB", TEXT, dict(wpm=20, snr_db=0)),
    ("SNR -3 dB", TEXT, dict(wpm=20, snr_db=-3)),
    ("QSB 0.3 Hz tief", TEXT, dict(wpm=25, snr_db=15, qsb_hz=0.3, qsb_depth=0.9)),
    ("QSB + SNR 6", TEXT, dict(wpm=25, snr_db=6, qsb_hz=0.5, qsb_depth=0.7)),
    ("QRM 500 Hz -6 dB", TEXT, dict(wpm=25, snr_db=15, qrm_hz=500, qrm_db=-6)),
    ("QRM 850 Hz -3 dB", TEXT, dict(wpm=25, snr_db=15, qrm_hz=850, qrm_db=-3)),
    ("Jitter 15%", TEXT, dict(wpm=25, snr_db=20, jitter=0.15)),
    ("schwer gewichtet", TEXT, dict(wpm=25, snr_db=20, weight=1.3)),
    ("leicht gewichtet", TEXT, dict(wpm=25, snr_db=20, weight=0.75)),
    ("Zahlen/Prosign", TEXT2, dict(wpm=28, snr_db=12)),
    ("alles zusammen", TEXT2, dict(wpm=30, snr_db=8, drift_hz=40, qsb_hz=0.4,
                                   qsb_depth=0.6, jitter=0.1)),
]

# ---------------------------------------------------------------------------
# Neue Matrix: Kategorien mit Parameterbereichen
# ---------------------------------------------------------------------------
def _u(rng, lo, hi):
    return float(rng.uniform(lo, hi))


def cat_sauber(rng):
    return dict(wpm=_u(rng, 12, 40), pitch=_u(rng, 400, 1000), snr_db=_u(rng, 25, 35))


def cat_tempo_pitch(rng):
    return dict(wpm=_u(rng, 8, 55), pitch=_u(rng, 300, 1200), snr_db=20)


def cat_snr_mittel(rng):
    return dict(wpm=_u(rng, 15, 35), pitch=_u(rng, 500, 900), snr_db=_u(rng, 6, 12))


def cat_snr_schwach(rng):
    return dict(wpm=_u(rng, 15, 30), pitch=_u(rng, 500, 900), snr_db=_u(rng, 0, 6))


def cat_drift(rng):
    return dict(wpm=_u(rng, 15, 35), pitch=_u(rng, 500, 900), snr_db=_u(rng, 6, 20),
                drift_hz=_u(rng, 30, 120))


def cat_qsb(rng):
    return dict(wpm=_u(rng, 15, 35), pitch=_u(rng, 500, 900), snr_db=_u(rng, 8, 20),
                qsb_hz=_u(rng, 0.2, 0.8), qsb_depth=_u(rng, 0.5, 0.9))


def cat_qrm(rng):
    pitch = _u(rng, 500, 900)
    off = _u(rng, 150, 400) * (1 if rng.random() < 0.5 else -1)
    return dict(wpm=_u(rng, 15, 35), pitch=pitch, snr_db=_u(rng, 12, 20),
                qrm_hz=pitch + off, qrm_db=_u(rng, -15, -3))


def cat_timing(rng):
    d = dict(wpm=_u(rng, 12, 35), pitch=_u(rng, 500, 900), snr_db=20,
             jitter=_u(rng, 0.05, 0.2), weight=_u(rng, 0.7, 1.4))
    if rng.random() < 0.4:
        d["farnsworth_wpm"] = max(5.0, d["wpm"] * _u(rng, 0.4, 0.7))
    return d


def cat_kombiniert(rng):
    pitch = _u(rng, 500, 900)
    d = dict(wpm=_u(rng, 15, 35), pitch=pitch, snr_db=_u(rng, 4, 12),
             drift_hz=_u(rng, 0, 60), jitter=_u(rng, 0.0, 0.12))
    if rng.random() < 0.6:
        d.update(qsb_hz=_u(rng, 0.2, 0.6), qsb_depth=_u(rng, 0.3, 0.8))
    if rng.random() < 0.4:
        d.update(qrm_hz=pitch + _u(rng, 200, 400) * (1 if rng.random() < 0.5 else -1),
                 qrm_db=_u(rng, -12, -4))
    return d


def cat_rauschen(rng):
    # Kein Signal: Text leer, nur Rauschen (lead/tail). Bewertung: nichts ausgeben.
    return dict(wpm=25, snr_db=0, lead_s=_u(rng, 6, 10), tail_s=0.5)


CATEGORIES = [
    ("sauber", cat_sauber),
    ("Tempo/Pitch", cat_tempo_pitch),
    ("SNR 6-12 dB", cat_snr_mittel),
    ("SNR 0-6 dB", cat_snr_schwach),
    ("Drift", cat_drift),
    ("QSB", cat_qsb),
    ("QRM", cat_qrm),
    ("Timing/Farnsw.", cat_timing),
    ("kombiniert", cat_kombiniert),
    ("Rauschen", cat_rauschen),
]


def build_cases(n_per_cat: int = 10, base_seed: int = 1000):
    """Liefert [(kategorie, name, text, kwargs, seed)], reproduzierbar."""
    cases = []
    for ci, (cat, sampler) in enumerate(CATEGORIES):
        for k in range(n_per_cat):
            seed = base_seed + 100 * ci + k
            rng = np.random.default_rng(seed)
            kw = sampler(rng)
            text = "" if cat == "Rauschen" else random_text(rng)
            cases.append((cat, f"{cat} #{k + 1}", text, kw, seed))
    return cases


def score_case(text: str, got: str) -> float:
    if text == "":
        # Rauschen: jedes ausgegebene Zeichen (außer Leerzeichen) kostet
        n = len(got.replace(" ", ""))
        return max(0.0, 1.0 - n / 5.0)
    return similarity(got, text)


def run(n_per_cat: int = 10, verbose: bool = False, base_seed: int = 1000):
    """Führt die Matrix aus; liefert (gesamt, {kategorie: mittel})."""
    per_cat = {}
    for cat, name, text, kw, seed in build_cases(n_per_cat, base_seed):
        sig = render(text, fs=8000, seed=seed, **kw)
        dec, _ = decode_signal(sig, 8000, block=512)
        got = dec.get_text()
        sc = score_case(text, got)
        per_cat.setdefault(cat, []).append(sc)
        if verbose or sc < 0.8:
            s = dec.status
            flag = "OK " if sc >= 0.95 else ("~  " if sc >= 0.8 else "!! ")
            print(f"{flag}{name:18s} {100 * sc:5.1f}%  {kw.get('wpm', 0):4.0f} WPM  "
                  f"{s['freq_hz']:5.0f} Hz  SNR {kw.get('snr_db', 0):4.1f} dB")
            print(f"      soll: {text}\n      ist:  {got}")
    means = {c: float(np.mean(v)) for c, v in per_cat.items()}
    overall = float(np.mean(list(means.values())))
    return overall, means


def run_legacy(verbose: bool = False) -> float:
    scores = []
    for name, text, kw in LEGACY_CASES:
        sig = render(text, fs=8000, seed=42, **kw)
        dec, _ = decode_signal(sig, 8000, block=512)
        got = dec.get_text()
        sc = similarity(got, text)
        scores.append(sc)
        s = dec.status
        flag = "OK " if sc >= 0.95 else ("~  " if sc >= 0.8 else "!! ")
        print(f"{flag}{name:18s} {100 * sc:5.1f}%  {s['wpm']:4.0f} WPM  {s['freq_hz']:5.0f} Hz"
              + (f"\n      {got}" if verbose or sc < 0.95 else ""))
    return float(np.mean(scores))


def main():
    utf8_console()
    verbose = "--verbose" in sys.argv
    n = 10
    if "--n" in sys.argv:
        n = int(sys.argv[sys.argv.index("--n") + 1])
    if "--legacy" in sys.argv:
        print(f"\nMittel (alte Matrix): {100 * run_legacy(verbose):.1f} %")
        return
    overall, means = run(n, verbose)
    print()
    for cat, m in means.items():
        print(f"{cat:16s} {100 * m:5.1f} %")
    print(f"\nMittel: {100 * overall:.1f} %   ({n} Fälle je Kategorie, {len(means)} Kategorien)")


if __name__ == "__main__":
    main()

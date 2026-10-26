# ADR-0017: Testmatrix mit zufälligen Texten und Rauschkategorie

**Status:** Accepted

Ergänzt durch ADR-0018: elfte Kategorie „CW-Filter"; die Hälfte der
Rauschfälle läuft durch ein schmales Empfängerfilter.

## Kontext

Die bisherige Testmatrix (`tests/run_matrix.py`) prüfte 22 feste Fälle mit
nur zwei Sätzen („CQ TEST DE DL1ABC DL1ABC K" und „UR RST 599 …"). Damit
bestand die Gefahr, Schwellen an genau diese Zeichenfolgen anzupassen: Ein
Fehler bei Buchstaben, die dort nicht vorkommen (z. B. erstes Zeichen „F"
statt „C", Issue #5), blieb unsichtbar. Außerdem prüfte die Matrix nicht, was
der Decoder bei reinem Rauschen ausgibt. Laut Leitlinie (ROADMAP) ist Müll im
Textfenster aber schlimmer als eine Lücke (Issue #1).

## Entscheidung

- **Texte:** `cwdecoder/testtext.py` erzeugt zufällige, fiktive Rufzeichen
  aus verschiedenen Präfix-Mustern (zwei Buchstaben, ein Buchstabe, Ziffer
  vorn, `/P`, `/M`, Landeskenner vorn), Contest-Exchanges, QSO-Floskeln mit
  Name, QTH, Wetter und Leistung, CQ-Rufe und Fünfergruppen aus allen
  Buchstaben und Ziffern.
- **Aufbau:** 10 Kategorien mit je 10 Fällen: sauber, Tempo/Pitch,
  SNR 6–12 dB, SNR 0–6 dB, Drift, QSB, QRM, Timing/Farnsworth, kombiniert und
  Rauschen. Jede Kategorie zieht Tempo, Tonhöhe und Störparameter pro Fall
  aus einem festen Bereich. Das Ergebnis ist der Mittelwert der
  Kategorie-Mittel.
- **Rauschkategorie:** Sie enthält 6–10 s Rauschen ohne Signal. Jedes
  ausgegebene Zeichen außer dem Leerzeichen kostet 20 Prozentpunkte. Ziel
  sind 100 %.
- **Seeds:** Fall `k` der Kategorie `i` nutzt den Seed `1000 + 100·i + k`.
  Der Lauf ist damit reproduzierbar. Für Stichproben gegen Übertuning nimmt
  `run_matrix.run(base_seed=…)` andere Basis-Seeds (z. B. 5000, 7777).
- **QRM-Bereich:** Die Störstation liegt 150–400 Hz neben dem Ton und ist
  3–15 dB schwächer. Gleich starke oder stärkere Stationen sind kein
  Testziel: Dort entscheidet der Nutzer per Klick ins Spektrum, welche
  Station er hören will. Ohne diese Wahl gibt es keine „richtige" Antwort.
- **CI-Untergrenzen** (`tests/test_matrix.py`, Marker `slow`): Gesamtmittel
  mindestens 95 %, Rauschkategorie mindestens 99 %. Die Untergrenze liegt
  mit etwas Abstand unter dem gemessenen Wert, damit nur ein grober Einbruch
  CI rot macht. Der Pflichtlauf vor und nach DSP-Änderungen bleibt
  `python tests/run_matrix.py` mit dem genauen Mittelwert.
- **Alte Matrix:** `python tests/run_matrix.py --legacy` bleibt zum
  Vergleich mit früheren Messungen erhalten.

## Konsequenzen

- Schwellen werden gegen viele Zeichenfolgen und gestreute Parameter
  geprüft, nicht gegen zwei Sätze.
- Ausgabe bei reinem Rauschen fällt sofort auf.
- Die Werte der neuen Matrix sind nicht mit den alten 95,4 % vergleichbar.
  Bericht und `CLAUDE.md` nennen beide Werte (neu und `--legacy`).
- Ändern sich Kategorien, Bereiche oder die Seed-Formel, ändern sich alle
  Werte. Das braucht einen neuen ADR und neue Bezugswerte.
- Die Matrix ist ein Sicherheitsnetz gegen Rückschritte, kein Ziel für
  100 %: Schwache Fälle wie 20 % Jitter bei leichter Gewichtung bleiben
  bewusst schwach (Leitlinie).

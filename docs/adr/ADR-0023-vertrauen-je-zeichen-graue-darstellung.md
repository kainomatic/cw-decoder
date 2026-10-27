# ADR-0023: Vertrauen je Zeichen und graue Darstellung

**Status:** Accepted

## Kontext

Bisher gab der Decoder für jedes Zeichen nur das Ergebnis aus; ein `*`
stand für eine unbekannte Punkt/Strich-Folge. Ob ein Buchstabe knapp
entschieden wurde (ein Element genau zwischen Punkt und Strich, Tempo noch
nicht eingemessen, schwaches Signal), sah der Operator nicht. Gerade bei
Rufzeichen muss er wissen, wo er selbst hinhören muss. Entscheidung DF1DS
(27.10.2026, #18): unsichere Zeichen werden im Text grau dargestellt.

Leitlinie (ROADMAP): Der Decoder unterstützt den Operator, er ersetzt ihn
nicht. Ein Wahrscheinlichkeits-Decoder ist nicht beschlossen.

## Entscheidung

**Vertrauen als Metadaten, nicht als andere Decodierung.** Die Zeichen
bleiben exakt dieselben; zu jedem Zeichen wird nur ein Wert `conf` in 0…1
berechnet, aus dem, was beim Zeichenende ohnehin vorliegt. Die Berechnung
liest nur und ändert keinen Zustand; `tests/test_confidence.py` prüft für
alle 110 Fälle der Matrix (Seed 1000), dass der Text mit und ohne
Berechnung gleich ist.

Maße (`TimingDecoder.confidence`, `CWDecoder.char_confidence`):

1. **Abstand zur Strich-Schwelle** (Hauptmaß): kleinster logarithmischer
   Abstand aller Elemente des Zeichens zur aktuellen Strich-Schwelle,
   `min_i |log(len_i / schwelle)| / log(conf_margin_ref)`, auf 0…1
   geklemmt (`conf_margin_ref = 1.6`). Ein Element knapp an der Schwelle
   macht das ganze Zeichen unsicher.
2. **Tempo noch nicht eingemessen**: Hat der Decoder seit `reset_tempo`
   weniger als `conf_warmup_marks = 8` Töne vor dem Zeichen gehört, wird
   mit `conf_warmup_min = 0.6` bis 1 (linear) multipliziert. Ein sauber
   gegebenes erstes Zeichen bleibt damit über der Schwelle, ein knappes
   fällt darunter.
3. **Unbekanntes Symbol** (`*`): 0.
4. **Pegel**: `Thresholder.snr_db` unter `conf_snr_full_db = 16` dB
   multipliziert linear bis `conf_snr_min = 0.7` bei
   `conf_snr_low_db = 10` dB (Squelch-Schwelle; darunter gibt es keine
   Zeichen). Die 8 dB aus dem Auftrag beziehen sich auf eine andere
   Skala; `snr_db` ist der Abstand Signalpegel/Rauschteppich in der
   Hüllkurve; ohne mindestens 10 dB öffnet der Squelch nicht.

Die Werte stehen in `TimingConfig` bzw. `DecoderConfig` (`conf_*`).

**Schwelle:** `conf < UNSURE_CONF = 0.5` (`decoder.py`) gilt als unsicher.

**Schnittstelle** (rückwärtskompatibel): `on_char(ch)` bleibt.
`CWDecoder.last_conf` ist vor dem Aufruf von `on_char` gesetzt; neu ist der
optionale Callback `on_char_conf(ch, conf)`. `LiveDecoder(on_char_conf=…)`
gibt die Zeichen samt Vertrauen dorthin statt an `on_text`; Leerzeichen
und Absätze bleiben bei `on_text`. `get_text()` ist unverändert,
`get_text_marked()` schreibt unsichere Zeichen klein.

**Darstellung:**

- GUI: Tag `unsure`, Schrift grau `#8a8a8a`, Tooltip „unsicher erkannt".
  Die Rufzeichen-Markierung (`call`) hat höhere Tag-Priorität und bleibt
  sichtbar. Ein Rufzeichen, dessen Vorkommen bisher alle mindestens ein
  unsicheres Zeichen hatten, bekommt im Tooltip von Knopf und Markierung
  „enthält unsichere Zeichen"; ein sicher gehörtes Vorkommen hebt das auf.
  Der Knopf-Text und die Erkennung bleiben unverändert.
- Terminal (`live.py`, `decode_wav.py`): unsichere Zeichen **klein**
  (`CQ TEST OZ1hGT`), ohne Option. Ziffern und Satzzeichen haben keine
  Kleinform und sehen dort unverändert aus. `--expect` vergleicht ohne
  Groß/klein.
- Decodier-Log `.txt`: `sekunde;zeichen;vertrauen` (zwei Nachkommastellen);
  Leerzeichen und `¶` mit leerer dritter Spalte. Logs von vor beta12 haben
  zwei Spalten; nichts im Programm liest sie ein.
- N1MM (CW Reader, Spots, Tippen) bekommt die Zeichen unverändert.

## Konsequenzen

- Der Operator sieht, welche Zeichen knapp waren; an der Testmatrix sind
  bei sauberen Signalen 0 % der Zeichen grau, bei starkem Jitter (25 %)
  rund ein Drittel, und dort sind 80 % der falschen Zeichen grau markiert.
  Kategorien mit QSB/QRM: 4–5 % grau.
- Die Matrix ist unverändert (gleicher Text in allen Fällen, Seeds
  1000/5000/7777, alte Matrix, echte Aufnahmen); die Tuning-Regeln für
  `timing.py`/`decoder.py` gelten trotzdem weiter.
- Fehler, die nicht an der Strich-Schwelle entstehen (verlorene oder
  zusätzliche Elemente bei sehr schwachem Signal, falsche Zeichengrenzen),
  erkennt das Maß nicht; ein solches Zeichen kann schwarz und falsch sein.
- Ein späterer weicher Decoder könnte `conf` direkt liefern; die
  Schnittstelle (`last_conf`, `on_char_conf`) bleibt dafür gleich.

# ADR-0018: Schmales Empfängerfilter — Linien-Gate und Dynamik-Squelch

**Status:** Accepted

## Kontext

Die ersten echten Aufnahmen vom Shack-PC (26.10.2026, USB-Audio 48 kHz) kamen
durch ein schmales CW-Filter im Empfänger (−6 dB etwa 840–920 Hz, also rund
100 Hz breit). Die synthetische Matrix ging bis dahin von Rauschen über die
volle SSB-Bandbreite (2,4 kHz) aus. Durch ein so schmales Filter verhält sich
Rauschen anders:

- Im Spektrum ist es selbst ein Buckel über dem Band-Median. Die bisherige
  Tonerkennung (Peak ≥ 8 dB über dem Median) hielt es für einen Ton.
- Nach dem Detektor hat seine Hüllkurve langsame Schwankungen, die wie
  Tastung aussehen; der Pegel-Squelch (Signal ≥ 10 dB über dem
  Rauschteppich) ging auf.

Die Folgen auf dem Shack-PC waren Müll bei leerer Frequenz und danach ein
verschlepptes Tempo, sodass die nächste Station als „TTTT" erschien.

## Entscheidung

Zwei voneinander unabhängige Kriterien müssen beide erfüllt sein, damit der
Squelch öffnet. Dazu kommt ein Tempo-Reset bei Tonverlust.

1. **Linien-Gate im `ToneTracker`** (`TrackerConfig`):
   - Ein CW-Ton ist eine schmale Linie. Der Peak muss gegenüber seinem
     Umfeld (±20…40 Hz, `line_core_hz`/`line_win_hz`) um mindestens 9 dB
     herausragen (`min_line_db`).
   - Hysterese: Das Gate schließt erst, wenn die Linie 0,6 s lang
     (`line_off_s`) unter 6 dB liegt (`line_off_db`). So überbrückt es
     Drift und QSB.
   - Ergebnis ist `tone_present`. Bei fester Frequenz wird die Linie an
     dieser Frequenz beurteilt.
2. **Dynamik-Squelch im `Thresholder`** (`ThresholdConfig`):
   - Gemessen wird der Abstand vom 99,5. zum 10. Perzentil der Hüllkurve
     über die letzten 2 s (`dyn_window_s`, `dyn_hi_pct`). Er muss mindestens
     20 dB betragen (`min_dyn_db`).
   - Getastetes CW liegt bei 26 dB und mehr. Rauschen durch ein 100-Hz-Filter
     (Rayleigh) liegt im Mittel bei etwa 17,6 dB, im 90. Perzentil bei
     19,6 dB.
   - Bewertet wird im 10-ms-Takt (`dyn_step_ms`), sobald 0,5 s im Fenster
     liegen.
   - **Warum 99,5 %:** Die erste Fassung (98. Perzentil, Bewertung alle
     100 ms) öffnete nach mehr als 2 s Rauschen erst nach 100–150 ms
     Signal. Dann fehlte der Anfang des ersten Zeichens (C → N/F am Anfang
     jedes Durchgangs). 0,5 % von 2 s sind 10 ms; die Dynamik springt also
     nach den ersten ~10 ms Signal an.
3. **Vorausschau 60 ms, samplegenau, unabhängig von der Blockgröße:**
   - Die Schwelle verarbeitet die Hüllkurve um `lookahead_ms = 60`
     verzögert. Dynamik-Ring und Linien-Gate sehen den Wert 60 ms später.
     Beim ersten Ton nach einer Pause sind beide Kriterien damit schon
     offen, wenn die Schwelle den Tonbeginn erreicht.
   - Der `ToneTracker` liefert das Gate pro Sample (hop-genau), nicht mehr
     einmal pro Block. Vorher wirkte ein großer Block als versteckte
     Vorausschau: Mit den 64-ms-Blöcken der Matrix ging es, mit den
     20-ms-Blöcken der GUI fehlte oft das erste Zeichen. Jetzt ist das
     Ergebnis für 10–128-ms-Blöcke und 8/48 kHz gleich.
   - Der Rauschteppich lernt nur aus rauschähnlichen Werten. Liegt ein Wert
     mehr als 12 dB über dem Teppich (`floor_freeze_db`; bei
     Rayleigh-Rauschen praktisch nie), steigt er so langsam wie bei Tastung
     „an". Sonst lief er auf dem ersten Ton hoch, bevor der Squelch offen
     war.
   - `Thresholder.flush()` verarbeitet am Dateiende die zurückgehaltenen
     60 ms.
   - Eine erste Vorausschau mit 150 ms wurde verworfen: Die Latenz ist
     spürbar, und sie kostete bei −3 dB und tiefem QSB. 60 ms fallen nicht
     auf, weil Zeichen ohnehin erst am Zeichenende erscheinen.
   - Regressionstest: `tests/test_erstes_zeichen.py` (Blöcke 10/20/64 ms,
     Vorlauf 1/3/6 s).
4. **Tempo-Reset:** Fällt `tone_present` weg, schließt `CWDecoder` das
   laufende Zeichen ab und ruft `TimingDecoder.reset_tempo()` auf. Damit
   wird die nächste Station frisch eingemessen. Der Startwert bleibt auf
   30–150 ms (8–40 WPM) geklemmt.
5. **Robustere Tempo-Schätzung:**
   - Vor der Clusterung fallen winzige Teilcluster (weniger als 2 Werte bzw.
     unter 20 %) und unplausible Verhältnisse (> 5) heraus. Ausnahme: Liegen
     die drei neuesten Elemente alle im kleinen Cluster, ist das ein
     Tempowechsel und wird behalten.
   - Störimpulse unter 0,3 Punktlängen fallen immer heraus.
   - `adapt` steigt von 0,35 auf 0,5.
6. **Tempo-Suchbereich 5–60 WPM** (`timing.DIT_MIN_MS = 20`,
   `DIT_MAX_MS = 240`). Schneller als 60 WPM gibt niemand; die Grenze dient
   nur der Robustheit: Je kürzer die kleinste zulässige Punktlänge, desto
   eher wird ein Störimpuls als Element gelernt. Vorher lag die Grenze bei
   12 ms (100 WPM).
7. **Testabdeckung:**
   - `gen.render(rx_filter_hz=…)` bzw. `--rx-filter` simuliert ein schmales
     Empfängerfilter für Signal, Rauschen und QRM zusammen.
   - Die Matrix hat eine elfte Kategorie „CW-Filter" (100–250 Hz,
     SNR 3–15 dB).
   - Die Hälfte der Rauschfälle läuft durch ein solches Filter
     (ergänzt ADR-0017).
   - Vier echte Aufnahmen in `testdata/real/` (Freigabe DF1DS) prüft
     `tests/test_real.py` mit enthaltenen Fragmenten statt Vollvergleich.
     Fragmente, die der Decoder noch nicht liefert, stehen als bekannte
     Lücke in `run_matrix.REAL_KNOWN_GAPS` (xfail). `run_matrix.py --real`
     druckt alle Texte.

**Warum zwei Kriterien:** Jedes allein lässt sich täuschen.

| Kriterium | Wird getäuscht durch |
|---|---|
| Linien-Gate allein | sehr schmales Filter (Rauschen wird fast zur Linie) und Rauschen kurz nach einem echten Ton (Max-Hold) |
| Dynamik-Squelch allein | Impulsstörungen und QSB auf Rauschen |

Rauschen müsste beide gleichzeitig überlisten. Die beiden Größen messen
verschiedene Eigenschaften (Breite im Spektrum gegenüber Verteilung der
Hüllkurve), daher passiert das selten.

## Konsequenzen

- Bei reinem Rauschen, auch durch ein CW-Filter, gibt der Decoder nichts aus
  (Matrix: Rauschen 100 %).
- Nach einer leeren Frequenz misst er das Tempo der nächsten Station neu,
  statt das alte zu verschleppen.
- **Anlaufzeit und Latenz:** Der Dynamik-Squelch bewertet erst 0,5 s nach
  dem Start des Decoders. Die Tastung läuft immer 60 ms hinter dem Audio
  (Vorausschau); dafür ist das erste Zeichen nach einer Pause vollständig.
- **Bekannte Lücken an echten Aufnahmen** (190242): `TALLINN` kommt als
  `T A L L INN` (sehr weite Zeichenabstände des OPs). Seit der Vorausschau
  kommt dort außerdem `UR FST` statt `UR RST`.
- **Schwache Signale:** Ein Signal, das nur knapp über dem Filterrauschen
  liegt (unter etwa 9 dB Linie), bleibt stumm. Das ist gewollt (Leitlinie:
  lieber Lücke als Müll).
- **Unsaubere Handtaste:** Elementlängen, die kontinuierlich streuen, bleiben
  unlesbar. Das ist kein Decoder-Ziel.
- **Neue Parameter:** `TrackerConfig` und `ThresholdConfig` haben neue
  Parameter. Wer sie ändert, misst die Matrix (inkl. CW-Filter und Rauschen)
  vorher und nachher.

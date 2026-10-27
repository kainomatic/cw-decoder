# ADR-0025: Adaptive Zeichenschwelle und Störmark-Filter

**Status:** Accepted

## Kontext

Shack-Test mit Beta 13 (27.10.2026, #20, Auftrag #21). Drei Befunde am
Decoder-Kern, alle aus echten Aufnahmen (`testdata/real/`):

1. **Enge Zeichenabstände.** Die starke Station bei 864 Hz in
   `cw_20261027_194831` tastet Elementpausen von 0,7 Punkten und
   Zeichenpausen von nur 1,2–2,4 Punkten (`▇90 ·62 ▇90 ·63 ▇83 ·77 ▇243
   ·122 ▇93 …`). Die feste Zeichenschwelle `char_thr · dit` (2,2 Punkte)
   liegt darüber; zwei Zeichen werden ein ungültiges Symbol (`*`). IN3TWX
   in `193609` gibt ähnlich eng, dort entstehen gültige, aber falsche
   Zeichen (`LO?` statt `LOUD`, `<KN>S` statt `YES`).
2. **Aussetzer am Rand eines Elements.** Fading/AGC schneidet kurz vor dem
   Ende eines Strichs ein Stück heraus; übrig bleibt ein Rest von
   10–25 ms, der als eigener Punkt zählt (`▇164 ·49 ▇13`).
3. **Teppich-Regel.** Im `Thresholder` darf der Rauschteppich nach 3 s am
   Stück wieder steigen („Dauerträger ist kein CW"). Die Bedingung prüft
   nur `run_ms > 3000`, gilt also auch nach 3 s *Pause* bei geschlossenem
   Squelch.

Oberste Regel (DF1DS): Nichts darf schlechter werden. Jede Änderung wurde
einzeln gemessen (Matrix mit Seeds 1000/5000/7777, `--legacy`,
`tests/test_real.py`, Volltext aller Aufnahmen gegen
`tests/real_baseline.json`) und ist per Config abschaltbar.

## Entscheidung

### Adaptive Zeichenschwelle (`TimingConfig.char_thr_adaptive`, an)

Die Pausen des laufenden Verkehrs (`history` = 24, dasselbe Fenster wie
die Punktlängen-Schätzung) zwischen 0,5 Punkt und der Wortschwelle werden
im log-Bereich in zwei Cluster geteilt. Verfahren: kleinste Streuung
innerhalb der Cluster (Otsu), nur an Stellen mit einer echten Lücke
(Nachbarwerte ≥ Faktor 1,3 auseinander). Gültig nur mit

- mindestens 8 Pausen und je 3 pro Cluster,
- Median-Verhältnis oben/unten ≥ `char_cluster_ratio` (1,4),
- unterem Cluster mit Median ≤ 1,6 Punkte (sieht nach Elementpausen aus).

Die Schwelle ist das geometrische Mittel der Mediane, aber nie außerhalb
der mittleren Hälfte der leeren Strecke zwischen den Clustern – sonst
teilte sie die Pausen anders ein als die Clusterung selbst. Angewendet
wird sie geklemmt auf `char_thr_min..char_thr_max` (1,0…3,0 Punkte) und
nie unter `char_thr_dot_floor` (1,2) × der Punktlänge, die die Töne des
laufenden Zeichens zeigen. Ohne gültige Cluster gilt die feste Schwelle
`char_thr`. Die Wortschwelle bleibt, wie sie war, fällt aber nie unter die
Zeichenschwelle.

Warum kein fester, kleinerer Wert: Der Abstand Element-/Zeichenpause ist
Eigenschaft des Gebers (Keyer 1:3, IN3TWX 1:2–4, die 864-Hz-Station
1:1,7–3,4, Farnsworth 1:6). Ein fester Wert, der die engen Geber trennt,
zerlegt bei normalen Gebern verschliffene Zeichen.

Warum die Ausschlüsse: Ohne die 0,5-Punkt-Grenze bildeten Aussetzer
(10–35 ms) ein eigenes unteres Cluster, die Schwelle fiel auf 1 Punkt
(`CQ KEQ CQ` in 194453). Ohne „echte Lücke" und 3 Werte oben bildete
Otsu am Anfang einer Farnsworth-Sendung ein „Cluster" aus einer
Elementpause und einer Zeichenpause (`OE3` → `OE VT`). Ohne die
Punktlängen-Untergrenze trennte ein Fenster voller Pausen der vorigen
Station (48 ms) die Elementpausen von GI5RSS (73 ms): `G I` → `TTE EE`.

### Trennung ungültiger Symbole (`TimingConfig.char_split`, an)

Ergibt ein Zeichen `*` (kein gültiges Symbol), wird es an seiner längsten
inneren Pause in zwei Zeichen geteilt, wenn diese Pause mindestens
`char_split_ratio` (1,5) × so lang ist wie der Median der übrigen und
beide Teile gültige Zeichen sind. Grund: Beim Stationswechsel enthält das
Pausenfenster noch die vorige Station, die Clusterung reagiert erst nach
einigen Zeichen. Die Regel kann nur ein `*` ersetzen, nie ein gültiges
Zeichen ändern. Sie ist eine Ergänzung zum Auftrag (dort nur Clusterung)
und allein schon in allen drei Seeds besser.

Zeichen aus einer Teilung bekommen höchstens das Vertrauen
`char_split_conf` (0,45, unter `UNSURE_CONF`) und erscheinen damit als
unsicher (grau in der GUI, klein im Terminal). Grund (Review #21): In
lesbarem Material ist die Teilung ein Gewinn (`CIAO`, `PERIL QSO`), in
Störstellen wird aus einem ehrlichen `*` aber plausibel aussehender Text
(`CHCH`, `5555NM`); der Operator soll das sehen. Nur Metadaten, Text und
Matrix unverändert.

### Störmark-Filter (`TimingConfig.glitch_filter`, an)

Nur bei eingemessenem Tempo (`n_marks ≥ conf_warmup_marks`, nie bei der
ersten Station nach `reset_tempo`): Ein Ton kürzer als `glitch_max_dit`
(0,4) Punkte wird mit dem Nachbarton verschmolzen, wenn die Pause
dazwischen kürzer als `glitch_gap_dit` (0,5) Punkte ist. Über einen kurzen
Ton entscheidet ggf. die folgende Pause (Ereignis `gap()`; in `poll()`
erst ab einem Punkt Pause, weil die laufende Pause die Entprellzeit noch
enthält – so fällt die Entscheidung unabhängig von der Blockgröße).

**Verwerfen** von Knacksern (kurzer Ton zwischen zwei langen Pausen,
`glitch_discard`) ist eingebaut, aber **aus**: Bei Fading werden echte
Punkte so kurz, dass sie als Knackser gälten (`DO` → `N O`); Seed 1000
fiel damit um 0,1 Punkte, die Aufnahmen bekamen neue Fehler. Ein Zeichen,
das nur aus dem Störmark bestünde, wird ohnehin nie gefiltert.

Verworfen nach Messung: Lücken unter 0,5 Punkt innerhalb eines Zeichens
ebenfalls zu überbrücken (Aussetzer in der Mitte eines Strichs). Matrix in
allen Seeds schlechter, `ES3YJ` in 190855 verloren.

### Teppich-Regel (`ThresholdConfig.carrier_needs_key`, aus)

`carrier_needs_key=True` lässt den Teppich nur nach 3 s Tastung „an"
steigen, wie der Kommentar es meint. Gemessen: Matrix in allen Seeds
gleich; bei fester Frequenz 864 Hz auf 194831 (28,5–31,8 s) bleibt der
Teppich bei −40…−44 dB statt auf −22 dB zu springen, der Text ist
identisch. In drei echten Aufnahmen ändern sich aber einzelne Zeichen in
Störstellen (gemischt: `…PHIEDN` → `…PHIEBK`, aber auch ein zusätzliches
`E`). Nach Auftrag („korrigieren, wenn unverändert, sonst Befund im ADR")
bleibt die alte Regel Standard; der Schalter ist für den nächsten
Live-Test da.

## Messung

| Stand | Seed 1000 | Seed 5000 | Seed 7777 | `--legacy` | Rauschen |
|---|---|---|---|---|---|
| vorher | 97,70 | 96,70 | 98,43 | 98,27 | 100 |
| nur Trennung | 97,90 | 96,98 | 98,45 | 98,27 | 100 |
| nur Clusterung | 97,83 | 97,15 | 98,47 | 98,27 | 100 |
| beide (Schritt 1) | 97,83 | 97,20 | 98,49 | 98,27 | 100 |
| + Störmark-Filter (Schritt 2) | 97,85 | 97,20 | 98,49 | 98,27 | 100 |
| + Teppich `carrier_needs_key` | 97,85 | 97,20 | 98,49 | 98,27 | 100 |

Synthetisch (`gen.py --char-gap`): Zeichenabstand 1,5–2,0 Punkte vorher
Totalausfall (`* * B *****K`), jetzt sauber bis auf das erste Wort vor dem
Einmessen. Aussetzer (`gen.py --dropouts 0.3`) bei 15–20 WPM jetzt
fehlerfrei.

## Konsequenzen

- 194831 (32–38 s) liefert `4HX 4HX` statt `*X *X`. Die Tastung ist dort
  `....- .... -..-` (vier gleich starke Punkte bei 864 Hz, gleicher
  Abstand), also `4HX`; `VHX` gibt die Aufnahme nicht her.
- Deutlich mehr Text bei Gebern mit engen Zeichenabständen (193609:
  `STEFAN73`, `GE WOLF LOUD`, `BARRY`, `YES HEARD`, `WEAK WEAK`,
  `TAKE CARE`; 202035: `DL4KCA`, `UR RST 599`). Einzelne mehrdeutige
  Stellen kippen anders (`EAT` → `EETT` bei einer Lücke von 2,1 Punkten).
- `TimingDecoder` hält jetzt pro Zeichen die Pausen (`cur_gaps`) und einen
  kleinen Zustand für zurückgehaltene Störmarks; `reset_text` und
  `force_flush` räumen ihn auf.
- Nebenbefund (unverändert, kein Rückschritt): Der Volltext echter
  Aufnahmen hängt schon vorher leicht von der Blockgröße ab (Ausgabe per
  `poll()` am Blockende, Bandbreiten-Nachführung je Block).

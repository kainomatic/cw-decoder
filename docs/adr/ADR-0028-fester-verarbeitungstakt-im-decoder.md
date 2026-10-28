# ADR-0028: Fester Verarbeitungstakt im Decoder

**Status:** Accepted

## Kontext

Seit ADR-0018/#8 galt: „`CWDecoder.process` ist blockgrößen-unabhängig“.
Das stimmte für den `Thresholder` (60-ms-Vorausschau, Sample für Sample),
aber nicht für die Kette. Die GUI liefert 20-ms-Blöcke (160 Samples bei
8 kHz), die Testmatrix 512. Live und Test sahen also nicht denselben Text
(#22).

**Messung** (`python tests/run_matrix.py --blocks`, echte Aufnahmen plus
Matrix Seed 1000, Blockgrößen 80/160/320/512/1024): **39 von 119 Fällen**
hingen von der Blockgröße ab; mittlere Ähnlichkeit zu 160: 98,7 % (80),
99,2 % (320), 98,5 % (512), 97,4 % (1024).

**Ursachen.** Für die Zuordnung lief die Kette im festen 10-ms-Takt, und je
ein Aspekt wurde wieder „einmal je Aufrufer-Block“ gemacht. Alle Aspekte
„je Block“ ergaben exakt den alten Text (Kontrolle). Gezählt ist, wie oft
ein Aspekt allein die Abhängigkeit wieder erzeugt:

| Aspekt (je Aufrufer-Block statt im Takt) | Fälle |
|---|---|
| Mischfrequenz der Hüllkurve: `tracker.freq` vom **Blockende** für den ganzen Block | 31 |
| Einschwingen des Thresholders: Teppich = Median des **aktuellen Blocks** | 16 |
| `poll()` und Absatz-Prüfung am Blockende (Vermutung 3) | 10 |
| Bandbreite/Entprellung nach einem Ton erst nach dem Block (Vermutung 1) | 9 |
| Lock-Wechsel und Tonverlust einmal je Block (Vermutung 2) | 7 |

Bei 17 Fällen reicht genau ein Aspekt (11-mal die Mischfrequenz), einer
(Drift #7) braucht drei zugleich. Die beiden häufigsten Ursachen standen
nicht auf der Liste der Vermutungen.

**Was der feste Takt allein kostet.** Nur in 10-ms-Teilblöcke zerlegen
senkte die Matrix (Seed 1000) von 97,85 auf 96,91 %. Zuordnung wie oben,
Aufrufer 512: Mischfrequenz je Block 97,52, Bandbreite je Block 97,08,
poll 96,83, Einschwingen 96,99, Lock 96,46. Der alte Code hatte zwei
zufällige Vorteile:
1. Die Frequenz vom Blockende sah im Mittel ~32 ms in die Zukunft. Rastet
   der Tracker auf eine neue Station ein, bekam so schon der Anfang des
   ersten Elements die richtige Mischfrequenz.
2. Die Grenzfrequenz wurde mit Verzögerung nachgeführt; sofort nach jedem
   Ton umzuschalten verschlechtert z. B. einen Tempowechsel 15 → 32 WPM
   (`test_basic.py::test_speed_change`).
Längere Takte (16/32/64 ms: 97,18/97,33/97,85 %) holen das nur zurück,
weil sie dasselbe Zufallsverhalten nachbauen.

## Entscheidung

1. **Fester Takt** (`DecoderConfig.chunk_ms` = 10 ms): `process()` zerlegt
   die dezimierten Samples in Teilblöcke dieser Länge, der Rest wartet auf
   den nächsten Aufruf, `flush()` verarbeitet ihn. Lock-/Tonverlust,
   `poll()`, Absatz und Einschwingen laufen damit im festen Raster; das
   Ergebnis hängt **per Konstruktion** nicht von der Blockgröße des
   Aufrufers ab.
2. **Frequenz-Vorausschau** (`freq_lookahead_ms` = 60 ms): Die Hüllkurve
   (und alles danach) läuft so weit hinter dem Tracker her und mischt mit
   der Frequenz, die der Tracker bis „jetzt“ kennt. Lock und Gate gehen
   im Zeitraster der Hüllkurve mit (gespeichert je Teilblock). Das ist
   die deterministische Form des alten Vorteils 1; 60 ms entsprechen der
   Vorausschau des Thresholders.
3. **Bandbreiten-Takt** (`bw_step_ms` = 60 ms): Nach einem Ton werden
   Grenzfrequenz und Entprellzeit nur in diesem Takt nachgeführt, nicht
   sofort. Lock-Wechsel und Tonverlust setzen sie weiter sofort.
4. **Einmess-Regel** (`TimingConfig.warmup_min_mark`, an): Vor dem 8. Ton
   (Störmark-Filter noch aus, z. B. nach `reset_tempo`) zählt ein Ton unter
   `dit_min_ms` (20 ms, Punkt bei 60 WPM) nicht als Element. Gefunden an
   `cw_20261026_190445`: Ein 17-ms-Störimpuls direkt nach einem
   Tonverlust zog das frische Tempo auf 60 WPM, und es blieb dort hängen
   (breiteres Filter, kürzere Entprellung, mehr Störimpulse). Der alte
   Code hatte dasselbe Problem bei 80er-Blöcken; ob nach dem Reset 11 oder
   17 ms kamen, war Zufall der Blockgrenzen.

Gewählt aus einem Raster über drei Seeds (Takt 5/10/16 ms, Vorausschau
0–120 ms, Bandbreiten-Takt 10–60 ms); Kriterium: kein Seed, Legacy, keine
Rausch-Kategorie und kein bestehender Test schlechter.

## Ergebnis

| | vorher | nachher |
|---|---|---|
| Matrix Seed 1000 / 5000 / 7777 | 97,85 / 97,2 / 98,49 % | 97,94 / 97,77 / 98,61 % |
| alte Matrix (`--legacy`) | 98,27 % | 98,41 % |
| Rauschen (alle Seeds) | 100 % | 100 % |
| blockabhängige Fälle (119) | 39 | 0 |
| Fragmente echter Aufnahmen | alle, „UR RST“ bekannte Lücke | alle, „UR RST“ wieder gefunden |
| Laufzeit 373 s Audio, 160er-Blöcke | 6,65 s | 7,90 s (2,1 % Echtzeit) |

Volltext gegen `tests/real_baseline.json` (alter Code, 512er-Blöcke):
fünf Aufnahmen unter 0,98 (0,87–0,977). Bei allen liegt der neue Text
näher an der Baseline als der alte Code mit seiner ungünstigsten
Blockgröße; bei 190445, 194831 und 231339 liegt er näher am alten
GUI-Text (160) als der alte 512er-Text. Ausnahme 190855 (0,955): ein
Rausch-`E` weniger in einem 45-Zeichen-Text.

## Konsequenzen

- Live (GUI, 20 ms) und Test (Matrix, 512) sehen exakt denselben Text;
  `tests/test_blockgroesse.py` prüft das für alle echten Aufnahmen und 20
  Matrix-Fälle bei 80/160/512/1024 Samples (slow, läuft in der CI).
- Zusätzliche Latenz bis 10 ms (Teilblock) plus 60 ms
  (Frequenz-Vorausschau) vor dem Thresholder; die Zeichen kommen ohnehin
  erst nach der Zeichenpause.
- `CWDecoder.t_ms` zählt im Zeitraster der Hüllkurve. Zeitstempel im
  Decodier-Log und für „Nochmal hören“ liegen damit näher an der Stelle im
  Audio (Unterschied < 0,1 s).
- Rechenzeit +19 % bei 20-ms-Blöcken (mehr Aufrufe von Filtern und
  Thresholder je Sekunde), weiter rund 2 % Echtzeit.
- Neue Logik darf nie wieder von der Blockgrenze des Aufrufers abhängen;
  was im Takt laufen soll, gehört in `_process_delayed`.
- Die Schalter liegen in `DecoderConfig` (`chunk_ms`, `freq_lookahead_ms`,
  `bw_step_ms`) und `TimingConfig.warmup_min_mark`.

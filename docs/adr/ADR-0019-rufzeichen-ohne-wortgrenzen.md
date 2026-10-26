# ADR-0019: Rufzeichen ohne Wortgrenzen erkennen

**Status:** Accepted

## Kontext

Der Rufzeichen-Spotter (`cwdecoder/callsign.py`) prüfte bisher nur ganze
Wörter. Bei Gebern mit weiten Zeichenabständen sind die Wortgrenzen
unzuverlässig: In der Aufnahme 231339 (`testdata/real/`, #10) liegt das
Verhältnis Wort-/Zeichenpause nur bei etwa 1,4 statt 2,3. Rufzeichen kleben
deshalb an Nachbarwörtern (`DEDJ7PR`, `IK2ULVDEOY*T`, `DJ7PRRFB`) oder werden
zerrissen (`OY 1 CT`). Eine bessere Wortschwelle (1,35 × Zeichenpause im
Einzel-Cluster-Fall) hilft, löst den Überlappungsbereich aber nicht auf.
Die Rufzeichen sollen trotzdem als Buttons erscheinen, ohne dass Müll
dazukommt (Leitlinie: lieber Lücke als Müll).

## Entscheidung

Der Spotter prüft am Ende jedes Wortes auf zwei Wegen.

1. **Neue Rufzeichen innerhalb eines Wortes** (`calls_in_word`):
   - Ein Treffer muss das Rufzeichen-Muster ganz erfüllen und an einer
     Grenze beginnen und enden. Grenzen sind Wortanfang und Wortende, ein
     Prosign bzw. `*`/`?` (im Strom als Trennzeichen) und ein `DE` direkt
     davor oder danach.
   - Bei überlappenden Treffern gewinnt der direkt nach `DE`, sonst der
     längere.
   - Ist der Treffer kürzer als das Wort (zusammengeklebt), darf der Suffix
     höchstens 3 Buchstaben haben. Sonst ist das Ende unklar (`DJ7PRKM` =
     `DJ7PR` + `KM`).
   - Verlängert ein Kandidat ein bereits erkanntes Rufzeichen nur um
     Buchstaben, zählt das bekannte Rufzeichen.
2. **Bekannte Rufzeichen im Zeichenstrom:**
   - Die letzten 40 Zeichen ohne Leerzeichen werden nach allen schon
     erkannten Rufzeichen durchsucht.
   - Ein Treffer zählt, wenn er im gerade beendeten Wort endet und an einer
     Grenze beginnt (Wortgrenze, Trennzeichen oder `DE` davor). So werden
     `DJ7PRRFB` und das zerrissene `OY 1 CT` gefunden.
   - Neue Rufzeichen entstehen auf diesem Weg nie. Aus Teilstücken über
     Wortgrenzen hinweg würde sonst geraten.

Jedes Vorkommen (Rufzeichen und Position im Strom) zählt nur einmal. Die
Entprellung bleibt: Ein Rufzeichen wird höchstens alle 30 s neu gemeldet,
aber jedes Vorkommen zählt mit.

## Konsequenzen

- An der Aufnahme 231339 zählt der Spotter 16 Rufzeichen-Vorkommen statt
  8 aus ganzen Wörtern. Neu gemeldet werden dabei keine falschen.
- Ein Rufzeichen, das nur zusammengeklebt **und** mit unklarem Ende
  vorkommt (`1CTDEDJ7PRKM` als erstes Auftreten), wird erst erkannt, wenn es
  einmal sauber kam. Das ist gewollt.
- Ein bekanntes kürzeres Rufzeichen verdeckt ein längeres mit gleichem
  Anfang (`DL1AB` bekannt, `DL1ABC` kommt). Das ist selten und wird in Kauf
  genommen.
- Bestehende Fehlerkennungen ganzer Wörter bleiben, z. B. `J7PR` aus einem
  verlorenen `D`. Diese Regel ändert daran nichts.
- Tests: `tests/test_callsign.py` (zusammengeklebte und zerrissene
  Beispiele), `tests/test_real.py` (`REAL_SPOTS`).

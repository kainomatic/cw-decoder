# ADR-0024: Ringpuffer – letzte Sekunden sichern und nachhören

**Status:** Accepted

## Kontext

Fehldecodierungen fallen am Funkgerät erst auf, wenn sie schon vorbei sind.
Eine Daueraufnahme (Haken „Aufnahme") läuft dann meist nicht, und wer sie
immer mitlaufen lässt, sammelt Stunden WAV ohne Markierung der Stelle.
Außerdem will der Operator nachhören können, wenn Ohr und Decoder uneins
sind. Entscheidung DF1DS (27.10.2026, Ideensammlung #17, Auftrag #19):
Ringpuffer mit „Letzte 30 s speichern" und „Nochmal hören".

## Entscheidung

**Ringpuffer im Live-Pfad.** `cwdecoder/ringbuffer.py`, tk-frei:
- `AudioRing(fs, seconds)`: numpy-Array fester Größe (float32), Schreiben
  per Slice ohne Allokation, Lesen als Kopie; beides unter einem Lock.
  Geschrieben wird in `LiveDecoder.feed` (Decoder-Thread, vor Aufnahme und
  Decoder), nicht im Soundkarten-Callback.
- `TokenRing`: die Decoder-Ausgaben `(t_s, token, conf)` mit derselben
  Zeitbasis wie das Decodier-Log (`dec.t_ms`, Sekunden seit Start).
- Größen in `config.json`: `ring_seconds` 60 (10–300), `save_last_s` 30
  (5…`ring_seconds`, größere Werte werden gekürzt), `replay_s` 10 (3–30),
  `replay_slow` (bool). 60 s sind bei 8 kHz 1,9 MB, bei 48 kHz 11,5 MB.
  Die Puffergröße gilt ab dem nächsten Start des Decoders. Einstellbar unter
  Einstellungen → „Puffer und Nochmal hören…".
- Nur die GUI legt einen Ring an; der Terminal-Modus hat keinen.

**„Letzte 30 s speichern" (Strg+S).** Schreibt im Hintergrund-Thread
`cw_JJJJMMTT_HHMMSS_NNN_letzte30s.wav` (Schema der Aufnahmen, ADR-0003;
Zahl = `save_last_s`) und daneben `…_letzte30s.txt` mit den Tokens des
Fensters, Zeiten relativ zum Anfang des Ausschnitts, drei Spalten wie das
Decodier-Log (ADR-0023). Ort: `Dokumente\CW Decoder\Aufnahmen`. Ist weniger
im Puffer, wird gespeichert, was da ist; die Statuszeile nennt die echte
Länge. Fehler beim Schreiben: `SaveLastError` mit Klartext (ADR-0007).
Das erste Zeichen der TXT kann vor dem Ausschnitt begonnen haben (Ausgabe
kommt erst nach dem Zeichenende).

**Warum WAV.** Gleiches Format wie die Aufnahmen: `decode_wav`, die
Testmatrix (`--real`) und jedes Audioprogramm lesen es ohne Umweg. Ein
Fehlfall wird so mit einem Klick zur Testdatei für `testdata/`.

**„Nochmal hören" (Strg+R).** `cwdecoder/replay.py`: Kopie der letzten
`replay_s` Sekunden, Pegel auf Spitze 0,5 angeglichen (höchstens 30-fach),
5 ms ein-/ausgeblendet, Wiedergabe in einem eigenen Thread über
`sounddevice.OutputStream` auf dem Standard-Ausgabegerät. Der Decoder und
der Ring laufen weiter. Während der Wiedergabe heißt der Knopf „Stopp";
ein zweiter Start wird abgelehnt. Kann das Gerät die Eingangsrate nicht,
wird mit scipy auf 48/44,1 kHz umgerechnet (gleiche Dauer und Tonhöhe).
Kein Ausgabegerät / belegt: `ReplayError` mit Klartext, kein Absturz. Die
Auswahl des Ausgabegeräts ist ein eigenes Issue, falls nötig.

**Langsamer (0,7×) nur ohne Tonhöhenänderung.** Zeitdehnung per WSOLA
(`replay.stretch`, rund 30 Zeilen numpy): Fenster 40 ms, 50 % Überlappung,
jedes Fenster wird ±4 ms (eine Periode ab 250 Hz) so verschoben, dass es
phasenrichtig an das vorige anschließt. Der Ton bleibt auf seiner Frequenz,
Tastpausen bleiben Pausen. **Kein einfaches Resampling:** Es senkt die
Tonhöhe um den Faktor 0,7 (700 Hz → 490 Hz), der Ton landet außerhalb des
gewohnten Filters und klingt anders als auf dem Band.

## Konsequenzen

- Fehlfälle lassen sich ohne Daueraufnahme sichern; WAV und TXT passen
  zueinander (Test: `decode_wav` auf der WAV liefert den Text der TXT).
- Bis zu 11,5 MB (48 kHz, 60 s) bzw. 58 MB (300 s) zusätzlicher Speicher.
- Im reinen Rauschen kann die Dehnung kurze Scheintöne bilden; zum Hören
  unerheblich, die gedehnte Fassung ist nicht für den Decoder gedacht.
- Die Knöpfe stehen in einer zweiten Zeile unter der Werkzeugleiste (in der
  ersten ist bei 760–900 px Breite kein Platz).

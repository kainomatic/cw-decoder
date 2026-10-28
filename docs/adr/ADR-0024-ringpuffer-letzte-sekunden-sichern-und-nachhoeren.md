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
  (5…`ring_seconds`, größere Werte werden gekürzt), `replay_s` 10 (3–30);
  seit #25 dazu `replay_hold_s`, `replay_rate`, `output_device` (siehe
  Nachtrag unten; `replay_slow` entfällt). 60 s sind bei 8 kHz 1,9 MB, bei 48 kHz 11,5 MB.
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

## Nachtrag #25 (28.10.2026): Festhalten mit Verfall, Tempo-Regler, Ausgabegerät

Wünsche DF1DS aus dem Shack-Test (#20): Beim zweiten Strg+R hörte man schon
anderes Material, 0,7× war mal zu schnell, mal zu langsam, und die
Wiedergabe lief immer über die Standard-Ausgabe.

**Festhalten mit Verfall** (`replay.ReplayHold`, tk-frei). Strg+R fasst die
letzten `replay_s` Sekunden als Kopie und hält sie fest. Jedes weitere
Strg+R innerhalb von `replay_hold_s` (Standard 5 s, 1–60) **nach dem Ende
der Wiedergabe** (auch nach „Stopp") spielt denselben Ausschnitt, beliebig
oft. Vergeht die Frist, verfällt er; das nächste Strg+R fasst neu. Kein
Knopf „Neu fassen": Die Frist ist die einfachere Bedienung (Präzisierung
DF1DS, #20). Decoder und Ring laufen durchgehend weiter. Strg+S während des
Festhaltens speichert genau diesen Ausschnitt als `…_festgehalten.wav` plus
TXT mit den Tokens seines Zeitfensters (`ringbuffer.save_clip`), sonst wie
bisher die letzten `save_last_s`. Statuszeile „festgehalten 10 s – noch
4 s" (Countdown aus `_poll`), Knopf „Nochmal (festgehalten)".

**Tempo-Regler 0,5×…1,0×** neben dem Knopf. Die Dehnung läuft als Strom
(`replay.Stretcher`): je Block ein halbes Fenster (20 ms), der Zustand
(Lage des vorigen Fensters, Überlappungspuffer) bleibt zwischen den
Blöcken. Der Wiedergabe-Thread fragt je Block eine Funktion nach dem Tempo,
die nur eine Zahl der GUI liest (`App.replay_rate_now`, kein tk im Thread,
ADR-0009); der Regler wirkt so sofort, auch mitten im Durchgang. Bei 1,0
wird das Original unverändert durchgereicht (gleiche Fensterlage, Summe der
Hann-Fenster = 1). Der Regler beginnt mit `replay_rate` aus den
Einstellungen; Verschieben gilt nur für den festgehaltenen Ausschnitt, mit
neuem Material springt er zurück. Unter 0,5× wird nicht angeboten (die
Dehnung klingt dann hallig). Alte Configs: `replay_slow=True` → 0,7. Die
Verfallsfrist zählt ab dem Ende der gedehnten Wiedergabe. Kann das Gerät
die Eingangsrate nicht, wird der Ausschnitt vor der Dehnung umgerechnet.

**Ausgabegerät** wählbar im Dialog „Puffer und Nochmal hören…" (Liste der
Ausgänge aus `sounddevice.query_devices()`, „Standard" voreingestellt).
Gespeichert wird der Name, gesucht wird per Namensteil wie beim Eingang –
robust gegen wechselnde Gerätenummern. Fehlt das Gerät oder lässt es sich
nicht öffnen, spielt der Player über die Standard-Ausgabe
(`OutputDeviceMissingError`, Klartext „Ausgabegerät nicht gefunden"; Dialog
einmal je Sitzung bzw. nach Gerätewechsel, sonst nur die Statuszeile).

## Konsequenzen

- Fehlfälle lassen sich ohne Daueraufnahme sichern; WAV und TXT passen
  zueinander (Test: `decode_wav` auf der WAV liefert den Text der TXT).
- Bis zu 11,5 MB (48 kHz, 60 s) bzw. 58 MB (300 s) zusätzlicher Speicher.
- Im reinen Rauschen kann die Dehnung kurze Scheintöne bilden; zum Hören
  unerheblich, die gedehnte Fassung ist nicht für den Decoder gedacht.
- Die Knöpfe stehen in einer zweiten Zeile unter der Werkzeugleiste (in der
  ersten ist bei 760–900 px Breite kein Platz).

# CLAUDE.md – Projektkontext für Claude Code

## Was das ist
Live-Morsedecoder in Python für Audio vom Funkgerät (USB-Audio oder VB-Cable
unter Windows). Ziel: Text live anzeigen, erkannte Rufzeichen per Klick an
N1MM Logger+ übergeben. Vorbild ist "CW Reader", nur mit zuverlässigerer
Geschwindigkeits-Erkennung und besserer Rauschunterdrückung.

Die Architektur und der Decoder-Kern wurden in einer Claude-Desktop-Session
entworfen und gegen synthetische Signale getestet. Diese Session (Claude
Code) ist für das Testen am echten Gerät, Bugfixes und Anpassungen zuständig.
Der Mensch reicht Prompts und Ergebnisse zwischen beiden Sessions hin und her;
Fragen zur Architektur und größere Umbauten gehen an die Desktop-Session.

## Arbeitsregeln
- Sprache in Code-Kommentaren, Commit-Messages und Antworten: Deutsch.
- Vor jeder Änderung an `cwdecoder/dsp.py`, `timing.py` oder `decoder.py`:
  `python tests/run_matrix.py` laufen lassen und den Mittelwert notieren.
  Nach der Änderung wieder. Der Mittelwert (zuletzt ~95 %) darf nicht sinken,
  sonst die Änderung begründen oder zurücknehmen.
- Tuning-Parameter liegen in den `*Config`-Dataclasses (`TrackerConfig`,
  `ThresholdConfig`, `TimingConfig`, `DecoderConfig`). Keine Magic Numbers
  tief im Code verstecken.
- Keine neuen Abhängigkeiten außer numpy, scipy, sounddevice ohne Rückfrage.
  Die GUI bleibt bei tkinter (ist in Python unter Windows dabei).
- Echte Aufnahmen vom Funkgerät kommen nach `testdata/` (WAV, 8–48 kHz) und
  werden mit `python -m cwdecoder.decode_wav datei.wav --trace` ausgewertet.
  Aufnahmen bitte committen, sie sind die wichtigsten Testdaten
  (`.gitignore` anpassen, falls sie klein genug sind, < 5 MB pro Datei).
- Jede Änderung als eigener, kleiner Commit mit aussagekräftiger Message.

## Befehle
```
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
python tests/test_basic.py            # Schnelltests
python tests/run_matrix.py            # Testmatrix (Störungen, Tempi, SNR)
python -m cwdecoder.live --list       # Audiogeräte
python -m cwdecoder.live --device "USB" --record testdata/x.wav
python -m cwdecoder.gui               # Oberfläche
python -m cwdecoder.gen "CQ TEST" -o t.wav --wpm 25 --snr 6
python -m cwdecoder.decode_wav t.wav --expect "CQ TEST"
```

## Signalkette (Reihenfolge ist wichtig)
Audio -> `Decimator` (auf ~8 kHz) -> `ToneTracker` (FFT, Tonfrequenz) ->
`Envelope` (Quadraturmischer + Tiefpass, Bandbreite abhängig vom Tempo) ->
`Thresholder` (Rauschteppich/Signalpegel, Hysterese, Squelch, Entprellung ->
`KeyEvent(on, duration_ms)`) -> `TimingDecoder` (Punktlänge per Clusterung,
Zeichen/Wortgrenzen, Ausgabe per Timeout) -> `morse.decode_symbol`.
`CWDecoder.process(samples)` verbindet alles und ist blockgrößen-unabhängig.

Wichtige Zusammenhänge:
- `TimingDecoder.dit_ms` steuert rückwärts die Filterbandbreite und die
  Entprellzeit (`CWDecoder._update_bandwidth`). Wer dort etwas ändert,
  ändert die ganze Kette.
- Der `Thresholder` schätzt den Rauschteppich im linearen Bereich (Mittel),
  nicht im dB-Bereich; das ist Absicht (Rayleigh-Einbrüche).
- Der `ToneTracker` nutzt Max-Hold mit Abklingen, damit der Ton über
  Tastpausen gehalten wird. Sprung > 40 Hz = neue Station übernehmen.

## Bekannte offene Punkte (Stand: erste Version)
1. GUI (`gui.py`) wurde ohne Display geschrieben und nie gestartet. Erwartete
   Baustellen: Layout, Canvas-Größe beim ersten Zeichnen, Threading beim
   Stop/Start, Gerätewahl.
2. `n1mm.EntryWindowTyper` (ctypes/user32) ist unter Windows ungetestet:
   Fenstersuche über Prozessname `N1MMLogger`, dann `SetForegroundWindow`
   und `SendInput`. Prüfen, ob das Rufzeichen im Entry Window ankommt und ob
   Alt+W tatsächlich "Wipe" ist. Alternative, falls das hakt: Spot-Server
   (`n1mm.SpotServer`, Telnet 127.0.0.1:7373) ist getestet.
3. `sounddevice` unter Windows: Welche Host-API (MME/WASAPI/DirectSound)
   liefert 8 kHz direkt? `live.open_stream` probiert 8000, 48000, 44100.
   Beim USB-Audio vom Funkgerät und bei VB-Cable prüfen, ob das sauber läuft
   und ob der Pegel passt (zu niedrig = Squelch bleibt zu, zu hoch =
   Clipping, beides in der Statuszeile am SNR erkennbar).
4. Schwache Signale: ab ~0 dB SNR (2,4 kHz) steigen die Fehler. Ideen, erst
   nach Absprache: Mehrheitsentscheid über mehrere Bandbreiten, weicher
   Decoder (Wahrscheinlichkeiten statt harter Schwellen).
5. Farnsworth/gedehnte Abstände: Wortschwelle passt sich erst nach ~3
   Zeichenpausen an; die ersten Wörter werden ggf. zerhackt.

# CW Decoder

Live-Morsedecoder für Audio vom Funkgerät (USB-Audio, VB-Cable, Line-In) mit
automatischer Tonverfolgung, adaptiver Rauschunterdrückung, selbstlernender
Gebegeschwindigkeit und Anbindung an N1MM Logger+.

## Installation (Windows)

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Python 3.10 oder neuer. `sounddevice` bringt PortAudio mit, es muss nichts
weiter installiert werden.

## Benutzung

Geräte anzeigen:

```
python -m cwdecoder.live --list
```

Live im Terminal (Gerät per Nummer oder Namensteil):

```
python -m cwdecoder.live --device "USB Audio"
python -m cwdecoder.live --device 3 --record qso.wav
```

Grafische Oberfläche mit Spektrum, Text, Rufzeichen-Buttons und N1MM:

```
python -m cwdecoder.gui
```

Ein Klick ins Spektrum setzt die Tonfrequenz fest (Haken "Ton automatisch
suchen" geht aus); Haken wieder setzen schaltet zurück auf Automatik.

WAV-Datei offline decodieren (zum Tunen und zum Nachstellen von Problemen):

```
python -m cwdecoder.decode_wav aufnahme.wav
python -m cwdecoder.decode_wav aufnahme.wav --expect "CQ TEST DE DL1ABC" --trace
```

Testsignal erzeugen:

```
python -m cwdecoder.gen "CQ TEST DE DL1ABC K" -o test.wav --wpm 28 --snr 6 --drift 60 --qsb 0.4 --qsb-depth 0.7
```

Testmatrix (verschiedene Tempi, SNR, Drift, QSB, QRM) laufen lassen:

```
python tests/run_matrix.py
```

## Wie es funktioniert

1. **Tonverfolgung** (`dsp.ToneTracker`): FFT über 128 ms, alle 16 ms, im
   Bereich 300–1200 Hz. Max-Hold mit Abklingen hält den Ton auch über
   Tastpausen fest. Der stärkste Peak (mit Sub-Bin-Interpolation) wird weich
   nachgeführt; springt eine deutlich andere Linie hoch, wird umgeschaltet.
2. **Hüllkurve** (`dsp.Envelope`): Quadraturmischer auf 0 Hz plus Tiefpass
   3. Ordnung. Die Filterbandbreite wird aus der erkannten Geschwindigkeit
   abgeleitet (langsam = schmal = weniger Rauschen, schnell = breiter), mit
   Grenzen 25–150 Hz.
3. **Schwelle** (`dsp.Thresholder`): Rauschteppich als Mittelwert im linearen
   Bereich, Signalpegel mit schnellem Anstieg und langsamem Abfall (bei
   Tastung an schneller, damit QSB nachgeführt wird). Ein-/Ausschaltschwelle
   liegen 6 bzw. 10 dB unter dem Signalpegel, bei schwachem Signal
   proportional zwischen Rauschen und Signal. Squelch bei < 10 dB Abstand,
   Entprellung relativ zur Punktlänge.
4. **Timing** (`timing.TimingDecoder`): Punktlänge wird laufend aus den
   letzten 24 Ton- und Pausenlängen per Clusterung geschätzt (Punkte/Striche,
   Element-/Zeichenpausen). Die Wortschwelle passt sich an gedehnte
   Zeichenabstände (Farnsworth) an. Zeichen werden per Timeout ausgegeben,
   nicht erst beim nächsten Ton.
5. **Rufzeichen** (`callsign.py`): Wörter, die wie Rufzeichen aussehen,
   erscheinen als Buttons in der GUI.

## N1MM Logger+

N1MM nimmt laut Doku keine Rufzeichen per UDP entgegen (eingehend nur
Spektrumdaten und QSY auf Port 13064), deshalb zwei Wege:

- **Tastatur** (Standard): Klick auf ein Rufzeichen holt das N1MM-Fenster in
  den Vordergrund, sendet optional Alt+W (Wipe) und tippt das Rufzeichen in
  das Entry Window.
- **Spots**: Das Programm ist ein Mini-DX-Cluster auf `127.0.0.1:7373`.
  In N1MM: Window → Telnet → Adresse `127.0.0.1`, Port `7373` eintragen und
  verbinden. Angeklickte Rufzeichen erscheinen als Skimmer-Spot auf der
  aktuellen Frequenz in der Bandmap.

Damit das Programm die Frequenz kennt: in N1MM unter Config → Configure
Ports → Broadcast Data den Haken bei "Radio" setzen (Standard
`127.0.0.1:12060`).

## Projektstruktur

```
cwdecoder/
  gen.py         Testsignal-Generator (Text -> WAV mit Störungen)
  dsp.py         Decimator, ToneTracker, Envelope, Thresholder
  timing.py      Geschwindigkeits-Schätzung, Punkt/Strich/Pausen -> Zeichen
  morse.py       Morsetabelle inkl. Prosigns
  decoder.py     Gesamtkette (CWDecoder)
  decode_wav.py  Offline-Decoder mit Bewertung
  live.py        Soundkarte -> Terminal
  gui.py         Tkinter-Oberfläche
  callsign.py    Rufzeichen-Erkennung
  n1mm.py        RadioInfo-UDP, Tastatur-Übergabe, Spot-Server
tests/
  run_matrix.py  Testmatrix
```

## Stand / offene Punkte

- Die DSP-Kette ist gegen synthetische Signale getestet (Testmatrix ~95 %
  Zeichen-Übereinstimmung, bis ca. 0 dB SNR in 2,4 kHz). Echte Aufnahmen
  vom Funkgerät (`--record`) sind der nächste Schritt zum Feintuning.
- Die GUI und die Tastatur-Übergabe an N1MM wurden unter Linux ohne
  Display geschrieben und müssen unter Windows einmal durchgeklickt werden.
- Mögliche Erweiterungen: mehrere Signale gleichzeitig (Multi-Decoder über
  das Band), Wahrscheinlichkeits-Decoder statt harter Schwellen bei sehr
  schwachen Signalen, Rufzeichen-Plausibilität über Master-Callsign-Datei.

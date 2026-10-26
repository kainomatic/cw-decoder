# CW Decoder

Live-Morsedecoder für Audio vom Funkgerät (USB-Audio, VB-Cable, Line-In) mit
automatischer Tonverfolgung, adaptiver Rauschunterdrückung, selbstlernender
Gebegeschwindigkeit und Anbindung an N1MM Logger+.

## Installation (Windows, Setup-Datei)

1. Unter [Releases](https://github.com/kainomatic/cw-decoder/releases) die
   Setup-Datei herunterladen:
   - **Stable:** `CWDecoder-Setup-vX.Y.Z.exe` — für den Funkbetrieb.
   - **Beta:** `CWDecoder-Beta-Setup-vX.Y.Z.exe` (als „Pre-release"
     markiert) — Vorabversion zum Testen.
2. Setup starten und den Assistenten durchklicken (Admin-Rechte nötig,
   Windows 10/11, 64 Bit). Danach steht „CW Decoder" im Startmenü.

**SmartScreen-Warnung:** Die Setup-Dateien sind nicht signiert (ADR-0015).
Beim ersten Start meldet Windows ggf. „Der Computer wurde durch Windows
geschützt". Dann auf **Weitere Informationen → Trotzdem ausführen**
klicken. Setup-Dateien nur aus den Releases dieses Repos verwenden; sie
werden dort automatisch aus dem getaggten Quelltext gebaut.

**Stable und Beta** sind zwei getrennte Programme und können gleichzeitig
installiert sein und laufen:

| | Stable | Beta |
|---|---|---|
| Startmenü | CW Decoder | CW Decoder Beta (Fenstertitel mit „BETA") |
| Programmordner | `C:\Program Files\CW Decoder` | `C:\Program Files\CW Decoder Beta` |
| Einstellungen, Log | `%APPDATA%\CWDecoder\` | `%APPDATA%\CWDecoder-Beta\` |
| Updates | nur Stable-Releases | nur Beta-Releases |

**Updates:** Kurz nach dem Start fragt das Programm bei GitHub nach einer
neueren Version seines Kanals (abschaltbar über den Haken „Nicht mehr an
Updates erinnern"; `update_check` in `config.json`). Ist eine da, zeigt ein
Dialog die neue Version und einen Link zu den Änderungen.
„Herunterladen und installieren" lädt das Setup, beendet den CW Decoder,
installiert still (Windows fragt nach Admin-Rechten) und startet die neue
Version. „Später" lässt einen Hinweis im Hilfe-Menü stehen. Von Hand:
**Hilfe → Nach Updates suchen**. Ohne Internet startet das Programm normal.

**Deinstallieren** über Windows-Einstellungen → Apps. Die Frage, ob
Einstellungen und Logs gelöscht werden sollen, ist mit „Nein" vorbelegt;
Aufnahmen bleiben immer erhalten.

## Entwicklung (aus dem Quelltext)

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Python 3.12 (Referenzversion). `sounddevice` bringt PortAudio mit, es muss
nichts weiter installiert werden. Für die Tests zusätzlich
`pip install -r requirements-dev.txt`. EXE und Installer selbst bauen:
`docs/BUILD.md`.

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
python -m cwdecoder.gui --n1mm   # N1MM-Anbindung gleich beim Start an
```

Die N1MM-Anbindung ist standardmäßig aus und belegt erst Ports (UDP 12060,
TCP 7373), wenn der Haken "N1MM-Anbindung" gesetzt wird.

Installiert heißt das Programm `CWDecoder.exe`; dieselben Funktionen gibt
es dort per Kommandozeile: `CWDecoder.exe --decode datei.wav`,
`CWDecoder.exe --list-devices`, `CWDecoder.exe --version`.

Die GUI merkt sich Gerät, feste Tonfrequenz und die Haken. Ablageorte:

| Was | Wo (Windows) |
|-----|--------------|
| Einstellungen, Log, Lockfile | `%APPDATA%\CWDecoder\` (`config.json`, `logs\cwdecoder.log`); Beta: `%APPDATA%\CWDecoder-Beta\` |
| Aufnahmen (Haken "Aufnahme") | `Dokumente\CW Decoder\Aufnahmen\` (Datei → Aufnahmeordner öffnen) |

Den Log-Ordner öffnet auch **Hilfe → Log-Ordner öffnen**.

Probleme melden: Hilfe → Fehler melden… zeigt einen Bericht (Version, System,
Audiogerät, letzte Logzeilen) und öffnet auf Wunsch ein vorausgefülltes
GitHub-Issue im Browser. Das Programm sendet selbst nichts.

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

Tests und Testmatrix (zufällige Texte; Tempi, SNR, Drift, QSB, QRM, Timing,
reines Rauschen; `--legacy` für die alte Matrix):

```
pytest
python tests/run_matrix.py
```

## Wie es funktioniert

1. **Tonverfolgung** (`dsp.ToneTracker`): FFT über 128 ms, alle 16 ms, im
   Bereich 300–1200 Hz. Max-Hold mit Abklingen hält den Ton auch über
   Tastpausen fest. Der Peak (mit Sub-Bin-Interpolation) wird in einem
   Fenster von ±60 Hz weich nachgeführt und folgt so einer Drift; auf eine
   andere Linie wird nur umgeschaltet, wenn sie mindestens 3 dB stärker ist.
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
  das Entry Window. Das Entry Window wird am Titel erkannt
  ("14053.63 CW Elecraft K3 VFO A": Frequenz, Mode, Radio, VFO A/B); alle
  Fenstertitel von N1MM stehen im Log. Lässt sich N1MM nicht in den
  Vordergrund holen, wird nichts getippt, sondern das Rufzeichen in die
  Zwischenablage gelegt (Strg+V in N1MM).
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
  __version__.py Version und Kanal (stable/beta)
  paths.py       Ablageorte (App-Ordner, Log, Aufnahmen)
  config.py      Einstellungen (config.json)
  logging_setup.py  Diagnose-Log
  gui_tooltip.py, gui_errors.py, gui_error_report.py  GUI-Bausteine
  error_report.py   Fehlerbericht
  instance_lock.py  Schutz gegen Doppelstart
  app_mutex.py      benannter Mutex für den Installer
  updater.py, gui_update.py  Self-Update (Prüfung, Download, Dialog)
  app_main.py       Einstieg der EXE (GUI, --decode, --list-devices, --version)
run_cwdecoder.py   Einstieg für PyInstaller
cwdecoder.spec     PyInstaller-Build
installer/         Inno-Setup-Skripte (Stable, Beta)
tools/             make_icon.py, release_tools.py (Release-Workflow)
tests/
  test_*.py      pytest
  run_matrix.py  Testmatrix
  gui_smoke.py   GUI-Rauchtest mit Fake-Soundkarte
docs/adr/        Architekturentscheidungen
docs/BUILD.md    EXE und Installer bauen
```

## Stand / offene Punkte

- Die DSP-Kette ist gegen synthetische Signale getestet (Testmatrix mit
  zufälligen Texten ~97 % Zeichen-Übereinstimmung, bis ca. 0 dB SNR in
  2,4 kHz; bei reinem Rauschen keine Ausgabe). Echte Aufnahmen
  vom Funkgerät (`--record`) sind der nächste Schritt zum Feintuning.
- Die GUI und die Tastatur-Übergabe an N1MM wurden unter Linux ohne
  Display geschrieben und müssen unter Windows einmal durchgeklickt werden.
- Mögliche Erweiterungen: mehrere Signale gleichzeitig (Multi-Decoder über
  das Band), Wahrscheinlichkeits-Decoder statt harter Schwellen bei sehr
  schwachen Signalen, Rufzeichen-Plausibilität über Master-Callsign-Datei.

## Lizenz

Copyright (C) 2026 DF1DS (kainomatic). GNU General Public License v3.0 oder
später (GPL-3.0-or-later), siehe `LICENSE`.

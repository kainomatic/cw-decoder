# CW Decoder – Stand und nächste Schritte (ROADMAP.md)

> Steuert die **Reihenfolge** der Arbeit. Lebendes Dokument: Status bei jedem
> Auftrag aktualisieren (`✅` erledigt, `🔧 IN ARBEIT`, `➡️` als Nächstes,
> `⏳` später). Entscheidungen stehen in `docs/adr/`, Aufgaben in GitHub-Issues.

---

## Aktueller Stand

**Ziel-Version 0.1.0, Beta-Phase.** Decoder-Kern, GUI und
Programm-Infrastruktur stehen; das Programm ist als Setup mit Self-Update
installierbar (Stable/Beta getrennt). Stable `v0.1.0` erst nach Freigabe
durch DF1DS.

Testmatrix (`python tests/run_matrix.py`): Mittelwert **95,4 %**
(Stand Arbeitspaket 4, unverändert gegenüber vorher).

---

## ✅ Arbeitspaket 1 — Decoder-Kern (Desktop-Session)

Signalgenerator, DSP-Kette (Decimator, ToneTracker, Envelope, Thresholder),
TimingDecoder, Offline-Decoder, Testmatrix. Gegen synthetische Signale
getestet.

## ✅ Arbeitspaket 2 — Live-Modus, GUI, N1MM (erste Runde unter Windows)

GUI unter Windows gestartet und per Rauchtest (`tests/gui_smoke.py`,
Fake-Soundkarte) durchgeklickt; Bugfixes bei Start/Stop, Aufnahme, Threading.
N1MM: Entry Window am Titel erkennen, Fokussperre umgehen, Zwischenablage als
Rückfallweg, belegte Ports melden.

## ✅ Arbeitspaket 3 — Programm-Infrastruktur und Projektregeln

Version/Kanal, Ablageorte, Diagnose-Log, Config, Tooltips, Fehlerdialoge,
Fehlerbericht, Single-Instance, Menüleiste, ADRs 0001–0010, pytest + CI
(Windows/Linux, Python 3.12), Lizenz GPL-3.0-or-later.

## 🔧 IN ARBEIT Arbeitspaket 4 — Installer mit Self-Update

- ✅ PyInstaller-Bundle `CWDecoder.exe` mit `--decode`, `--list-devices`,
  `--version` (ADR-0011).
- ✅ Inno-Setup-Installer Stable und Beta, parallel installierbar (ADR-0012).
- ✅ Self-Update: Prüfung beim Start, „Hilfe → Nach Updates suchen",
  Dialog, Download, stille Installation, Neustart; AppMutex (ADR-0013).
- ✅ Release-Workflow über Tags, Release-Notes aus dem Changelog
  (ADR-0014); kein Code-Signing (ADR-0015).
- 🔧 Erstes Beta-Release und Update-Nachweis Beta → Beta auf dem
  Build-Rechner.

## ➡️ Stable 0.1.0 (Freigabe DF1DS)

- Beta auf dem Shack-PC installieren, mit Funkgerät und N1MM testen.
- Danach CHANGELOG einfrieren und `v0.1.0` taggen (ADR-0014).

## ⏳ Live-Test am Funkgerät

- `sounddevice` unter Windows: welche Host-API (MME/WASAPI/DirectSound)
  liefert 8 kHz direkt? `open_stream` probiert 8000, 48000, 44100, 16000.
  Am USB-Audio des Funkgeräts und an VB-Cable prüfen, ob es sauber läuft und
  ob der Pegel passt (zu niedrig = Squelch bleibt zu, zu hoch = Clipping;
  beides am SNR in der Statuszeile erkennbar).
- Echte Aufnahmen (Aufnahmeordner, siehe Datei-Menü) sammeln, auswerten
  (`python -m cwdecoder.decode_wav datei.wav --trace`) und geeignete als
  Testdaten nach `testdata/` committen (< 5 MB je Datei).
- Schwache Signale: ab ~0 dB SNR (2,4 kHz) steigen die Fehler. Ideen, erst
  nach Absprache mit der Desktop-Session: Mehrheitsentscheid über mehrere
  Bandbreiten, weicher Decoder (Wahrscheinlichkeiten statt harter Schwellen).
- Farnsworth/gedehnte Abstände: Wortschwelle passt sich erst nach ~3
  Zeichenpausen an; die ersten Wörter werden ggf. zerhackt.

## ⏳ N1MM am echten Logger

- `EntryWindowTyper`: Kommt das Rufzeichen im Entry Window an? Ist Alt+W
  tatsächlich „Wipe"? Fenstertitel aus dem Log prüfen.
- Spot-Server (Telnet 127.0.0.1:7373) in N1MM verbinden und Bandmap-Spots
  prüfen.
- RadioInfo-Broadcasts (UDP 12060): Frequenz und Mode in der GUI.

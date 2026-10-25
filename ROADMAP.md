# CW Decoder – Stand und nächste Schritte (ROADMAP.md)

> Steuert die **Reihenfolge** der Arbeit. Lebendes Dokument: Status bei jedem
> Auftrag aktualisieren (`✅` erledigt, `🔧 IN ARBEIT`, `➡️` als Nächstes,
> `⏳` später). Entscheidungen stehen in `docs/adr/`, Aufgaben in GitHub-Issues.

---

## Aktueller Stand

**Version 0.1.0 (stable), noch kein Release-Tag.** Decoder-Kern und GUI
laufen; Programm-Infrastruktur (Log, Config, Fehlerdialoge, Fehlerbericht,
Single-Instance, Menü) steht. Nächster Schritt ist der Installer mit
Self-Update.

Testmatrix (`python tests/run_matrix.py`): Mittelwert **95,4 %**
(Stand Arbeitspaket 3, unverändert gegenüber vorher).

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

## ➡️ Arbeitspaket 4 — Installer mit Self-Update

- Build (Bundle für Windows) und Installer; Startmenü-Eintrag.
- Release-Workflow über Tags `vX.Y.Z` / `vX.Y.Z-betaN` (ADR-0002),
  Release-Notes aus diesem Changelog.
- Update-Prüfung beim Start (Config `update_check`), „Hilfe → Nach Updates
  suchen" ersetzt den Platzhalter; Stable/Beta getrennt.
- Erkennen einer laufenden Instanz beim Update (ggf. benannter Mutex
  zusätzlich zum Lockfile, ADR-0010).

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

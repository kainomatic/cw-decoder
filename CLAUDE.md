# CLAUDE.md – Projektkontext für Claude Code

## Was das ist
Live-Morsedecoder in Python für Audio vom Funkgerät (USB-Audio oder VB-Cable
unter Windows). Ziel: Text live anzeigen, erkannte Rufzeichen per Klick an
N1MM Logger+ übergeben. Vorbild ist "CW Reader", nur mit zuverlässigerer
Geschwindigkeits-Erkennung und besserer Rauschunterdrückung.

Lizenz GPL-3.0-or-later (`LICENSE`). Python-Referenzversion 3.12.

## Onboarding für neue Sessions
Der Chatverlauf ist flüchtig, das Repo ist die maßgebliche Wahrheit. Zu
Beginn jeder neuen Session in dieser Reihenfolge lesen:
1. `CLAUDE.md` (dieses Dokument) — Arbeitsweise und Regeln
2. `ROADMAP.md` — aktueller Stand und nächster Schritt
3. `docs/adr/` (Index in `docs/adr/README.md`) — getroffene Entscheidungen
4. `CHANGELOG.md` `[Unreleased]` — was seit dem letzten Release passiert ist

## Rollenmodell (ADR-0001)
| Rolle | Wer | Aufgabe |
|-------|-----|---------|
| Architekt & Reviewer | Claude Desktop | entwirft Architektur und Decoder-Kern, schreibt Aufträge, reviewt; schreibt nicht ins Repo |
| Vermittler & Tester | DF1DS | überbringt Aufträge und Berichte, testet am Funkgerät mit N1MM, liefert Aufnahmen, entscheidet über Stable-Releases |
| Ausführender Maintainer | Claude Code | Code, Tests, Commits, Push, CI, Doku, ADRs, Issues, Releases |

- Jeder Auftrag beginnt mit **`NEUE SESSION: ja`** oder **`NEUE SESSION: nein`**.
  Bei „ja" hat DF1DS vorher `/clear` ausgeführt → Onboarding wie oben.
  Bei „nein" geht es in der laufenden Session weiter.
- Immer nur ein Auftrag gleichzeitig am Repo.
- Fragen zur Architektur und größere Umbauten (vor allem am Decoder-Kern)
  gehen an die Desktop-Session. Abweichungen vom Auftrag im Bericht nennen.

## Branch und Releases (ADR-0002)
- Nur `main`. Kleine Commits direkt auf `main`, danach pushen.
- Releases nur per Tag: `vX.Y.Z` (Stable), `vX.Y.Z-betaN` (Beta).
  Einzige Versionsquelle: `cwdecoder/__version__.py` (`__version__`, `CHANNEL`).
  SemVer. Details zum Release-Ablauf folgen mit dem Installer.

## Entscheidungen und Aufgaben festhalten
- **ADR-Pflicht:** Jede Design- oder Grundentscheidung (Architektur,
  Datenformat, Ablageort, Fehlerverhalten, Sicherheit, Arbeitsweise, Release)
  bekommt einen ADR in `docs/adr/` — im selben Auftrag. Format, Nummerierung
  und Index: `docs/adr/README.md`. Status `Accepted`; bei Änderung neuer ADR,
  alter wird `Superseded by ADR-XXXX`, nie löschen.
- Offene Aufgaben, Bugs, Ideen → GitHub-Issue (nicht im Chat sammeln).
- Projektstand → `ROADMAP.md`.

## Definition of Done (je Auftrag)
Ein Auftrag ist erst fertig, wenn alles erfüllt ist:
1. **pytest grün** lokal **und CI grün** (GitHub Actions, Windows + Linux).
2. **ROADMAP.md**-Status aktualisiert.
3. **CHANGELOG.md** `[Unreleased]` ergänzt (Added/Changed/Fixed/…).
4. Erledigte **Issues** per `Fixes #N` in der Commit-Message geschlossen.
5. **ADR** angelegt, falls eine Entscheidung gefallen ist.
6. **Gepusht**, und der Bericht nennt den Hash von `origin/main`
   (`git log --oneline -1 origin/main`). „working tree clean" allein genügt nicht.

## Arbeitsregeln
- Sprache in Code-Kommentaren, Commit-Messages, Doku und Antworten: Deutsch.
- Kopfzeile in jeder Python-Datei:
  `# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later`
- Jede Änderung als eigener, kleiner Commit mit aussagekräftiger Message.
- Tuning-Parameter liegen in den `*Config`-Dataclasses (`TrackerConfig`,
  `ThresholdConfig`, `TimingConfig`, `DecoderConfig`). Keine Magic Numbers
  tief im Code verstecken.
- Keine neuen Laufzeit-Abhängigkeiten außer numpy, scipy, sounddevice ohne
  Rückfrage (Entwicklung: pytest in `requirements-dev.txt`).
  Die GUI bleibt bei tkinter.
- Aufnahmen aus der GUI landen in `Dokumente\CW Decoder\Aufnahmen`
  (ADR-0003). Gute Aufnahmen als Testdaten nach `testdata/` kopieren
  (WAV, 8–48 kHz, < 5 MB, ggf. `.gitignore` anpassen) und committen; mit
  `python -m cwdecoder.decode_wav datei.wav --trace` auswerten.

## GUI-Regeln
- **Kein tk-Aufruf aus Threads.** Hintergrundarbeit meldet über die Queue
  `App.msgs`, `_poll()` holt per `after()` ab (ADR-0009).
- Alle sichtbaren Texte als Modulkonstanten `_LBL_*` (Beschriftungen),
  `_MSG_*` (Meldungen), `_TT_*` (Tooltips) — Vorbereitung für i18n.
- Jedes Bedienelement bekommt einen Tooltip:
  `attach_tooltip(widget, _TT_...)` aus `cwdecoder/gui_tooltip.py` (ADR-0006).
- Fehler in der GUI: `report_error(exc)` bzw. `gui_errors.report_exception`;
  neue erwartbare Fehler bekommen eine eigene Ausnahmeklasse und einen
  Eintrag in `classify_error` (ADR-0007). Im Terminal-Modus bleibt stderr.
- Logging über `logging.getLogger(__name__)`; nie Audiodaten loggen (ADR-0004).

## Testen
- Framework **pytest** (`pip install -r requirements-dev.txt`, dann `pytest`).
- Logik tk-frei halten und direkt testen. Tests, die ein echtes Fenster
  brauchen, haben einen **Skip-Guard**, wenn kein Display vorhanden ist
  (`tests/conftest.py`: `requires_display`).
- Tests dürfen nicht in echte Nutzerordner schreiben: Fixture `app_env`
  (biegt `APPDATA`/`HOME` auf ein Temp-Verzeichnis um).
- **Testmatrix bleibt Pflicht** vor und nach jeder Änderung an
  `cwdecoder/dsp.py`, `timing.py` oder `decoder.py`:
  `python tests/run_matrix.py`, Mittelwert vorher/nachher notieren. Er darf
  nicht sinken (zuletzt 95,4 %), sonst begründen oder zurücknehmen.
- Unter Windows Tests über das Bash-Tool laufen lassen (längere Läufe).

## Befehle
```
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements-dev.txt
pytest                                # alle Tests (GUI-Rauchtest nur mit Display)
python tests/run_matrix.py            # Testmatrix (Störungen, Tempi, SNR)
python tests/gui_smoke.py             # GUI-Rauchtest direkt
python -m cwdecoder.live --list       # Audiogeräte
python -m cwdecoder.live --device "USB" --record x.wav
python -m cwdecoder.gui               # Oberfläche
python -m cwdecoder.gen "CQ TEST" -o t.wav --wpm 25 --snr 6
python -m cwdecoder.decode_wav t.wav --expect "CQ TEST"
set CWDECODER_DEBUG=1                 # Log auf DEBUG
```

Ablageorte (ADR-0003): `%APPDATA%\CWDecoder\` (`config.json`,
`cwdecoder.lock`, `logs\cwdecoder.log`), Beta: `%APPDATA%\CWDecoder-Beta\`.

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

## Offene Punkte
Stehen in `ROADMAP.md` (Live-Test am Funkgerät, N1MM am echten Logger,
schwache Signale, Farnsworth) und als GitHub-Issues.

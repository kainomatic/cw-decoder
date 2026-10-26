# CLAUDE.md – Projektkontext für Claude Code

> Allgemeine Arbeitsweise für alle Projekte: https://github.com/kainomatic/claude-playbook (README). Dieses CLAUDE.md enthält nur, was für cw-decoder spezifisch ist.

Lesen per `gh api repos/kainomatic/claude-playbook/readme --jq .content | base64 -d`
(privates Repo). Dort stehen Rollen, Auftragsformat, Definition of Done und
die allgemeinen Code-Regeln; hier nur Kurzfassung und Projektbesonderheiten.

## Was das ist
Live-Morsedecoder in Python für Audio vom Funkgerät (USB-Audio oder VB-Cable
unter Windows). Ziel: Text live anzeigen, erkannte Rufzeichen per Klick an
N1MM Logger+ übergeben. Vorbild ist "CW Reader", nur mit zuverlässigerer
Geschwindigkeits-Erkennung und besserer Rauschunterdrückung.

Lizenz GPL-3.0-or-later (`LICENSE`). Python-Referenzversion 3.12.

## Onboarding für neue Sessions
Bei `NEUE SESSION: ja` (DF1DS hat `/clear` ausgeführt) in dieser Reihenfolge:
1. das Auftrags-Issue: `gh issue view N --comments`
2. `CLAUDE.md` (dieses Dokument), bei Bedarf das Playbook
3. `ROADMAP.md` — Stand, Leitlinie, nächster Schritt, offene Issues
4. `docs/adr/README.md` — Index der Entscheidungen
5. `CHANGELOG.md` `[Unreleased]`

## Rollen und Aufträge (ADR-0016, Playbook §1 und §3)
- **Claude Desktop:** Architekt & Reviewer; schreibt im Repo **nur Issues**
  (anlegen, kommentieren, Labels); Push nur nach Einzelfreigabe durch
  DF1DS, nur Daten oder Doku, nie Programmcode (Playbook §1). **DF1DS:** Tester, startet Aufträge,
  entscheidet über Stable. **Claude Code:** einziger Schreiber am Code
  (Code, Tests, Commits, Push, CI, Doku, ADRs, Tags, Releases).
- **Aufträge über Issues:** Ein Auftrag ist ein Issue mit Label `auftrag`
  (Kopf `NEUE SESSION: ja/nein`, Kontext, Aufgabe, Akzeptanzkriterien);
  er kann auch als Kommentar in einem Issue stehen. Start mit
  „Bearbeite Issue #N" → `gh issue view N --comments` lesen und beginnen.
- Rückfragen während der Arbeit: `gh issue comment N --body-file …`.
- **Abschlussbericht** als Kommentar im Issue: Commits, Hash von
  `origin/main` (`git log --oneline -1 origin/main`), CI-Link
  (`gh run list --workflow ci.yml --limit 1`), Abweichungen mit Begründung,
  offene Punkte.
- **Fragen, die eine Entscheidung brauchen, stehen nur im Issue-Kommentar.**
  Die Terminal-Ausgabe an DF1DS ist ein Einzeiler:
  „Bericht und Fragen in Issue #N: <Link>". Nichts, was DF1DS kopieren
  müsste. Beim bloßen Schließen eines Issues nach bestandenem Review
  lautet die Ausgabe „Issue #N geschlossen, nichts Neues." – kein Link auf
  den alten Bericht.
- Das Issue erst schließen, wenn das Review der Desktop-Session
  „bestanden" sagt: dann `Fixes #N` im nächsten Commit. Bei
  Korrekturpunkten bleibt es offen (`NEUE SESSION: nein`).
- Verlangt der Auftrag einen Tag: Workflow abwarten (`gh run watch`),
  Release-Link als Kommentar ins Issue, erst danach mit `Fixes #N`
  schließen.
- Entscheidungen, die DF1DS gehören, stellt die Desktop-Session im Chat mit
  Bewertung und Empfehlung; im Issue steht nur das Ergebnis (Playbook §6,
  ADR-0016).
- Immer nur ein `auftrag`-Issue in Arbeit. Issues ohne `auftrag` (Liste in
  `ROADMAP.md`, „Beschlossen, noch nicht umgesetzt") sind kein Auftrag.
- Architekturfragen und größere Umbauten am Decoder-Kern gehen an die
  Desktop-Session (als Issue-Kommentar).

## Branch und Releases (ADR-0002)
- Nur `main`. Kleine Commits direkt auf `main`, danach pushen.
- Releases nur per Tag: `vX.Y.Z` (Stable), `vX.Y.Z-betaN` (Beta).
  Einzige Versionsquelle: `cwdecoder/__version__.py` (`__version__`, `CHANNEL`).
  SemVer.

## Release (ADR-0011 bis ADR-0015, Anleitung `docs/BUILD.md`)
- Im Repo steht immer die **Ziel-Stable-Nummer** `__version__ = "X.Y.Z"`
  und `CHANNEL = "stable"`, auch während einer Beta-Phase. Für Betas patcht
  der Workflow beides nur im Build (`tools/release_tools.py`).
- **Beta-Tag** `vX.Y.Z-betaN` darf Claude Code setzen
  (`git tag vX.Y.Z-betaN && git push origin vX.Y.Z-betaN`). Nummern nie
  wiederverwenden; scheitert der Lauf: fixen, nächste Nummer.
- **Stable-Tag** `vX.Y.Z` nur nach Freigabe durch DF1DS. Vorher CHANGELOG
  einfrieren (`[Unreleased]` → `[X.Y.Z] - JJJJ-MM-TT`, neuer leerer
  `[Unreleased]`); nur beim Stable, nie bei Betas. Danach `__version__` auf
  die nächste Ziel-Nummer heben.
- Tag-Push startet `.github/workflows/release.yml`: Versions-Sync
  (Tag-Basis == `__version__`, sonst Abbruch), PyInstaller-Bundle,
  Smoke-Test, Inno-Setup, Release-Notes aus `CHANGELOG.md`, GitHub-Release
  mit `CWDecoder-Setup-vX.Y.Z.exe` bzw. `CWDecoder-Beta-Setup-vX.Y.Z.exe`.
  Lauf beobachten: `gh run watch`.
- Vor einer Beta für den Shack-PC: Self-Update Beta N → N+1 auf dem
  Entwicklungsrechner nachweisen (ROADMAP, „Testablauf Installer/Beta").
- Installer: `installer/cwdecoder.iss` und `installer/cwdecoder-beta.iss`
  immer gemeinsam ändern; die AppId-GUIDs nie ändern.
- Self-Update (`updater.py`, `gui_update.py`): Kanalfilter, Asset-Muster und
  der Schalter `/RESTARTCWDECODER` hängen an den Namen oben — Umbenennen nur
  mit neuem ADR.

## Entscheidungen, Aufgaben, Definition of Done
ADR-Pflicht, Issues statt Chat-Notizen und die Definition of Done gelten wie
im Playbook (§2, §4). Projektspezifisch:
- ADR-Format, Nummerierung und Index: `docs/adr/README.md`. Bei Änderung
  neuer ADR, der alte wird `Superseded by ADR-XXXX`, nie löschen.
- „CI grün" heißt: GitHub Actions unter Windows **und** Linux.
- Bei Änderungen an `dsp.py`, `timing.py`, `decoder.py`: Testmatrix vorher
  und nachher im Bericht (siehe „Testen").

## Arbeitsregeln (projektspezifisch)
- Kopfzeile in jeder Python-Datei:
  `# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later`
- Der Projektname des Referenzprojekts (als zusammenhängendes Wort,
  Buchstaben plus Zahl) erscheint nirgends im Repo, auch nicht in
  Commit-Messages. Vor dem Push: `git grep -inE "qsl ?73"` und
  `git log --format=%B origin/main..HEAD | grep -iE "qsl ?73"` müssen leer
  sein. Die Q-Gruppe QSL und die Zahl 73 sind normale Funkbegriffe und
  überall erlaubt (#7).
- Tuning-Parameter liegen in den `*Config`-Dataclasses (`TrackerConfig`,
  `ThresholdConfig`, `TimingConfig`, `DecoderConfig`).
- Laufzeit-Abhängigkeiten nur numpy, scipy, sounddevice (weitere nur nach
  Rückfrage). Entwicklung: pytest und Pillow in `requirements-dev.txt`;
  PyInstaller nur für den Build. Die GUI bleibt bei tkinter.
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
- Start über `cwdecoder/gui_start.py` (ADR-0020): Lock und Startfenster vor
  den schweren Imports. `gui_start` und alles, was es vor dem Lock lädt,
  bleiben frei von numpy/scipy/sounddevice (Test `test_gui_start.py`).
- Layout: rechte Spalte und Scrollbalken vor dem Textfeld packen; das
  Textfeld hat eine kleine Wunschbreite (`width=40`), sonst verdrängt es
  bei hoher DPI-Skalierung die Spalte (Test mit `tk scaling 2.0`).

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
  nicht sinken (zuletzt 97,7 % bei 11 Kategorien inkl. „CW-Filter"; alte
  Matrix `--legacy` 98,3 %), sonst begründen oder zurücknehmen. Die
  Kategorie **Rauschen** (zur Hälfte durch ein schmales CW-Filter) muss
  100 % bleiben: Bei reinem Rauschen gibt der Decoder nichts aus
  (ADR-0017, ADR-0018).
  Stichprobe gegen Übertuning: `run_matrix.run(base_seed=5000)` bzw. `7777`.
- Unter Windows Tests über das Bash-Tool laufen lassen (längere Läufe).

## Befehle
```
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements-dev.txt
pytest                                # alle Tests (GUI-Rauchtest nur mit Display)
python tests/run_matrix.py            # Testmatrix (11 Kategorien, zufällige Texte)
python tests/run_matrix.py --legacy   # alte Matrix (zwei feste Sätze)
python tests/gui_smoke.py             # GUI-Rauchtest direkt
python -m cwdecoder.live --list       # Audiogeräte
python -m cwdecoder.live --device "USB" --record x.wav
python -m cwdecoder.gui               # Oberfläche
python -m cwdecoder.gen "CQ TEST" -o t.wav --wpm 25 --snr 6
python -m cwdecoder.decode_wav t.wav --expect "CQ TEST"
set CWDECODER_DEBUG=1                 # Log auf DEBUG
python tools/make_icon.py && pyinstaller --noconfirm cwdecoder.spec   # Bundle
dist\CWDecoder\CWDecoder.exe --decode t.wav > out.txt                  # Bundle prüfen
ISCC /DAPP_VERSION=0.1.0 installer\cwdecoder.iss                       # Installer
```

Ablageorte (ADR-0003): `%APPDATA%\CWDecoder\` (`config.json`,
`cwdecoder.lock`, `logs\cwdecoder.log`), Beta: `%APPDATA%\CWDecoder-Beta\`.
Aufnahmen: `cw_…_NNN.wav` plus Decodier-Log `cw_…_NNN.txt` (`sekunde;zeichen`).

## Signalkette (Reihenfolge ist wichtig)
Audio -> `Decimator` (auf ~8 kHz) -> `ToneTracker` (FFT, Tonfrequenz,
Linien-Gate `tone_present`) -> `Envelope` (Quadraturmischer + Tiefpass,
Bandbreite abhängig vom Tempo) -> `Thresholder` (Rauschteppich/Signalpegel,
Hysterese, Squelch aus Pegel + Dynamik + Gate, Entprellung ->
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
  Tastpausen gehalten wird. Im Lock sucht er den Peak nur im Fenster
  ±60 Hz um die aktuelle Frequenz (`track_window_hz`, folgt Drift) und
  wechselt auf eine andere Linie nur, wenn sie mindestens 3 dB stärker ist
  (`switch_margin_db`); beim Wechsel wird der Max-Hold gelöscht.
- Squelch öffnet nur, wenn **beide** unabhängigen Kriterien passen
  (ADR-0018): Linien-Gate im Tracker (Peak ≥ 9 dB über dem Umfeld
  ±20…40 Hz, schließt erst nach 0,6 s unter 6 dB) und Dynamik der Hüllkurve
  (99,5.–10. Perzentil über 2 s ≥ 20 dB, im 10-ms-Takt). Grund: Rauschen
  durch ein schmales Empfängerfilter (~100 Hz) sieht sonst wie ein
  getasteter Ton aus.
- Der `Thresholder` arbeitet mit **60 ms Vorausschau** (`lookahead_ms`):
  Dynamik und Gate (pro Sample vom Tracker) sehen 60 ms voraus, die
  Schwelle läuft dahinter. Damit ist das Ergebnis unabhängig von der
  Blockgröße (GUI: 20 ms, Matrix: 64 ms), und das erste Zeichen nach
  einer Pause bleibt vollständig (`tests/test_erstes_zeichen.py`). Nie
  wieder Logik einbauen, die vom Blockende abhängt.
- Fällt `tone_present` weg, schließt `CWDecoder` das Zeichen ab und setzt
  das Tempo zurück (`TimingDecoder.reset_tempo`), damit die nächste
  Station frisch eingemessen wird. Tempo-Suchbereich 5–60 WPM
  (`timing.DIT_MIN_MS`/`DIT_MAX_MS`).
- Elemente eines Zeichens werden erst am Zeichenende in Punkt/Strich
  eingeteilt (`TimingDecoder._flush`); die Strich-Schwelle liegt adaptiv
  zwischen den beiden Clustern (1,4–2,6 Punktlängen).

## Offene Punkte
Stehen als GitHub-Issues; die Übersicht steht in `ROADMAP.md` unter
„Beschlossen, noch nicht umgesetzt" (dazu Live-Test am Funkgerät und N1MM am
echten Logger).

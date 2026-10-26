# Changelog

Alle nennenswerten Änderungen am CW Decoder stehen in dieser Datei.

Das Format folgt [Keep a Changelog](https://keepachangelog.com/de/1.1.0/),
die Versionsnummern folgen [Semantic Versioning](https://semver.org/lang/de/).
Releases entstehen durch Tags `vX.Y.Z` bzw. `vX.Y.Z-betaN` (ADR-0002).

## [Unreleased]

### Added
- Installierbares Windows-Programm: Setup-Dateien
  `CWDecoder-Setup-vX.Y.Z.exe` (Stable) und
  `CWDecoder-Beta-Setup-vX.Y.Z.exe` (Beta), parallel installierbar, mit
  Startmenü-Eintrag und Deinstallation (fragt, ob Einstellungen gelöscht
  werden sollen; Standard Nein) (ADR-0011, ADR-0012).
- Self-Update: Prüfung kurz nach dem Start (abschaltbar), „Hilfe → Nach
  Updates suchen", Update-Dialog mit Release-Notes-Link, Download mit
  Fortschritt, stille Installation und automatischem Neustart; „Später"
  lässt einen Hinweis im Hilfe-Menü stehen. Stable sieht nur Stables, Beta
  nur Betas (ADR-0013).
- `CWDecoder.exe --decode datei.wav`, `--list-devices`, `--version` in der
  installierten Version (ADR-0011).
- Release-Workflow: Tag `vX.Y.Z` bzw. `vX.Y.Z-betaN` baut Bundle und
  Installer und veröffentlicht das GitHub-Release mit Notes aus diesem
  Changelog (ADR-0014). Anleitung für lokale Builds in `docs/BUILD.md`.
- Programm-Icon (`tools/make_icon.py`).
- Version und Release-Kanal in `cwdecoder/__version__.py` (0.1.0, stable);
  Fenstertitel „CW Decoder v0.1.0", im Beta-Kanal mit „BETA" (ADR-0003).
- Ablageorte in `cwdecoder/paths.py`: App-Ordner `%APPDATA%\CWDecoder`
  (Beta: `CWDecoder-Beta`), Aufnahmen in `Dokumente\CW Decoder\Aufnahmen`
  (ADR-0003).
- Diagnose-Log `<App-Ordner>\logs\cwdecoder.log` (1 MB × 5), Level per
  `CWDECODER_DEBUG=1` auf DEBUG; Start, Version, Gerät, Abtastrate und Fehler
  werden protokolliert, Audiodaten nie (ADR-0004).
- Einstellungen in `<App-Ordner>\config.json` (Gerät, feste Tonfrequenz,
  N1MM, Wipe, Aufnahme, Update-Prüfung); kaputte Datei wird beiseitegelegt
  und gemeldet, Speichern atomar (ADR-0005).
- Hover-Tooltips an allen Bedienelementen (ADR-0006).
- Fehlerdialoge mit Klartext für Soundkarte, belegten Port, fehlendes
  N1MM-Fenster und kaputte Einstellungen; unerwartete Fehler mit
  aufklappbarem Traceback (ADR-0007).
- „Hilfe → Fehler melden…": Bericht mit Version, System, Audiogerät und den
  letzten 200 Logzeilen; Vorschau, lokal speichern oder als GitHub-Issue im
  Browser öffnen — das Programm sendet nichts selbst (ADR-0008).
- Menüleiste: Datei (Aufnahmeordner öffnen, Beenden), Hilfe (Nach Updates
  suchen — Platzhalter, Log-Ordner öffnen, Fehler melden…, Über).
- Schutz gegen Doppelstart der GUI per Lockfile (ADR-0010).
- Lizenz GPL-3.0-or-later (`LICENSE`, Kopfzeile in jeder Python-Datei).
- pytest-Setup, neue Tests für Config, Logging, Pfade, Tooltips,
  Fehlerzuordnung, Fehlerbericht und Lock; CI unter Windows und Linux
  (Python 3.12).
- Projektdokumente: ADRs (`docs/adr/`), `ROADMAP.md`, dieses Changelog,
  erweiterte `CLAUDE.md` (Onboarding, Rollen, Definition of Done).

### Changed
- GUI-Aufnahmen landen nicht mehr in `testdata/` des Repos, sondern im
  Aufnahmeordner unter Dokumente; `testdata/` bleibt für Testdateien.
- Diagnose-Ausgaben der N1MM-Anbindung (Fenstertitel, Vordergrund, belegte
  Ports) gehen ins Log statt auf stderr.
- `live.open_stream()` und `live.pick_device()` werfen `AudioDeviceError`
  statt `SystemExit`; der Terminal-Decoder meldet weiterhin auf stderr.
- GUI-Texte als `_LBL_*`/`_MSG_*`/`_TT_*`-Konstanten (Vorbereitung i18n).
- Einstellungen der GUI bleiben über Neustarts erhalten; `--n1mm` gilt nur
  für den laufenden Start.
- „Hilfe → Nach Updates suchen" prüft jetzt wirklich (vorher Platzhalter).
- Die GUI legt zusätzlich zum Lockfile einen benannten Mutex an, an dem der
  Installer eine laufende Instanz erkennt (ADR-0013).
- CI: `actions/checkout` und `actions/setup-python` auf v7 (Node 24).
- Arbeitsweise: Aufträge, Rückfragen, Berichte und Reviews laufen über
  GitHub-Issues (Label `auftrag`); die Desktop-Session schreibt im Repo nur
  Issues (ADR-0016, ersetzt ADR-0001). `CLAUDE.md` verweist für die
  allgemeine Arbeitsweise auf das claude-playbook; `ROADMAP.md` hat einen
  Einstieg für neue Desktop-Sessions, Leitlinie, Testablauf und die Liste
  der offenen Issues.

### Fixed
- Absturz des Decoder-Threads beendete den Lauf bisher still; jetzt stoppt
  die GUI und zeigt einen Fehlerdialog.
- GUI-Rauchtest brach sporadisch mit „Tcl_AsyncDelete" ab (tk-Objekte wurden
  in einem Hintergrund-Thread abgeräumt).
- Zwei GUI-Tests scheiterten ohne tkinter mit `ModuleNotFoundError`; sie
  werden jetzt übersprungen.
- Release-Workflow brach beim Schreiben der Release-Notes auf der
  cp1252-Konsole des Windows-Runners ab (v0.1.0-beta1 ohne Release).
- Nach einem Self-Update blieb die heruntergeladene Setup-Datei (ca. 40 MB)
  in `%TEMP%` liegen; der nächste Start räumt alte `CWDecoder-Update-*.exe`
  jetzt auf (#6).

# ADR-0013: Self-Update — Prüfen, Herunterladen, Installieren, Neustart

**Status:** Accepted

## Kontext

DF1DS soll neue Versionen ohne manuellen Download bekommen, Beta-Tester
nur Betas, Stable-Nutzer nur Stables. Die Prüfung darf den Start nicht
bremsen und ohne Netz nicht stören. Der Installer muss die laufende EXE
ersetzen können und das Programm danach wieder starten.

## Entscheidung

### Prüfen (`cwdecoder/updater.py`, ohne tk)

- Quelle ausschließlich
  `https://api.github.com/repos/kainomatic/cw-decoder/releases` (HTTPS,
  Timeout 8 s, User-Agent `CWDecoder-Updater/1`). Keine Telemetrie, nur
  diese eine Abfrage.
- Kanalfilter: **stable** = `prerelease: false` und Tag `vX.Y.Z`;
  **beta** = `prerelease: true` und Tag `vX.Y.Z-betaN`. Entwürfe und
  Releases, bei denen Tag und Flag nicht zusammenpassen, werden ignoriert.
- Versionsvergleich: Basis numerisch, bei gleicher Basis
  `vX.Y.Z-betaN < vX.Y.Z`, Betas numerisch (`beta10 > beta2`). Die laufende
  Beta kennt ihre volle Version, weil der Workflow `__version__` im Build auf
  `X.Y.Z-betaN` setzt (ADR-0014).
- Asset per Regex: Stable `^CWDecoder-Setup-vX.Y.Z\.exe$` (passt nicht auf
  Beta-Dateien), Beta `^CWDecoder-Beta-Setup-vX.Y.Z\.exe$`.
- `check_for_update()` wirft nie: Netz-, API- und Formatfehler ergeben
  `UpdateStatus.ERROR` mit Klartext. Rate-Limit (403/429) bekommt eine
  eigene Meldung.

### Herunterladen

- Nur URLs, die mit `https://github.com/` oder
  `https://objects.githubusercontent.com/` beginnen; Weiterleitungen (GitHub
  leitet auf sein CDN um) nur auf HTTPS-Ziele.
- Ziel `%TEMP%\CWDecoder-Update-*.exe`. Größe muss `assets[].size`
  entsprechen, sonst wird die Datei gelöscht und nicht ausgeführt. SHA256
  wird nur geloggt: Die Releases-Liste liefert keinen Referenz-Hash; Schutz
  bieten TLS zur GitHub-Domain und die Größenprüfung.
- Erwartbare Fehler sind `UpdateError` und haben einen Eintrag in
  `classify_error` (ADR-0007).

### GUI (`cwdecoder/gui_update.py`, `gui.py`)

- 1,5 s nach dem Start Prüfung im Hintergrund-Thread, nur bei
  `update_check: true` in der Config. Ergebnis über die Queue `App.msgs`
  (ADR-0009). Fehler beim automatischen Check nur ins Log.
- „Hilfe → Nach Updates suchen" prüft immer (auch bei `update_check:
  false`) und meldet „aktuell" bzw. den Fehler im Dialog.
- Update-Dialog: installierte und neue Version, Link zu den Release-Notes,
  „Herunterladen und installieren" mit Fortschrittsbalken (Download im
  Thread, Meldungen über eine eigene Queue), „Später", Haken „Nicht mehr an
  Updates erinnern".
- „Später" setzt oben ins Hilfe-Menü „⬆ Update auf vX.Y.Z verfügbar"
  (öffnet den Dialog wieder). Der Haken schreibt `update_check: false`.

### Installieren und Neustart

- Vor dem Installer-Start: Audio-Stream stoppen, N1MM-Ports schließen,
  Lockfile freigeben (ADR-0010), AppMutex schließen. Dann
  `"<setup> /SILENT /RESTARTCWDECODER"` starten und die GUI beenden.
- `/SILENT`: Fortschrittsfenster, keine Assistent-Seiten. Die UAC-Abfrage
  bleibt (Installation nach Program Files) und ist akzeptiert.
- Benannter Mutex `CWDecoder-Stable` / `CWDecoder-Beta` per
  `CreateMutexW` (ctypes, `cwdecoder/app_mutex.py`), angelegt beim Start der
  GUI, Handle bis Prozessende gehalten, nicht fatal. Er ergänzt das
  PID-Lockfile (ADR-0010): Der Installer erkennt daran eine laufende
  Instanz bei manueller Installation. Beim Self-Update wird er vorher
  geschlossen, damit der stille Installer nicht auf den eigenen,
  gerade endenden Prozess wartet; das Ersetzen der Dateien sichert
  `CloseApplications=yes` ab.
- Neustart nur über den `[Run]`-Eintrag mit `Check: ShouldRestartApp`
  (`WizardSilent()` und `/RESTARTCWDECODER` in `GetCmdTail`), `nowait
  runascurrentuser` — das Programm läuft danach als normaler Nutzer, nicht
  mit Admin-Rechten. `RestartApplications=no`, damit der Restart Manager
  nicht zusätzlich startet.

| Aufruf | Haken „starten" | Automatischer Neustart |
|---|---|---|
| interaktiv | ja | nein |
| `/SILENT` (Verteilung) | nein | nein |
| `/SILENT /RESTARTCWDECODER` (Self-Update) | nein | ja |

## Konsequenzen

- Stable-Nutzer sehen nie eine Beta und umgekehrt.
- Ohne Netz startet das Programm normal; nur der manuelle Check meldet den
  Fehler.
- Kein kryptografischer Nachweis der Setup-Datei (siehe ADR-0015, kein
  Code-Signing); Vertrauen beruht auf HTTPS zu GitHub.
- Der Mutex wird beim Self-Update kurz vor Prozessende freigegeben; ein
  zweiter Start in diesem Moment ist trotzdem durch das Lockfile bzw. das
  Ende des Prozesses abgedeckt.

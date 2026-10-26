# ADR-0012: Inno-Setup-Installer, Stable und Beta parallel installierbar

**Status:** Accepted

## Kontext

Das Bundle aus ADR-0011 braucht einen Installer mit Startmenü-Eintrag,
Deinstallation und Eintrag unter „Apps". Beta-Versionen sollen sich neben
der Stable testen lassen, ohne deren Einstellungen anzufassen (getrennte
App-Ordner, ADR-0003).

## Entscheidung

- **Inno Setup 6**, zwei eigenständige Skripte statt eines parametrierten:
  `installer/cwdecoder.iss` (Stable) und `installer/cwdecoder-beta.iss`
  (Beta). Getrennte Dateien machen die festen GUIDs offensichtlich; ein
  falscher Schalter kann nicht die falsche GUID einbauen. Beide Dateien
  werden synchron gehalten (sie unterscheiden sich nur in den Werten unten).

| | Stable | Beta |
|---|---|---|
| AppId (niemals ändern) | `{87644335-2C59-4FE7-BD3F-040220A4D56D}` | `{D14A0CE4-9839-4396-9C0C-EEE7AFA3DA84}` |
| Produktname | CW Decoder | CW Decoder Beta |
| Installationsordner | `{autopf}\CW Decoder` | `{autopf}\CW Decoder Beta` |
| Nutzerdaten | `%APPDATA%\CWDecoder` | `%APPDATA%\CWDecoder-Beta` |
| Setup-Datei | `CWDecoder-Setup-vX.Y.Z.exe` | `CWDecoder-Beta-Setup-vX.Y.Z.exe` |
| AppMutex | `CWDecoder-Stable` | `CWDecoder-Beta` |

- Beta-Setup-Dateien tragen die Ziel-Stable-Nummer (`X.Y.Z`), nicht das
  `-betaN`-Suffix; die `.iss` kennt nur `APP_VERSION`.
- `APP_VERSION` kommt per `/DAPP_VERSION=X.Y.Z` vom Release-Workflow;
  ohne Schalter gilt der Fallback oben in der `.iss`.
- Windows 10 oder neuer (`MinVersion=10.0`), nur x64,
  `PrivilegesRequired=admin` (Installation nach Program Files).
- Sprachen Deutsch und Englisch; LICENSE (GPL) wird im Assistenten gezeigt;
  Desktop-Verknüpfung optional (Standard aus).
- `[InstallDelete]` räumt `{app}\_internal` vor dem Kopieren ab, damit keine
  Reste einer älteren Version im Bundle bleiben.
- Deinstallation fragt, ob der App-Ordner unter `%APPDATA%` gelöscht werden
  soll; Standard **Nein** (auch bei stiller Deinstallation mit
  `/SUPPRESSMSGBOXES`). Aufnahmen unter `Dokumente\CW Decoder` werden nie
  gelöscht.
- Laufende Instanz und Neustart: `AppMutex`, `CloseApplications=yes`,
  `RestartApplications=no` und der `[Run]`-Mechanismus aus ADR-0013.
- Inno Setup im Workflow per `choco install innosetup`, lokal per winget
  oder choco (`docs/BUILD.md`).

## Konsequenzen

- Stable und Beta laufen nebeneinander mit eigener Config, eigenem Log und
  eigenem Lock (ADR-0003, ADR-0010); Aufnahmen teilen sie sich.
- Änderungen am Installer immer in beiden `.iss`-Dateien.
- Die AppId-GUIDs dürfen nie geändert werden; eine neue GUID ergäbe eine
  zweite Installation statt eines Updates.
- Ohne Code-Signing warnt SmartScreen beim ersten Start des Setups
  (ADR-0015).

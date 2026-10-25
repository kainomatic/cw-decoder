# ADR-0003: Datenablage — App-Ordner je Kanal, Aufnahmen in den Dokumenten

**Status:** Accepted

## Kontext

Bisher lagen Aufnahmen aus der GUI im `testdata/`-Ordner des Repos, Config
und Log gab es nicht. Mit dem Installer (nächster Schritt) läuft das Programm
nicht mehr aus einem Repo-Checkout; außerdem sollen Stable und Beta
nebeneinander installierbar sein, ohne sich Config, Log oder Lockfile zu
teilen.

Aufnahmen sind für die Weiterentwicklung die wichtigsten Testdaten: Nutzer
schicken sie zur Analyse weiter. Sie müssen ohne Suchen auffindbar sein.

## Entscheidung

- `cwdecoder/__version__.py` ist die einzige Quelle für `__version__` und
  `CHANNEL` (`"stable"` oder `"beta"`).
- `cwdecoder/paths.py` kapselt alle Ablageorte; jede `get_*`-Funktion legt
  ihren Ordner an.

| Zweck | Windows | Linux/CI |
|-------|---------|----------|
| App-Ordner (Config, Lock) | `%APPDATA%\CWDecoder` bzw. `CWDecoder-Beta` | `~/.config/CWDecoder` (bzw. `$XDG_CONFIG_HOME`) |
| Log | `<App-Ordner>\logs` | ebenso |
| Aufnahmen | `Dokumente\CW Decoder\Aufnahmen` | `~/CW Decoder/Aufnahmen` |

- Der Dokumente-Ordner wird unter Windows per `SHGetKnownFolderPath`
  ermittelt, damit eine Umleitung (z. B. OneDrive) berücksichtigt wird;
  Rückfall ist `%USERPROFILE%\Documents`.
- Aufnahmen sind kanalunabhängig: Stable und Beta schreiben in denselben,
  für den Nutzer sichtbaren Ordner.
- `testdata/` im Repo bleibt ausschließlich für versionierte Testdateien.
- Der Aufnahmeordner wird erst beim ersten Aufnehmen angelegt, nicht schon
  beim GUI-Start.

## Konsequenzen

- Positiv: Installer-tauglich, Stable/Beta sauber getrennt, Aufnahmen über
  „Datei → Aufnahmeordner öffnen" mit einem Klick erreichbar.
- Positiv: Tests können `APPDATA`/`HOME` umbiegen und brauchen keinen
  echten Nutzerordner.
- Negativ: Eine Aufnahme, die als Testfall ins Repo soll, muss von Hand nach
  `testdata/` kopiert werden.

# ADR-0011: Build mit PyInstaller als onedir-Bundle

**Status:** Accepted

## Kontext

DF1DS soll den CW Decoder am Shack-PC ohne Python-Installation nutzen
können. Das Programm braucht numpy, scipy und sounddevice (mit der
PortAudio-DLL) und läuft als tkinter-Oberfläche. Für Tests und Fehlersuche
sollen die Offline-Decodierung und die Geräteliste auch mit der
installierten EXE gehen.

## Entscheidung

- **PyInstaller**, Spec-Datei `cwdecoder.spec` im Repo als einzige
  Build-Konfiguration. PyInstaller ist ein reines Build-Werkzeug und keine
  Laufzeit-Abhängigkeit (nicht in `requirements.txt`).
- **onedir** (`dist\CWDecoder\CWDecoder.exe` + `_internal\`), nicht onefile:
  schneller Start ohne Entpacken nach `%TEMP%`, weniger Fehlalarme von
  Virenscannern, der Installer kopiert einfach den Ordner.
- `console=False` (Fensterprogramm), Name `CWDecoder`, Icon
  `assets/cwdecoder.ico`. Das Icon erzeugt `tools/make_icon.py` mit Pillow
  (nur `requirements-dev.txt`); es wird gebaut, nicht eingecheckt.
- `collect_all('sounddevice')` und `collect_all('_sounddevice_data')`:
  sounddevice lädt die PortAudio-DLL zur Laufzeit per ctypes, das erkennt die
  Analyse nicht. numpy/scipy über die mitgelieferten Hooks; `scipy.signal`
  und `scipy.io.wavfile` zusätzlich als `hiddenimports`.
- Einstieg `run_cwdecoder.py` → `cwdecoder/app_main.py`:
  - ohne Argumente (oder `--n1mm`) die GUI,
  - `--decode <wav> [--expect …] [--freq …] [--trace]` Offline-Decodierung,
  - `--list-devices` Geräteliste, `--version` Version und Kanal.
- Kommandozeilen-Ausgabe der Fenster-EXE: Umleitung (`> datei`) geht direkt;
  sonst hängt sich die EXE per `AttachConsole` an die Konsole des Aufrufers;
  ohne Konsole landet die Ausgabe in `<App-Ordner>\logs\cli-ausgabe.txt`.
- Fehler in den Kommandozeilen-Modi werden abgefangen (stderr, Exit-Code 1).
  Ein unbehandelter Fehler würde in der Fenster-EXE einen Dialog öffnen und
  den Aufrufer – z. B. den Release-Workflow – blockieren.
- Prüfung nach jedem Build: `CWDecoder.exe --version` und
  `CWDecoder.exe --decode <Testsignal>` müssen stimmen (lokal laut
  `docs/BUILD.md`, im Release-Workflow automatisch), die GUI muss ohne
  Fehlerdialog starten.

## Konsequenzen

- Kein Python auf dem Zielrechner nötig; Bundle ca. 140 MB, Installer ca.
  40 MB.
- Das Bundle enthält PortAudio-Dateien für andere Plattformen (32 Bit, ARM,
  macOS) mit, weil `collect_all` das ganze Datenpaket nimmt. Harmlos, kostet
  ein paar MB.
- Bei Python- oder Bibliotheks-Updates muss der Build neu geprüft werden;
  der Smoke-Test im Workflow fängt die gröbsten Fehler ab.
- In `cmd`/PowerShell erscheint die Ausgabe ohne Umleitung erst nach dem
  Prompt (Windows wartet nicht auf Fensterprogramme). Dokumentiert in
  `docs/BUILD.md`.

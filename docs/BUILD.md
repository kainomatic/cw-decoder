# CW Decoder bauen (EXE und Installer)

Normalerweise baut GitHub Actions alles beim Setzen eines Tags
(`.github/workflows/release.yml`, ADR-0014). Diese Anleitung ist für den
lokalen Build, z. B. um Änderungen an `cwdecoder.spec` oder den
Installer-Skripten vor dem Tag zu prüfen.

## Voraussetzungen

| Was | Hinweis |
|-----|---------|
| Windows 10/11, 64 Bit | Build- und Zielplattform |
| Python 3.12, 64 Bit | Referenzversion |
| PyInstaller | `pip install pyinstaller` (nur Build, keine Laufzeit-Abhängigkeit) |
| Pillow | für das Icon, steht in `requirements-dev.txt` |
| Inno Setup 6 | `winget install JRSoftware.InnoSetup` oder `choco install innosetup` |

## 1. Umgebung

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
pip install pyinstaller
```

## 2. Icon erzeugen

```
python tools/make_icon.py
```

Schreibt `assets/cwdecoder.ico` (16–256 px). Die Datei ist ein Build-Artefakt
und nicht im Repo.

## 3. Bundle bauen (ADR-0011)

```
pyinstaller --noconfirm cwdecoder.spec
```

Ergebnis: `dist\CWDecoder\CWDecoder.exe` mit dem Ordner `_internal\`
(onedir, kein Python auf dem Zielrechner nötig).

Schnelltest:

```
python -m cwdecoder.gen "CQ TEST DE DF1DS K" -o t.wav --wpm 25 --snr 20 --seed 1
dist\CWDecoder\CWDecoder.exe --decode t.wav --expect "CQ TEST DE DF1DS K" > out.txt
type out.txt
dist\CWDecoder\CWDecoder.exe --version > out.txt & type out.txt
dist\CWDecoder\CWDecoder.exe
```

Der letzte Aufruf startet die Oberfläche; es darf kein Fehlerdialog kommen.

Die EXE ist ein Fensterprogramm. In `cmd` und PowerShell erscheint die
Ausgabe der Kommandozeilen-Modi direkt in der Konsole, aber erst nach dem
Prompt (Windows wartet nicht auf Fensterprogramme). Mit Umleitung
(`> out.txt`) wartet die Shell und die Ausgabe ist vollständig. Ohne
Konsole (Doppelklick, Verknüpfung) landet sie in
`%APPDATA%\CWDecoder\logs\cli-ausgabe.txt`.

### Fallstricke

- **PortAudio:** `sounddevice` lädt die DLL zur Laufzeit aus dem Paket
  `_sounddevice_data`. `cwdecoder.spec` sammelt beide Pakete per
  `collect_all`; fehlt die DLL, findet die GUI keine Geräte.
- **scipy:** Die Hooks aus `pyinstaller-hooks-contrib` reichen;
  `scipy.signal` und `scipy.io.wavfile` stehen zur Sicherheit in
  `hiddenimports`.
- `build/` und `dist/` sind in `.gitignore`.

## 4. Installer bauen (ADR-0012)

```
"%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" /DAPP_VERSION=0.1.0 installer\cwdecoder.iss
"%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" /DAPP_VERSION=0.1.0 installer\cwdecoder-beta.iss
```

(Bei einer Installation für alle Nutzer liegt `ISCC.exe` unter
`C:\Program Files (x86)\Inno Setup 6\`.)

Ergebnis in `installer\Output\`: `CWDecoder-Setup-v0.1.0.exe` bzw.
`CWDecoder-Beta-Setup-v0.1.0.exe`. Ohne `/DAPP_VERSION` gilt der Wert, der
oben in der `.iss` steht.

Der Beta-Installer sollte ein Bundle enthalten, das mit `CHANNEL = "beta"`
gebaut wurde; sonst schreibt die installierte Beta in den Stable-App-Ordner.
Lokal dafür `cwdecoder/__version__.py` vorübergehend ändern und **nicht
committen** (der Release-Workflow macht das automatisch, ADR-0014).

## 5. Release

Releases entstehen nur über Tags (ADR-0002, ADR-0014):

```
git tag v0.1.0-beta1 && git push origin v0.1.0-beta1     # Beta (Claude Code)
git tag v0.1.0 && git push origin v0.1.0                 # Stable (nur DF1DS)
```

Der Workflow prüft, dass die Basis des Tags zu `__version__` passt, baut
Bundle und Installer und hängt die Setup-Datei an das GitHub-Release.

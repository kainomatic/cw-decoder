# ADR-0014: Release-Workflow und Versionsregeln

**Status:** Accepted

## Kontext

ADR-0002 legt fest: nur `main`, Releases per Tag, `__version__.py` als
einzige Versionsquelle. Offen waren der Build-Ablauf, die Nummern während
einer Beta-Phase, wann das CHANGELOG eingefroren wird und wer welche Tags
setzen darf.

## Entscheidung

### Versionen (SemVer 2.0.0)

- `MAJOR.MINOR.PATCH`. MAJOR bei Inkompatibilität (Config lässt sich nicht
  mehr laden, Bedienung grundlegend anders), MINOR bei neuen Funktionen,
  PATCH bei Fehlerbehebungen. Solange MAJOR = 0, dürfen inkompatible
  Änderungen auch in MINOR kommen. Startversion 0.1.0.
- `cwdecoder/__version__.py` trägt im Repo immer die **Ziel-Stable-Nummer**
  `X.Y.Z` und `CHANNEL = "stable"`, auch während einer Beta-Phase.
- Tags: `vX.Y.Z` = Stable, `vX.Y.Z-betaN` = Beta (N ab 1). Beta-Nummern
  werden nie wiederverwendet; scheitert ein Lauf, kommt die nächste Nummer.

### Wer darf taggen

| Tag | Auslöser |
|---|---|
| `vX.Y.Z-betaN` | Claude Code (auf Auftrag oder zum Prüfen des Ablaufs) |
| `vX.Y.Z` | nur nach Freigabe durch DF1DS |

### CHANGELOG

- Während der Beta-Phase sammelt sich alles unter `## [Unreleased]`.
- **Eingefroren wird nur beim Stable-Release:** `[Unreleased]` →
  `## [X.Y.Z] - JJJJ-MM-TT`, darüber ein neuer leerer `[Unreleased]`.

### Workflow (`.github/workflows/release.yml`, Trigger `push: tags: v*`)

1. Checkout, Python 3.12, `pip install -r requirements.txt` +
   `pyinstaller pillow`.
2. `tools/release_tools.py prepare`: Tag-Format prüfen; Basis des Tags muss
   `__version__` entsprechen, sonst Abbruch mit Lösungshinweis. Bei Beta
   werden `CHANNEL = "beta"` und `__version__ = "X.Y.Z-betaN"` nur im
   Arbeitsverzeichnis des Laufs gesetzt (kein Commit), damit die Beta in
   `CWDecoder-Beta` schreibt und ihre volle Version für den Update-Vergleich
   kennt (ADR-0013). Setzt `CHANNEL`, `IS_PRERELEASE`, `APP_VERSION`,
   `FULL_VERSION`, `ISS_FILE`, `SETUP_FILE`.
3. Icon, `pyinstaller cwdecoder.spec`, Smoke-Test des Bundles
   (`--version` muss `FULL_VERSION` und Kanal melden, `--decode` eines
   Testsignals muss den Text liefern).
4. Inno Setup per choco, `ISCC /DAPP_VERSION=X.Y.Z` mit der passenden
   `.iss` (ADR-0012).
5. `tools/release_tools.py notes`: Release-Notes aus `CHANGELOG.md` —
   Beta aus `[Unreleased]`, Stable aus `[X.Y.Z]`; fehlt der Abschnitt,
   Rückfall auf `[Unreleased]`, sonst Platzhaltertext. Kein Abbruch.
6. `softprops/action-gh-release` mit `prerelease` aus dem Tag,
   `fail_on_unmatched_files: true`.

- Die Logik von Schritt 2 und 5 liegt in Python (reine Funktionen) und ist
  in `tests/test_release_tools.py` getestet, statt als Regex im YAML.
- Job-Timeout 30 Minuten.
- Actions auf aktuellen Major-Versionen (`actions/checkout@v7`,
  `actions/setup-python@v7`, `softprops/action-gh-release@v3`, Node 24).

### Ablauf Beta

```
__version__ = "X.Y.Z" (Ziel-Stable), CHANGELOG [Unreleased] pflegen
git tag vX.Y.Z-beta1 && git push origin vX.Y.Z-beta1
… weitere Commits, weiterhin [Unreleased] …
git tag vX.Y.Z-beta2 && git push origin vX.Y.Z-beta2
```

### Ablauf Stable (nach Freigabe durch DF1DS)

```
__version__ prüfen (X.Y.Z), CHANGELOG einfrieren, committen, pushen
git tag vX.Y.Z && git push origin vX.Y.Z
danach __version__ auf die nächste Ziel-Nummer setzen
```

## Konsequenzen

- Tag und Code können nicht auseinanderlaufen (Abbruch vor dem Build).
- Releases sind ohne lokale Schritte reproduzierbar.
- Das Repo zeigt nie `CHANNEL = "beta"`; lokale Beta-Builds brauchen eine
  vorübergehende, nicht committete Änderung (`docs/BUILD.md`).
- Nach einem Stable-Release muss `__version__` erhöht werden, bevor die
  nächste Beta getaggt werden kann (sonst wäre `vX.Y.Z-beta1` älter als die
  installierte Stable und würde nicht angeboten).

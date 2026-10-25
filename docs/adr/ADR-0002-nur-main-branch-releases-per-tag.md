# ADR-0002: Nur der main-Branch, Releases entstehen durch Tags

**Status:** Accepted

## Kontext

Das Projekt hat einen Maintainer (Claude Code) und arbeitet einen Auftrag
nach dem anderen ab. Ein `dev`-/`main`-Modell mit Merges würde Aufwand und
Konfliktpotenzial erzeugen, ohne Nutzen zu bringen. Trotzdem soll es Stable-
und Beta-Versionen geben (ADR-0003: getrennte App-Ordner je Kanal).

## Entscheidung

- Es gibt nur den Branch `main`. Jeder Auftrag wird in kleinen Commits direkt
  auf `main` gebaut und gepusht. Keine Feature-Branches, keine Merges.
- CI (GitHub Actions, `.github/workflows/ci.yml`) läuft bei jedem Push und
  Pull Request auf `main`: pytest unter `windows-latest` und `ubuntu-latest`
  mit Python 3.12.
- Releases entstehen ausschließlich durch Tags auf einen `main`-Commit:
  - `vX.Y.Z` → Stable-Release
  - `vX.Y.Z-betaN` → Beta-Release
- `cwdecoder/__version__.py` ist die einzige Versionsquelle; Tag und
  `__version__` müssen übereinstimmen (Beta-Tags tragen die Ziel-Stable-
  Nummer plus `-betaN`). Versionierung nach SemVer.
- Ein Push auf `main` ist kein Release; die spätere Update-Prüfung richtet sich
  nur nach Tags/GitHub-Releases. Pushen ist deshalb jederzeit unkritisch.
- Build, Installer und der genaue Release-Ablauf werden im Installer-Auftrag
  festgelegt (eigener ADR).
- Python-Referenzversion ist 3.12 (Entwicklung, CI, späterer Build).

## Konsequenzen

- Positiv: Einfacher Ablauf, keine Merge-Konflikte, jeder Stand auf `main`
  ist CI-geprüft.
- Negativ: Ein Hotfix auf eine ältere Stable-Version ist nur über einen
  späteren Tag auf `main` möglich (oder einen dann zu beschließenden
  Hotfix-Branch).

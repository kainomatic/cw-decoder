# ADR-0001: Rollenmodell — Desktop entwirft, Code baut, DF1DS vermittelt

**Status:** Accepted

## Kontext

Das Projekt wird mit zwei Claude-Instanzen entwickelt: Architektur und
Decoder-Kern entstanden in einer Claude-Desktop-Session (gegen synthetische
Signale getestet), Tests am echten Gerät, Bugfixes und Infrastruktur laufen in
Claude Code. Beide haben keinen gemeinsamen Gesprächsverlauf. Ohne klare
Zuständigkeiten drohen doppelte Arbeit, widersprüchliche Änderungen und
verlorene Entscheidungen.

## Entscheidung

| Rolle | Wer | Aufgabe |
|-------|-----|---------|
| **Architekt & Reviewer** | Claude Desktop | Entwirft Architektur und Decoder-Algorithmen, schreibt Aufträge mit Akzeptanzkriterien, reviewt Ergebnisse. Schreibt nicht selbst ins Repo. |
| **Vermittler & Tester** | DF1DS | Überbringt Aufträge und Berichte zwischen den Sessions, testet am Funkgerät mit N1MM, liefert Aufnahmen, entscheidet über Stable-Releases. |
| **Ausführender Maintainer** | Claude Code | Code, Tests, Commits, Push, CI, Doku, ADRs, Issues, Releases. |

- Jeder Auftrag beginnt mit `NEUE SESSION: ja` oder `NEUE SESSION: nein`.
  Bei „ja" führt DF1DS vorher `/clear` aus; Claude Code liest dann die
  Onboarding-Dokumente neu (CLAUDE.md → ROADMAP.md → docs/adr/).
- Immer nur ein Auftrag gleichzeitig am Repo.
- Fragen zur Architektur und größere Umbauten des Decoder-Kerns gehen an die
  Desktop-Session; Claude Code setzt um und meldet Abweichungen im Bericht.
- Dauerhaftes gehört ins Repo, nicht in den Chat: Entscheidungen → ADR,
  Aufgaben/Bugs → GitHub-Issue, Stand → ROADMAP.md.

## Konsequenzen

- Positiv: Klare Zuständigkeit; der Repo-Stand ist die einzige Wahrheit und
  übersteht jeden Session-Wechsel.
- Negativ: Jede Rückfrage kostet einen Umweg über den Vermittler.

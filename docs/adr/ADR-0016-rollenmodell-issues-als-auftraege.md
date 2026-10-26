# ADR-0016: Rollenmodell mit Issue-Recht der Desktop-Session, Aufträge über Issues

**Status:** Accepted

Ersetzt ADR-0001.

## Kontext

Nach ADR-0001 schrieb die Desktop-Session nicht ins Repo; Aufträge und
Berichte wanderten per Copy-Paste über DF1DS zwischen den Sessions. Seit
2026-10-26 hat Claude Desktop GitHub-Zugriff. Damit lassen sich Aufträge,
Rückfragen, Berichte und Reviews direkt im Repo führen – nachvollziehbar und
ohne Kopierfehler. Gleichzeitig muss klar bleiben, wer Code ändern darf.

Die projektübergreifende Arbeitsweise steht jetzt zentral im
[claude-playbook](https://github.com/kainomatic/claude-playbook); dieser ADR
hält fest, was davon für cw-decoder gilt.

## Entscheidung

### Rollen

| Rolle | Wer | Rechte und Aufgaben |
|-------|-----|---------------------|
| **Architekt & Reviewer** | Claude Desktop | Liest das Repo, entwirft Architektur und Decoder-Kern, schreibt Aufträge als Issues, reviewt Berichte gegen den Code. **Schreibt im Repo nur Issues:** anlegen, kommentieren, Labels setzen. Kein Commit, kein Push, kein Tag, keine Release-Änderung, keine Datei-Änderung. |
| **Vermittler & Tester** | DF1DS | Startet Claude Code mit „Bearbeite Issue #N", testet am Funkgerät mit N1MM, liefert Aufnahmen und Logs, entscheidet über Stable-Releases. |
| **Ausführender Maintainer** | Claude Code | **Einziger Schreiber am Code:** Code, Tests, Commits, Push, CI, Doku, ADRs, Tags, Releases; berichtet im Auftrags-Issue. |

Kernlogik, die die Desktop-Session entwirft, kommt als Patch oder genaue
Anweisung in ein Issue und wird von Claude Code eingespielt (mit Testmatrix
vorher/nachher).

### Aufträge über Issues

- Ein Auftrag ist ein Issue mit Label `auftrag`, Autor die Desktop-Session.
  Kopf `NEUE SESSION: ja/nein`, dann Kontext, Aufgabe (je Punkt ein
  Commit), Akzeptanzkriterien. Ein Auftrag kann auch als Kommentar in einem
  bestehenden Issue stehen, das dafür das Label `auftrag` bekommt.
- DF1DS startet Claude Code mit „Bearbeite Issue #N" (bei `ja` vorher
  `/clear`). Claude Code liest das Issue mit allen Kommentaren
  (`gh issue view N --comments`).
- Rückfragen während der Arbeit: Kommentar im Issue.
- Abschlussbericht: Kommentar im Issue mit Commits, `origin/main`-Hash,
  CI-Link, Abweichungen, offenen Punkten.
- Review der Desktop-Session als Kommentar darunter. „Bestanden" → Claude
  Code schließt das Issue mit `Fixes #N` im nächsten (letzten) Commit.
  Korrekturpunkte → Issue bleibt offen, Weiterarbeit mit
  `NEUE SESSION: nein`.
- Immer nur ein Issue mit Label `auftrag` in Arbeit.
- Aufgaben-Issues ohne `auftrag` (z. B. #1–#3) sind Sammlung; sie werden
  erst durch das Label zum Auftrag. Die Liste steht in `ROADMAP.md` unter
  „Beschlossen, noch nicht umgesetzt".

Unverändert aus ADR-0001: Dauerhaftes gehört ins Repo (Entscheidung → ADR,
Aufgabe → Issue, Stand → ROADMAP.md); Architekturfragen und größere Umbauten
am Decoder-Kern gehen an die Desktop-Session.

## Konsequenzen

- Kein Copy-Paste mehr zwischen den Sessions; Auftrag, Bericht und Review
  stehen zusammen im Issue.
- Eine neue Desktop-Session braucht nur den Startsatz und `ROADMAP.md`.
- Klare Schreibgrenze: Code ändert nur Claude Code, damit bleibt `main`
  CI-geprüft und es gibt keine konkurrierenden Änderungen.
- Ein Auftrag ist erst erledigt, wenn das Review „bestanden" sagt; das
  Schließen kostet einen weiteren kleinen Commit.

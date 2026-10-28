# ADR-0029: CI nach geänderten Dateien, Volllauf vor jedem Tag

**Status:** Accepted

## Kontext

Seit #22 dauerte die CI unter Windows 7–12 min, unter Linux ~10½ min und
lief bei jedem Push, auch bei reinen Doku-Commits (ROADMAP, CHANGELOG,
ADR). Der größte Teil der Zeit steckt in wenigen Tests des Decoder-Kerns
(Testmatrix, echte Aufnahmen, Blockgröße, Vertrauen). DF1DS: nichts
Unnötiges laufen lassen, ohne Schutz zu verlieren (#28).

## Entscheidung

**A – Tests verschlanken.** `tests/test_blockgroesse.py` prüft die echten
Aufnahmen nur noch bei 160 und 512 Samples (GUI und Matrix), die 20
Matrix-Fälle weiter bei 80/160/512/1024. `tests/test_confidence.py`
vergleicht mit/ohne Vertrauen an 20 Matrix-Fällen gleichmäßig über alle 11
Kategorien statt an allen 110. Den Volltest der Blockgröße macht weiter
`python tests/run_matrix.py --blocks`.

**B – Tests nach geänderten Dateien.**
- Zwei pytest-Marker (registriert in `pyproject.toml`, mit
  `--strict-markers`): **`decoder`** (Matrix, echte Aufnahmen, Blockgröße,
  Vertrauen, erste Zeichen) und **`gui`** (GUI-Rauchtest, Fenster-Tests).
  Der alte Marker `slow` entfällt. Alles ohne Marker sind die schnellen
  Tests.
- Ein Job `changes` in `ci.yml` bestimmt per `git diff --name-only` die
  geänderten Dateien des Pushs bzw. Pull Requests und ordnet jede einer
  Gruppe zu. Die Regeln stehen an einer Stelle, in
  `tools/ci_select.py` (reines Python, lokal ausprobierbar:
  `python tools/ci_select.py cwdecoder/dsp.py README.md`):

  | Gruppe | Dateien | Lauf |
  |---|---|---|
  | alles | `.github/workflows/*`, `requirements*.txt`, `pyproject.toml`, `pytest.ini`, `tests/conftest.py`, `tools/ci_select.py` | alle Tests |
  | handbuch | `README.md`, `docs/N1MM.md`, `docs/VERGLEICH.md`, `docs/handbuch/**` | nur `tests/test_handbuch.py` |
  | doku | übrige `*.md`, `docs/adr/**` | kein Lauf |
  | decoder | `dsp`, `timing`, `decoder`, `morse`, `gen`, dazu `decode_wav`, `testtext`, `callsign`, `scp`, `segment`, `master.scp`, `qso_words.txt`; `testdata/**`, `tests/run_matrix.py`, `tests/real_baseline.json`, die decoder-Tests selbst | schnelle Tests + `-m decoder` |
  | gui | `cwdecoder/gui*.py`, `live`, `n1mm`, `fldigi_rpc`, `replay`, `ringbuffer`, `tests/gui_smoke.py`, `tests/test_gui*.py` | schnelle Tests + `-m gui` |
  | code | alles andere (auch Unbekanntes) | schnelle Tests |

  Mehrere Gruppen addieren sich (decoder und gui zusammen = alles).
- Reine Doku startet den Workflow gar nicht (`on.push.paths` mit
  Ausschlüssen); das Skript kommt bei Pull Requests zum selben Ergebnis.
- `workflow_dispatch`: von Hand auslösbar, dann immer Volllauf.
- **Volllauf vor jedem Tag:** `release.yml` ruft als ersten Job `ci.yml`
  mit `full: true` auf (Windows und Linux, alle Marker, getaggter Commit);
  der Build-Job hängt per `needs: tests` daran. Ohne grünen Volllauf gibt
  es kein Bundle, keinen Installer und kein Release.
- Lokal gilt weiter CLAUDE.md „Testen": bei Kern-Änderungen Volllauf plus
  Testmatrix.

`git diff` im Job statt `dorny/paths-filter`: keine fremde Action, die Regeln
sind mit pytest prüfbar (`tests/test_ci_select.py`), und der Job schreibt
seine Entscheidung mit der Dateiliste in die Zusammenfassung des Laufs.

## Risiko: versteckte Abhängigkeiten

Eine Änderung an einer Datei der Gruppe „code" kann einen decoder- oder
gui-Test brechen, der dann erst später läuft. Abgefangen durch:

1. **Importprüfung** (`tests/test_ci_select.py`): Der Test geht alle
   Importe der decoder-Tests und von `run_matrix.py` durch, auch Importe in
   Funktionen, rekursiv durch das Paket. Jedes gefundene `cwdecoder`-Modul
   muss in der Gruppe `decoder` stehen oder mit Begründung als Ausnahme
   (`__init__`, `paths`, `live`). So kamen `decode_wav`, `testtext`,
   `callsign`, `scp` und `segment` in die Gruppe, die im Auftrag nicht
   standen. Ein neuer Import in der Signalkette fällt sofort auf.
2. **Marker-Prüfung:** Eine Testdatei mit `mark.decoder` muss selbst in
   der Gruppe `decoder` stehen, eine mit `mark.gui` in `gui`.
3. **Sicherheitsnetz:** Unbekannte Dateien zählen als Code, nie als Doku;
   Änderungen an Workflow, Abhängigkeiten oder pytest-Konfiguration lösen
   alles aus; ein Push ohne bestimmbare Basis (erster Push, Force-Push)
   ebenfalls.
4. **Volllauf vor jedem Tag.** Was die Auswahl übersieht, fällt spätestens
   vor der nächsten Beta auf, bevor etwas den Shack-PC erreicht.

Für die gui-Gruppe gibt es keine Importprüfung: `gui.py` importiert fast
das ganze Paket, die Gruppe würde alles umfassen. Hier verlassen wir uns
auf den Volllauf vor dem Tag; die Fenster-Tests laufen ohnehin nur unter
Windows.

## Konsequenzen

- Doku-Commits kosten keine CI-Zeit mehr, Code-Commits außerhalb von
  Decoder und GUI laufen nur die schnellen Tests.
- Ein Fehler in einem decoder-/gui-Test kann bis zum nächsten Tag
  unentdeckt bleiben, wenn nur „code" geändert wurde; dann scheitert der
  Release-Lauf vor dem Build, und die Beta-Nummer ist verbraucht (ADR-0014).
  Wer unsicher ist, startet den Volllauf von Hand (`gh workflow run ci.yml`).
- Neue Module der Signalkette, neue Daten der decoder-Tests und neue
  GUI-Module müssen in `tools/ci_select.py` eingetragen werden (die
  Importprüfung erzwingt es für die decoder-Gruppe).
- ADR-0017 und ADR-0028 nennen noch den Marker `slow`; gemeint ist jetzt
  `decoder`.

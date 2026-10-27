# ADR-0026: Super Check Partial und Wörterbuch-Segmentierung

**Status:** Accepted

## Kontext

Shack-Test mit Beta 13 (#20, Auftrag #23). Zwei Befunde, die der
Decoder-Kern nach der Tastung richtig macht und die trotzdem falsch
aussehen:

1. **Pausen im Rufzeichen.** IK2JET gibt nach `J` und `E` Pausen von
   5,5 Punkten (`194453`), mehr als zwischen seinen Wörtern. Der Decoder
   schreibt korrekt `IK2J E T`; ein Mensch liest IK2JET aus dem Kontext.
2. **Wörter ohne Abstand.** LA8IG und IN3TWX geben Wortabstände so kurz wie
   Zeichenabstände (`202035`, `193609`): `TNXFERFBCALL`,
   `URRST5995NN5NN`, `GETUESUR569569BK`.

Beides ist Textverarbeitung **nach** dem Decoder. `dsp.py`, `timing.py`
und `decoder.py` bleiben unberührt, `CWDecoder.get_text()` liefert weiter
den rohen Decodertext, das Decodier-Log ebenso.

## Entscheidung

### Super Check Partial (`scp.py`)

- `MASTER.SCP` von supercheckpartial.com liegt als
  `cwdecoder/data/master.scp` im Programm (≈ 50 000 Rufzeichen aus
  Contest-Logs, ≈ 300 KB). Aktualisiert wird sie wie `cty.dat` nur von
  Hand mit `tools/update_scp.py`, kein Download zur Laufzeit.
- Geladen beim ersten Zugriff bzw. im Hintergrund beim GUI-Start
  (≈ 25 ms), gecacht und thread-sicher; nicht aus `gui_start` importiert
  (ADR-0020). Fehlt die Datei, gilt nichts als bekannt (alles gelb).
- `is_known(call)` (auch ohne `/P`, `DL/`), `near(call)`: bekannte
  Rufzeichen einen Edit entfernt (einfügen, löschen, ersetzen), längster
  gemeinsamer Anfang zuerst, höchstens 10.
- `CWDecoder.exe --scp RUFZEICHEN` (bekannt / ähnlich: … / unbekannt),
  im Release-Workflow am fertigen Bundle geprüft.

### Rufzeichen mit SCP (`callsign.py`, GUI)

- **Zusammensetzen.** Endet ein Wort mit einem Rufzeichen, das nicht in
  SCP steht, wartet der Spotter auf das nächste Wort. Folgen 1–2 Wörter
  aus je einem Buchstaben (oder eines aus zwei Buchstaben) und ist die
  Verkettung bekannt, meldet er die Verkettung mit der ganzen Spanne
  (Knopf, Spot, Markierung), sonst das Rufzeichen wie gehört.
  „Bekannt" heißt: in SCP **oder in dieser Sitzung schon einmal ganz
  gehört**. Grund: IK2JET steht nicht in der SCP vom 23.10.2026; in
  `194453` gibt er sein Rufzeichen aber einmal ohne Pausen. Danach wird
  jedes `IK2J E T` als IK2JET gezählt, vorher als IK2J.
- Das Warten verzögert nur Rufzeichen, die nicht in SCP stehen, und nur,
  bis das Folgewort mehr als zwei Zeichen oder eine Ziffer hat (bzw. bis
  zur nächsten Pause).
- **Farbe.** In SCP: Knopf-Rufzeichen und Markierung im Text grün
  (`CALL_SCP_BG`), sonst gelb wie bisher. Tooltip „in Super Check
  Partial" bzw. „nicht in SCP".
- **Vorschlag.** Nicht in SCP, aber Nachbarn mit einem Edit: Tooltip
  „ähnlich: …". Bei genau einem Nachbarn bietet ein Rechtsklick auf den
  Knopf „X übernehmen" an (Knopf ersetzen, Übergabe wie Klick).
  **Nie automatisch ersetzen:** SCP enthält nur Stationen, die in
  Contest-Logs vorkamen; ein unbekanntes Rufzeichen ist nicht falsch, und
  ein Edit-Nachbar ist oft eine andere echte Station (OY1CT/OY1CW). Der
  Operator entscheidet.
- `NOT_CALLS` und die Erkennung im Zeichenstrom (ADR-0019) bleiben.

### Wörterbuch-Segmentierung (`segment.py`)

- Wortschatz `cwdecoder/data/qso_words.txt` (≈ 90 Floskeln), dazu Muster:
  Rapport (`[3-5E][3-9N][1-9N]`, also 599, 5NN, ENN), Zahlen (1–4
  Ziffern), abgekürzte Zahlen, Rufzeichen (`looks_like_call`, mit SCP).
  Prosigns, `*` und `?` trennen ein Wort in unabhängig zerlegte Stücke.
- Dynamische Programmierung über alle Zerlegungen eines Stücks ab
  5 Zeichen, billigste gewinnt:

  | Teil | Kosten | zählt als bekannt |
  |------|--------|-------------------|
  | Wort aus dem Wortschatz (≥ 2 Buchstaben) | 1 | 1 |
  | Rapport | 0,6 | 1 |
  | Rufzeichen in SCP | 1 | 2 (unter 5 Zeichen: 1) |
  | Rufzeichen nicht in SCP, ≥ 5 Zeichen | 3 | 1 |
  | Zahl (eine Ziffer nur am Rand) | 1 | 0 |
  | abgekürzte Zahl, Einzelbuchstabe K/R/W | 1–1,1 | 0 |
  | unbekannter Rest (≥ 2 Zeichen) | 2 je Zeichen | – |

  Übernommen wird eine Zerlegung nur mit **höchstens einem unbekannten
  Rest und mindestens zwei bekannten Teilen**. Nicht zerlegt werden
  Wörter, die selbst bekannt, ein Muster, ein Rufzeichen oder reine
  Ziffern sind, und Wörter in Rufzeichenform mit langem Suffix
  (`DJ7PRRFB`: ob das R zum Rufzeichen gehört, weiß nur der Kontext).
- Die Gewichte sind an Fehlzerlegungen abgestimmt: Einzelbuchstaben,
  Zahlen und kurze Rufzeichen ohne SCP kommen in Fünfergruppen ständig vor
  und zählen deshalb nicht als bekannt; der Rapport ist billiger als eine
  Zahl, damit `569569` zu `569 569` wird und `5995NN5NN` nicht zu
  `5995 NN5NN`. Ergebnis: Die 110 Soll-Texte der Matrix (Seeds 1000,
  5000, 7777) bleiben Wort für Wort unverändert, von 20 000 zufälligen
  Fünfergruppen werden 23 zerlegt (0,1 %, meist echte Floskeln wie
  `DRRIG`).
- **Sichtbare Trenner.** Ein eingefügter Trenner ist kein gehörter
  Wortabstand. Im Textfenster steht ein grauer Mittelpunkt `·` (Tag
  `inferred`, Tooltip), im Terminal ebenfalls `·`; das Decodier-Log und
  `get_text()` bleiben roh. So bleibt erkennbar, was der Decoder gehört
  und was das Wörterbuch ergänzt hat – wichtig für Testdaten und für das
  Vertrauen in den Text.
- **N1MM-Engine** bekommt **echte Leerzeichen** (`n1mm_engine_segmented`,
  Standard an), damit N1MMs eigene Rufzeichenerkennung im CW Reader
  profitiert. Dafür gibt die GUI jedes Wort erst an seinem Ende an die
  Engine (ein Wort Verzögerung). Der Spotter meldet die Trennstellen dazu
  vor dem Leerzeichen des Wortes (`LiveDecoder._space` füttert den
  Spotter zuerst).
- Der Spotter arbeitet weiter auf dem Rohstrom (ADR-0019) und zusätzlich
  auf den zerlegten Teilen; ein Rufzeichen aus der Zerlegung zählt aber
  nur, wenn es in SCP steht (sonst entstünden Knöpfe wie `N73TUE` aus
  `5NN73TUE`).
- Schalter `segment_words` (Standard an) und `n1mm_engine_segmented` im
  Menü Einstellungen; `--no-segment` für `live` und `decode_wav`.

### Kleinigkeiten

- `-...-.-` ist `<BK>` (BT und K ohne Pause, #20).

## Konsequenzen

- `IK2JET` wird in `194453` gemeldet; `TNX·FER·FB·CALL` und
  `RST·599·5NN·5NN` stehen in der Anzeige von `202035`.
- Rufzeichen außerhalb von SCP erscheinen ein bis drei Zeichen später als
  Knopf.
- Die SCP enthält keine Lizenzangabe; die Seite stellt sie frei für
  Logprogramme bereit, N1MM und andere liefern sie mit (`THIRD_PARTY.md`).
- Ein neues Wort im Wortschatz kann Fehlzerlegungen bringen;
  `tests/test_segment.py` prüft die Matrix-Texte und Zufallsgruppen.
- Die Matrix ist nicht betroffen (sie misst `get_text()`).

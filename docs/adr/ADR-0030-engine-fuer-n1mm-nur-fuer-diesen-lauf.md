# ADR-0030: Engine für N1MM nur für diesen Lauf, zweite Instanz bittet die erste

**Status:** Accepted (ersetzt ADR-0022 Punkt 5, Satz zum Hinweisfenster)

## Kontext

Shack-Test mit `v0.1.0-beta19` (#30): Der CW Decoder lief mit
N1MM-Anbindung, aber ohne den Weg „CW Reader von N1MM (Engine)“. Öffnete
DF1DS in N1MM den CW Reader, startete N1MM einen zweiten CW Decoder. Der
erkannte, dass der erste die Engine nicht anbietet (ADR-0022 Punkt 5), und
zeigte 10–13 s ein Hinweisfenster. Danach hing N1MM. Die Prüfung war
richtig, die Bedienung eine Sackgasse.

Entscheidung DF1DS (29.10.): Variante a – ruft N1MM nach dem Decoder,
schaltet die laufende Instanz die Engine für diesen Lauf ein; Haken und
Config bleiben unverändert.

## Entscheidung

1. **Zweite Instanz bittet, statt zu warnen.** Wird sie als Engine
   gestartet (`--xmlrpc-server-port`/`-ti`) und ist der Port nicht
   erreichbar, schreibt sie `engine-request.json` neben `cwdecoder.lock`
   (Port, Titel, PID, Zeit; atomar über eine .tmp-Datei) und wartet bis
   5 s im 0,2-s-Takt auf den Port. Dann endet sie, ohne Dialog, mit
   Logzeile („nach 0.2 s erreichbar“ bzw. „nach 5.0 s nicht erreichbar“).
   Das Fenster der ersten holt sie wie bisher nach vorn (ADR-0020); das
   „startet gerade“-Fenster entfällt im Engine-Fall.
2. **Erste Instanz holt die Anforderung in `_poll()` ab** (4-mal je
   Sekunde, ADR-0009), löscht die Datei und ruft `App.request_engine(port,
   title)`. Anforderungen älter als 30 s gelten als Rest eines
   Absturzes und werden verworfen. Modul `cwdecoder/engine_request.py`,
   nur Standardbibliothek (wird vor dem Lock geladen, ADR-0020).
3. **Engine nur für diesen Lauf** (`App.engine_forced`): Port und Titel von
   N1MM, wirksame Wege = Haken plus Engine; ist die N1MM-Anbindung aus,
   läuft nur die Engine (Spot, Eintippen, Zwischenablage aus). Statuszeile:
   „Engine für N1MMs CW Reader eingeschaltet (nur dieser Lauf)“. Kommt die
   Engine nicht hoch (Port belegt), zeigt die erste das über
   `report_error`. Schaltet der Nutzer den Engine-Haken selbst um, endet
   der Sonderfall; dann gilt der Haken.
4. **Start durch N1MM ohne laufende Instanz** benutzt denselben Zustand:
   bisher setzte er Anbindung und Engine-Haken für diesen Lauf auf an
   (sichtbar, und mit allen übrigen Wegen). Jetzt bleiben die Haken wie
   gespeichert, nur die Engine läuft zusätzlich.
5. **Nur Geändertes speichern:** `_n1mm_changed` schreibt nur die Haken,
   die sich seit dem letzten Aufruf geändert haben. Bisher schrieb jeder
   Haken alle sechs `n1mm_*`-Werte, auch Werte, die nur für diesen Lauf
   galten (`--n1mm`, Start durch N1MM). Der Port für diesen Lauf wird nie
   gespeichert (`set_rpc_port` speichert nur bei Eingabe im Dialog).

Mechanismus Datei statt Fensternachricht oder Socket: Die zweite Instanz
kennt den Lock-Ordner ohnehin, Datei und `_poll` brauchen keinen weiteren
Port und keinen Thread, und eine Anforderung, die ankommt, während die
erste noch lädt, bleibt liegen, bis `_poll` läuft.

## Nachweis

Entwicklungsrechner, N1MM 1.0.7711, echter Decoder (erste Instanz:
`gui_start.main` mit simuliertem Audioeingang, weil der Rechner keine
Soundkarte hat; zweite Instanz: gebautes Bundle, von N1MM gestartet).
Bedienung über MSAA/Fensternachrichten, keine echten Eingaben.

| Fall | Ergebnis |
|---|---|
| Decoder läuft, Engine-Haken aus (wie Shack-Log), N1MM startet, CW Reader öffnen | zweite Instanz: Anforderung, Engine nach 0,2 s erreichbar, Ende; N1MM 232 Prüfungen ohne Hänger (`WM_NULL`, 2 s Frist); CW Reader zeigt „CQ TEST DE DL1ABC DL1ABC K“ |
| CW Reader schließen und neu öffnen | `fldigi.terminate`, Engine läuft weiter; zweite Instanz findet sie, keine Anforderung; Text kommt, kein Hänger |
| Decoder mit Engine-Haken, N1MM startet danach | wie bisher (ADR-0022, #13), kein Hänger, Text kommt |
| Config nach Ende und Beenden | byte-gleich mit vorher (beide Fälle) |

## Konsequenzen

- Der Engine-Haken unter „Übergabe…“ ist für den CW Reader nicht mehr
  nötig; er entscheidet nur noch, ob die Engine auch ohne Ruf von N1MM
  läuft.
- `_MSG_ENGINE_OFF`, `check_engine_of_first` und `ENGINE_NOTICE_MS`
  entfallen.
- Läuft schon ein CW Decoder und startet N1MM den CW Reader, steht die
  N1MM-Anbindung bei ausgeschaltetem Haken trotzdem in der Statusspalte
  (Engine-Zeile), bis der Decoder beendet wird.
- `tools/ci_select.py`: `cwdecoder/engine_request.py` gehört zur Gruppe
  `gui` (Ergänzung zu ADR-0029).
- Offen: Das Nach-vorn-Holen des Decoder-Fensters (ADR-0020) nimmt N1MM
  beim Öffnen des CW Readers den Fokus; im Nachweis scheiterte es an der
  Fokussperre und störte nicht.

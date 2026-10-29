# ADR-0022: Anbindung an N1MM als fldigi-kompatible Engine

**Status:** Accepted; Punkt 5, Satz zum Hinweisfenster der zweiten Instanz:
Superseded by ADR-0030

## Kontext

Ein erkanntes Rufzeichen soll mit möglichst wenig Handgriffen im
Rufzeichenfeld des N1MM-Entry-Window landen (#3). N1MM Logger+ hat keine
Schnittstelle, die das Rufzeichenfeld von außen setzt; eingehend nimmt es
per UDP nur Spektrumdaten und QSY an. Bisher gab es drei Wege:

- **Entry Window tippen** (Tastatur-Emulation): braucht den Vordergrund,
  kämpft mit der Windows-Fokussperre, trifft bei SO2R/SO2V leicht das
  falsche Fenster.
- **Skimmer-Spot** über einen eigenen Telnet-Cluster (Port 7373): sauber,
  aber das Rufzeichen landet in der Bandmap bzw. im Call-Frame, erst die
  Leertaste übernimmt es; ohne Frequenz kein Spot.
- **Zwischenablage**: Strg+V von Hand.

N1MM hat ein eigenes Fenster **CW Reader** (Window → CW Reader, je Entry
Window eines). Es dekodiert nicht selbst, sondern zeigt den Text einer
externen Engine: fldigi über dessen XML-RPC-Schnittstelle, CwGet oder ein
TNC. N1MM markiert die Rufzeichen im Text, ein Klick übernimmt sie ins
Rufzeichen- bzw. Exchange-Feld. Das ist die Bedienung, die DF1DS aus N1MM
kennt. DF1DS hat am 27.10.2026 entschieden: Der CW Decoder wird diese
Engine (Standardweg); Spot, Tippen und Zwischenablage bleiben wählbar.

### Mitschnitt (Issue #3, Phase A)

Mit einem Stub (`tools/fldigi_stub.py`, als `fldigi.exe` gebaut) an N1MM
Logger+ 1.0.7711 gemessen:

- N1MM **startet die Engine selbst** über den Pfad aus *CW Reader → Setup →
  Fldigi*: `<pfad> --xmlrpc-server-port 7367 --wo --config-dir "<ordner>"
  -ti "Fldigi CW Engine 1"`. Der Dateiname wird nicht geprüft; eigene
  Argumente lassen sich im Setup nicht anhängen.
- Port **7367** für CW Reader 1 (7362/7366 gehören dem Digital Interface).
  N1MM verbindet sich mit `http://localhost:<port>`.
- N1MM sucht danach ein **Fenster mit dem Titel aus `-ti`**. Ohne dieses
  Fenster fragt es nie ab („The window 'Fldigi CW Engine 1' could not be
  found after multiple tries"). Ein verstecktes Fenster genügt.
- N1MM blendet das gefundene Fenster ein (es bleibt auch nach dem Schließen
  des CW Readers stehen). Ein Fenster mit Besitzer (tk `transient`) findet
  N1MM dagegen nicht.
- `--config-dir` zeigt auf einen Unterordner neben der EXE (`…\CW`), den
  N1MM für fldigi vorsieht.
- N1MM fragt `fldigi.version` schon vor dem Start ab. Läuft die Engine schon,
  scheitert der gestartete Prozess am Port, und N1MM liest trotzdem von der
  laufenden.
- Aufrufe: `fldigi.version`; `modem.set_by_name('CW')`, `rig.set_mode('CW')`,
  `main.set_frequency(Hz)`; Dauerschleife `rx.get_data` (~200 ms, neue
  Zeichen seit dem letzten Aufruf, base64) und `main.get_trx_status`
  (~400 ms); AFC → `main.set_afc`, Align → `modem.get_carrier` +
  `modem.set_carrier`; Schließen → `rig.release_control`,
  `fldigi.terminate(0)`. „Clear RX" ruft nichts auf. `text.get_rx`,
  `text.get_rx_length`, `text.clear_rx` nutzt N1MM nicht.

## Entscheidung

1. **`cwdecoder/fldigi_rpc.py`**: `FldigiRpcServer` (stdlib
   `xmlrpc.server` mit `ThreadingMixIn`, nur 127.0.0.1, ohne
   `SO_REUSEADDR`) bedient die gemessenen Methoden und die naheliegenden
   Nachbarn (`text.get_rx(start, länge)`, `text.get_rx_length`,
   `text.clear_rx`, `modem.get_name`, `main.get_frequency` …). Unbekannte
   Methoden: einmal je Name loggen, `Fault(-506)` wie fldigi. Wir geben uns
   als fldigi 4.2.05 aus.
2. **`RxBuffer`**: decodierter Text als UTF-8, Prosigns als Text (`<AR>`),
   Wortabstand als Leerzeichen, Absatz als Zeilenumbruch. Länge monoton seit
   Start, gespeichert die letzten 64 kB, ältere Positionen liefern nichts.
   `rx.get_data` hat einen gemeinsamen Lesezeiger wie fldigi. `clear_rx`
   schiebt den Anfang ans Ende, die Länge läuft weiter.
3. **Werte**: `modem.get_carrier` = Tonfrequenz des Trackers (0 ohne Ton);
   `modem.set_carrier` (Align) wird bestätigt, aber nicht übernommen, weil
   der Decoder dem Ton selbst folgt. `main.get_frequency` = Frequenz aus
   RadioInfo (UDP 12060), sonst die letzte `main.set_frequency` von N1MM.
   Diese dient auch den Skimmer-Spots als Frequenz, wenn keine Broadcasts
   kommen.
4. **Erkennungsfenster**: Solange die Engine läuft, hat die GUI ein
   verstecktes tk-Fenster mit dem Titel aus `-ti` (Standard „Fldigi CW
   Engine 1"), ohne Besitzer. Blendet N1MM es ein, versteckt `_poll()` es
   sofort wieder: Es ist leer, und sichtbar hielte Windows es für das
   Hauptfenster (Taskleiste, `taskkill` schickte WM_CLOSE dorthin). Schließen
   des Fensters versteckt es nur. Der RPC-Server fasst kein tk an
   (ADR-0009): Text kommt über den gelockten Puffer, den `_poll()` füllt;
   Tonfrequenz und Funkfrequenz als einfache Attribute.
5. **Start durch N1MM**: `CWDecoder.exe` erkennt den Aufruf an
   `--xmlrpc-server-port` bzw. `-ti` und verhält sich wie `--n1mm-engine`:
   GUI mit N1MM-Anbindung und Engine für diesen Lauf, Port und Titel aus dem
   Aufruf, übrige fldigi-Argumente werden ignoriert. Läuft schon eine
   Instanz, gilt ADR-0020 (die zweite holt die erste nach vorn und endet);
   bietet die erste die Engine nicht an, sagt ein Hinweisfenster, was zu tun
   ist.
6. **`fldigi.terminate`** beendet den CW Decoder nicht. Der Operator
   arbeitet weiter mit ihm; öffnet er den CW Reader in N1MM neu, findet N1MM
   die laufende Engine.
7. **Wählbare Wege** (Config, Dialog „Übergabe…" in der GUI):
   `n1mm_engine` (Standard an), `n1mm_spot` (an), `n1mm_type` (aus),
   `n1mm_clipboard` (aus), `n1mm_rpc_port` (7367), `n1mm_wipe` wie bisher.
   Der Haken „N1MM-Anbindung" schaltet weiter alles zusammen ein und aus
   (Ports erst beim Einschalten). Ein **Einzelklick** auf ein Rufzeichen
   (Knopf oder Markierung im Text) löst Spot, Tippen und Zwischenablage
   aus; den Engine-Weg bedient N1MM selbst. Doppelklick (Wortlaut der
   Entscheidung) nicht, weil tk vor jedem Doppelklick den Einzelklick
   auslöst. Die Zwischenablage bleibt Rückfallweg, wenn das Tippen
   scheitert. Scheitern alle gewählten Klick-Wege, erscheint ein
   Klartextfehler (ADR-0007); neu `SpotNotSentError` und
   `EnginePortInUseError` („Port belegt – läuft fldigi?"), der Decoder läuft
   ohne Engine weiter.

8. **Skimmer-Spots ohne Login**: Der Telnet-Cluster (`SpotServer`) schickt
   Spots ab dem Verbindungsaufbau. N1MM sendet ohne „Automatically Logon"
   kein Rufzeichen und wartet nach `login:`; bisher kam deshalb kein Spot
   an (beim Nachweis gefunden).

## Konsequenzen

- Kein Fensterfokus, keine Tastatur-Emulation: Das Rufzeichen kommt mit
  N1MM-Bordmitteln ins Entry Window, auch bei SO2R (zwei CW Reader).
- Wir hängen an der Methodenliste der N1MM-Version. Ändert ein N1MM-Update
  die Aufrufe, zeigt das Log die unbekannten Methoden; der Stub misst neu.
- Port 7367 kollidiert mit fldigi nur, wenn fldigi selbst als
  CW-Reader-Engine läuft. Dann meldet der Decoder den belegten Port; der Port
  ist im Dialog änderbar (N1MM nimmt aber immer 7367 für Reader 1).
- CW Reader 2 (zweites Entry Window) ist nicht getestet: N1MM nimmt dort
  vermutlich Port 7368 und Titel „Fldigi CW Engine 2"; ein zweiter
  CW Decoder läuft wegen ADR-0010 nicht.
- Der CW Reader lässt sich in N1MM nur öffnen, wenn das Log auf Mode CW
  steht.
- Lizenz: Nachgebaut ist nur das XML-RPC-Protokoll (Methodennamen,
  Typen), kein fldigi-Code.
- Bisherige Nutzer, die das Tippen gewohnt waren, finden es jetzt unter
  „Übergabe…" (Standard aus).

## Nachtrag #13 (28.10.2026): Eigener Name statt „fldigi“, Engine-Fenster bei WM_CLOSE

**Lizenz und Namen.** Nachgebildet ist die XML-RPC-Schnittstelle von fldigi
(W1HKJ, GPL), ohne Übernahme von Code; fldigi ist ein eigenständiges
Projekt und mit dem CW Decoder nicht verbunden. Bisher meldete sich die
Engine als fldigi (`fldigi.name` → „fldigi“, `fldigi.version` → „4.2.05“).
Das Nachbilden einer Schnittstelle ist unproblematisch, sich als fremdes
Programm auszugeben nicht (Namensrecht; im Fehlerfall fiele der Verdacht
auf fldigi). Beschluss: eigener Name, sofern N1MM ihn akzeptiert.

**Mitschnitt** auf dem Entwicklungsrechner, N1MM 1.0.7711, Demo-Engine
mit `CQ TEST DE DL1ABC …`, nur Fensternachrichten (CW Reader per Menü
öffnen, Klick auf DL1ABC, Rufzeichenfeld per `WM_GETTEXT`):

| Variante | `fldigi.name` / `fldigi.version` | Text im CW Reader | Klick → Rufzeichenfeld | Meldung von N1MM |
|---|---|---|---|---|
| a | „CW Decoder“ / „0.1.0“ | ja | DL1ABC | keine |
| b | „CW Decoder“ / „4.2.05“ | ja | DL1ABC | keine |
| c | „fldigi“ / „4.2.05“ (bisher) | ja | DL1ABC | keine |

N1MM ruft nur `fldigi.version` auf und prüft keine Mindestversion;
`fldigi.name` und `fldigi.name_version` fragt es nicht ab.

**Entscheidung: Variante a.** `fldigi.name` → `APP_NAME` („CW Decoder“),
`fldigi.version` → `__version__` ohne Beta-Anhang (rein numerisch X.Y.Z wie
bei fldigi; nachgewiesen ist nur diese Form, ein Anhang „-beta18“ wäre
ungeprüft), `fldigi.name_version` → „CW Decoder 0.1.0-beta18
(fldigi-kompatibel)“ mit voller Version, `fldigi.version_struct` passend.
Der Fenstertitel „Fldigi CW Engine 1“ bleibt, N1MM schreibt ihn vor
(`-ti`). Log-Zeilen heißen jetzt `CW-Reader-Engine: …`.

**Engine-Fenster bei WM_CLOSE (beim Mitschnitt gefunden).** N1MM blieb beim
Start im Startbild hängen, wenn der CW Decoder schon mit Engine lief (auch
die Hänger in #24). Ursache: Beim Start schickt N1MM WM_CLOSE an jedes
Fenster „Fldigi CW Engine 1“, bis es verschwindet (gemessen gut 3600-mal
pro Sekunde), vermutlich um ein übrig gebliebenes fldigi zu beenden. Unser
Fenster versteckte sich bei WM_CLOSE nur. Jetzt zerstört der CW Decoder
das Fenster bei WM_CLOSE und legt es nach `ENGINE_WIN_REOPEN_MS` (1,5 s)
neu an; der XML-RPC-Server läuft weiter. Nachgewiesen: N1MM startet bei
laufender Engine normal, der CW Reader zeigt danach Text, Klick setzt
DL1ABC. Test: `tests/test_gui_app.py::test_engine_fenster_schliesst_bei_wm_close`.
Nebenbefund: `CWReader1` in der N1MM-INI steht unter
`[FontSizeAdjustments]` und hat mit dem Öffnen des CW Readers nichts zu tun.

# CW Decoder – Stand und nächste Schritte (ROADMAP.md)

> Steuert die **Reihenfolge** der Arbeit. Lebendes Dokument: Status bei jedem
> Auftrag aktualisieren (`✅` erledigt, `🔧 IN ARBEIT`, `➡️` als Nächstes,
> `⏳` später). Entscheidungen stehen in `docs/adr/`, Aufgaben in GitHub-Issues.
> Erste Datei, die jede neue Session liest.

---

## Einstieg für eine neue Desktop-Session

> Lies `CLAUDE.md`, diese ROADMAP, `docs/adr/README.md` und die offenen Issues (`gh issue list` oder GitHub). Du bist Architekt und Reviewer: Du liest das Repo, schreibst Aufträge für Claude Code (Kopf `NEUE SESSION: ja/nein`), reviewst Berichte gegen den Code und legst Issues an. Du pushst nie. Der Stand steht in "Aktueller Stand", der Plan unter "Beschlossen, noch nicht umgesetzt".

Rechte der Desktop-Session im Repo (ADR-0016): **nur** Issues anlegen,
kommentieren und Labels setzen. Keine Commits, kein Push, keine Tags, keine
Releases, keine Datei-Änderungen. Ausnahme: Push nach Einzelfreigabe durch
DF1DS, nur Daten oder Doku, nie Programmcode (Playbook §1). Kernlogik geht als Patch oder genaue
Anweisung in ein Issue; Claude Code spielt sie ein.

Ablauf eines Auftrags (Details: `CLAUDE.md` und
[claude-playbook](https://github.com/kainomatic/claude-playbook)):
Issue mit Label `auftrag` → DF1DS startet Claude Code mit „Bearbeite Issue
#N" → Rückfragen und Abschlussbericht als Kommentar im Issue → Review als
Kommentar darunter → bei „bestanden" schließt Claude Code das Issue mit
`Fixes #N`. Immer nur ein `auftrag`-Issue in Arbeit.

Startsatz: *„Lies das Repo kainomatic/cw-decoder, fang mit ROADMAP.md an,
und sag mir, was als Nächstes zu tun ist."*

---

## Aktueller Stand

**Ziel-Version 0.1.0, Beta-Phase.** Decoder-Kern, GUI und
Programm-Infrastruktur stehen; das Programm ist als Setup mit Self-Update
installierbar (Stable/Beta getrennt, ADR-0011 bis ADR-0015).

- Neueste Beta: [`v0.1.0-beta13`](https://github.com/kainomatic/cw-decoder/releases/tag/v0.1.0-beta13)
  (`CWDecoder-Beta-Setup-v0.1.0.exe`, Ringpuffer: „Letzte 30 s speichern"
  und „Nochmal hören", #19; davor beta12 mit grauen unsicheren Zeichen,
  #18, und beta11 mit dem CW Decoder als Engine für N1MMs CW Reader, #3). Self-Update beta2 → beta4 auf dem
  Entwicklungsrechner nachgewiesen. Noch keine Stable.
- Testmatrix (`python tests/run_matrix.py`, zufällige Texte, 11 Kategorien,
  ADR-0017/0018): Mittelwert **97,9 %**, Rauschen 100 % (auch durch
  CW-Filter); Stichproben Seed 5000/7777: 97,2/98,5 %. Alte Matrix
  (`--legacy`): **98,3 %**. Echte Aufnahmen: Fragmente in
  `tests/test_real.py`, Volltext-Stand `tests/real_baseline.json`. Erstes Zeichen nach langer Pause: `tests/test_erstes_zeichen.py`.
- Laufender Auftrag: siehe Issues mit Label `auftrag`
  (`gh issue list --label auftrag`).

**Nächster Schritt:** Review #23, dann Shack-Test mit `v0.1.0-beta15`.
DF1DS aktualisiert auf dem Shack-PC auf `v0.1.0-beta15` (Self-Update), richtet
N1MM nach `docs/N1MM.md` ein und testet mit Funkgerät und N1MM (siehe
„Testablauf Installer/Beta"). Danach
Auswertung der Aufnahmen durch die Desktop-Session und Entscheidung über die
Stable `v0.1.0`.

---

## Leitlinie

Ziel ist ein guter Decoder, der den Operator unterstützt, nicht ersetzt.
Keine 99 %. Bei brauchbaren Signalen sauberer Text; bei schwachen Signalen
Rufzeichen und Rapport so weit, dass man sie mit einem zweiten Hören
bestätigen kann; bei reinem Rauschen kein Müll im Textfenster (wichtiger als
die letzten Prozent). Kein Wahrscheinlichkeits-Decoder für −5 dB, solange
DF1DS es nicht vermisst.

Vergleichsmessungen gegen andere Decoder (z. B. fldigi, `docs/VERGLEICH.md`)
laufen einmalig und außerhalb der CI: Sie brauchen Echtzeit und ein
fremdes Programm. Maßstab in der CI bleibt die eigene Testmatrix.

## Testablauf Installer/Beta

Die Beta wird auf dem Shack-PC erst installiert, nachdem Claude Code auf
seinem Rechner den Self-Update von Beta N auf Beta N+1 nachgewiesen hat
(Dialog, Download, Silent-Install, Neustart mit neuer Version, Logauszug im
Bericht). Danach laufen Testrunden über Self-Update; Aufnahmen aus
`Dokumente\CW Decoder\Aufnahmen` gehen an die Desktop-Session.

Stand: Nachweis beta2 → beta4 erbracht (Arbeitspaket 4); `v0.1.0-beta11`
darf auf den Shack-PC.

Im Shack-Test zusätzlich (ab beta13, #19): Bei einer Fehldecodierung
**Strg+S** drücken; im Aufnahmen-Ordner müssen `cw_…_letzte30s.wav` und
die passende `.txt` liegen, die Statuszeile zeigt „Gespeichert: …".
**Strg+R** spielt die letzten 10 s hörbar über Lautsprecher/Kopfhörer
(Standard-Ausgabegerät), zweites Strg+R bricht ab; einmal mit
Einstellungen → „Nochmal hören langsamer (0,7×)". Die gesicherten
Ausschnitte gehen an die Desktop-Session (Kandidaten für `testdata/`).

## Beschlossen, noch nicht umgesetzt

Offene Aufgaben-Issues (noch kein Auftrag, bis sie das Label `auftrag`
bekommen):

Zurzeit keine; #14 und #15 sind mit #18 umgesetzt (siehe unten).

Ideen, noch nicht beschlossen: #16 (mehrere Stationen gleichzeitig,
„Skimmer light") und #17 (Ideensammlung Contest, Oberfläche; daraus der
Ringpuffer mit #19, die Vertrauensanzeige mit #18 und Super Check Partial
mit #23 umgesetzt). Offen aus #20: Ausgabegerät für „Nochmal hören"
wählbar.

#1, #2 und #5 sind umgesetzt und geschlossen (siehe „Decoder-Tuning" unten).

Issues zum Decoder-Kern (`dsp`) entwirft die Desktop-Session; Claude Code
setzt um und misst die Testmatrix vorher/nachher.

---

## ✅ Arbeitspaket 1 — Decoder-Kern (Desktop-Session)

Signalgenerator, DSP-Kette (Decimator, ToneTracker, Envelope, Thresholder),
TimingDecoder, Offline-Decoder, Testmatrix. Gegen synthetische Signale
getestet.

## ✅ Arbeitspaket 2 — Live-Modus, GUI, N1MM (erste Runde unter Windows)

GUI unter Windows gestartet und per Rauchtest (`tests/gui_smoke.py`,
Fake-Soundkarte) durchgeklickt; Bugfixes bei Start/Stop, Aufnahme, Threading.
N1MM: Entry Window am Titel erkennen, Fokussperre umgehen, Zwischenablage als
Rückfallweg, belegte Ports melden.

## ✅ Arbeitspaket 3 — Programm-Infrastruktur und Projektregeln

Version/Kanal, Ablageorte, Diagnose-Log, Config, Tooltips, Fehlerdialoge,
Fehlerbericht, Single-Instance, Menüleiste, ADRs 0001–0010, pytest + CI
(Windows/Linux, Python 3.12), Lizenz GPL-3.0-or-later.

## ✅ Arbeitspaket 4 — Installer mit Self-Update

- ✅ PyInstaller-Bundle `CWDecoder.exe` mit `--decode`, `--list-devices`,
  `--version` (ADR-0011).
- ✅ Inno-Setup-Installer Stable und Beta, parallel installierbar (ADR-0012).
- ✅ Self-Update: Prüfung beim Start, „Hilfe → Nach Updates suchen",
  Dialog, Download, stille Installation, Neustart; AppMutex (ADR-0013).
- ✅ Release-Workflow über Tags, Release-Notes aus dem Changelog
  (ADR-0014); kein Code-Signing (ADR-0015).
- ✅ Erste Beta-Releases `v0.1.0-beta2` und `v0.1.0-beta4`
  (`-beta1` und `-beta3` ohne Release: Workflow-Fehler, behoben).
- ✅ Update-Nachweis auf dem Build-Rechner: installierte beta2 fand beta4,
  lud sie, installierte still und startete als beta4 neu.
- Folge-Issues: #5 (siehe „Beschlossen, noch nicht umgesetzt"); #6
  (Setup-Datei blieb in `%TEMP%`) erledigt in `v0.1.0-beta5`.

## ✅ Decoder-Tuning — Testmatrix, Tonverfolgung, erstes Zeichen (#1, #2, #5)

Entwurf der Desktop-Session als Patch-Serie, eingespielt mit Auftrag #2.

- ✅ Testmatrix mit zufälligen Texten, 10 Kategorien inkl. reinem Rauschen
  (ADR-0017): 91,8 % → **97,0 %** (Seed 1000); alte Matrix 95,4 % → 98,5 %.
- ✅ Tonverfolgung: Fenster ±60 Hz um die aktuelle Frequenz, Wechsel nur bei
  3 dB stärkerer Linie (#2).
- ✅ Elemente erst am Zeichenende einteilen, adaptive Strich-Schwelle:
  erstes Zeichen falsch bei 10/6 dB in 12/30 bzw. 21/30 Läufen → 0/30 (#5).
- ✅ Rauschteppich während eines Tons eingefroren, Schwellen 65/45 %,
  QSB-Nachführung 40 dB/s.
- Beta `v0.1.0-beta6`.

## ✅ Schmales Empfängerfilter (#8)

- ✅ Linien-Gate im Tracker, Dynamik-Squelch, Tempo-Reset bei Tonverlust,
  robustere Tempo-Schätzung, Tempo 5–60 WPM (ADR-0018).
- ✅ Matrix: Kategorie „CW-Filter", Rauschen zur Hälfte durch CW-Filter:
  96,4 % → **97,7 %**, Rauschen 92 % → 100 %; alte Matrix 98,5 % → 98,3 %. Squelch mit 60 ms Vorausschau, unabhängig von der Blockgröße: erstes Zeichen nach einer Pause auch bei den 20-ms-Blöcken der GUI vollständig.
- Beta `v0.1.0-beta7`.

## ✅ Wortgrenzen, Rufzeichen ohne Wortgrenzen, Decodier-Log (#10)

- ✅ Wortschwelle im Einzel-Cluster-Fall 1,35 × Zeichenpause (Geber mit
  weiten Zeichenabständen, Aufnahme 231339); Matrix unverändert.
- ✅ Rufzeichen-Spotter findet zusammengeklebte und (wenn bekannt)
  zerrissene Rufzeichen (ADR-0019): an 231339 16 statt 8 Vorkommen.
- ✅ Decodier-Log `cw_….txt` neben jeder Aufnahme; Absätze im Textfenster.
- Beta `v0.1.0-beta8`; Review bestanden, #10 geschlossen.

## ✅ Start und GUI-Layout, Rufzeichen im Text (#9)

- ✅ Startfenster vor den schweren Imports, Startphasen im Log (ADR-0020).
- ✅ Lock mit Programm und Startzeit; zweite Instanz holt die erste nach
  vorn statt Dialog.
- ✅ Rufzeichen-Spalte bleibt bei 125–150 % DPI sichtbar; Rufzeichen im Text
  markiert und anklickbar.
- Beta `v0.1.0-beta9`; Review bestanden, #9 geschlossen. Self-Update
  beta8 → beta9 prüft DF1DS auf dem Shack-PC.

## ✅ Flagge und Land an den Rufzeichen (#11)

- ✅ `cty.dat` (AD1C) mitgeliefert, Zuordnung Rufzeichen → DXCC-Entität mit
  `=`-Ausnahmen, längstem Präfix und `/`-Zusätzen (ADR-0021).
- ✅ Deutsche Kurznamen für alle Entitäten, Flaggen als 24×16-PNG
  (Public Domain), Knopf mit Flagge und Landesname, Tooltip mit Zonen.
- ✅ `--dxcc` in der EXE, Bundle-Prüfung im Release-Workflow.
- Beta [`v0.1.0-beta10`](https://github.com/kainomatic/cw-decoder/releases/tag/v0.1.0-beta10);
  Review bestanden, Issue geschlossen.

## ✅ N1MM: CW Decoder als Engine für den CW Reader (#3)

- ✅ Mitschnitt mit Stub (`tools/fldigi_stub.py`) an N1MM 1.0.7711: N1MM
  startet die Engine selbst (Port 7367, Fenstertitel aus `-ti`) und pollt
  `rx.get_data` alle ~200 ms (ADR-0022).
- ✅ `cwdecoder/fldigi_rpc.py`: XML-RPC wie fldigi; Text im CW Reader von
  N1MM, Klick auf ein Rufzeichen setzt es ins Entry Window (nachgewiesen
  mit Testsignal, Screenshots in #3).
- ✅ Wege wählbar im Dialog „Übergabe…" (CW Reader, Spot, Tippen,
  Zwischenablage); Spots auch ohne Telnet-Login; Anleitung `docs/N1MM.md`.
- Beta [`v0.1.0-beta11`](https://github.com/kainomatic/cw-decoder/releases/tag/v0.1.0-beta11);
  Review bestanden, #3 geschlossen.

## ✅ Unsichere Zeichen grau, Rufzeichen-Spalte, Vergleichsdoku (#18, #14, #15)

- ✅ Vertrauen je Zeichen aus Abstand zur Strich-Schwelle, Tempo-Einmessung
  und Pegel; unter 0,5 grau in der GUI, klein im Terminal, dritte Spalte
  im Decodier-Log (ADR-0023). Reine Metadaten: Matrix-Text in allen Fällen
  identisch (Seed 1000/5000/7777: 97,7/96,7/98,4 %, alte Matrix 98,3 %).
- ✅ Rufzeichen-Spalte zeigt nur so viele Knöpfe, wie hineinpassen (#14).
- ✅ `docs/VERGLEICH.md`: Messung gegen fldigi aus #12 (#15).
- Beta [`v0.1.0-beta12`](https://github.com/kainomatic/cw-decoder/releases/tag/v0.1.0-beta12);
  Review bestanden, #18, #14 und #15 geschlossen.

## ✅ Ringpuffer: letzte Sekunden sichern und nachhören (#19)

- ✅ Ringpuffer der letzten 60 s (Audio und Decoder-Ausgabe), tk-frei in
  `ringbuffer.py` (ADR-0024).
- ✅ „Letzte 30 s speichern" (Strg+S): WAV + Decodier-Log im
  Aufnahmen-Ordner; `decode_wav` auf der WAV gibt den Text der TXT.
- ✅ „Nochmal hören" (Strg+R) über das Standard-Ausgabegerät, Stopp per
  zweitem Klick; optional 0,7× ohne Tonhöhenänderung (WSOLA).
- ✅ Einstellungen → „Puffer und Nochmal hören…" (Größen, langsamer).
- Kein Eingriff in `dsp.py`/`timing.py`/`decoder.py`, Matrix unverändert.
- Beta [`v0.1.0-beta13`](https://github.com/kainomatic/cw-decoder/releases/tag/v0.1.0-beta13);
  Shack-Test 27.10. ausgewertet (#20).

## ✅ Adaptive Zeichenschwelle, Störmark-Filter, Teppich-Regel (#21)

- ✅ Aufnahmen vom 27.10. als Testdaten (`REAL_CASES`, `REAL_SPOTS`),
  Volltext-Stand `tests/real_baseline.json`.
- ✅ Zeichenschwelle adaptiv per Clusterung der Pausen, dazu Trennung
  ungültiger Symbole (#20 Befund 3): 194831 liefert `4HX 4HX` statt
  `*X *X` (die Tastung ist `4HX`, nicht `VHX`).
- ✅ Störmark-Filter: kurze Reste nach Aussetzern werden verschmolzen
  (#20 Befund 2); Verwerfen von Knacksern gemessen und aus.
- ✅ Teppich-Regel (#20 Nebenbefund 3): Schalter `carrier_needs_key`,
  Standard unverändert (Aufnahmen minimal anders, ADR-0025).
- Matrix 97,9/97,2/98,5 % (vorher 97,7/96,7/98,4 %), alte Matrix 98,3 %
  (ADR-0025).
- #20 Befund 1 (IK2JET, Wortpausen im Rufzeichen) bleibt für den
  Auftrag Super Check Partial (#23).
- Beta [`v0.1.0-beta14`](https://github.com/kainomatic/cw-decoder/releases/tag/v0.1.0-beta14);
  Review bestanden, #21 geschlossen.

## ✅ Super Check Partial und Wörterbuch-Segmentierung (#23)

- ✅ `master.scp` (supercheckpartial.com, Release 2026.10.23) mitgeliefert,
  `scp.py` mit `is_known`/`near`, `--scp` in der EXE, Bundle-Prüfung im
  Release-Workflow, `tools/update_scp.py` (ADR-0026).
- ✅ Rufzeichen in SCP grün, sonst gelb; Vorschlag bei genau einem
  Nachbarn (Tooltip, Rechtsklick „übernehmen"), nie automatisch.
- ✅ `IK2J E T` → IK2JET (#20 Befund 1 erledigt). IK2JET steht nicht in der
  SCP; zusammengesetzt wird deshalb auch gegen Rufzeichen, die in der
  Sitzung schon einmal ganz gehört wurden.
- ✅ Wörterbuch-Zerlegung: `TNX·FER·FB·CALL`, `RST·599·5NN·5NN`,
  `GE·TU·ES·UR·569·569·BK`; Trenner grau, N1MM-Engine mit echten
  Leerzeichen; 110 Matrix-Texte unverändert.
- ✅ `<BK>` als Prosign (#20).
- Kein Eingriff in `dsp.py`/`timing.py`/`decoder.py`, Matrix nicht
  betroffen.
- Aus #17 damit erledigt: Super Check Partial; davor Ringpuffer (Instant
  Replay, letzte 30 s speichern, #19) und Vertrauensanzeige je Zeichen
  (#18).
- Beta `v0.1.0-beta15`; Review ausstehend.

## ➡️ Stable 0.1.0 (Freigabe DF1DS)

- Beta auf dem Shack-PC installieren, mit Funkgerät und N1MM testen.
- Danach CHANGELOG einfrieren und `v0.1.0` taggen (ADR-0014).

## 🔧 Live-Test am Funkgerät

Erste Runde erledigt (26.10.2026, Shack-PC mit beta6, vier Aufnahmen,
USB-Audio 48 kHz, ausgewertet von der Desktop-Session, #8):

- ✅ Aufnahme und Audio-Weg funktionieren am Shack-PC.
- ✅ Befund: Das CW-Filter im Empfänger ist nur ~100 Hz breit. Rauschen
  dahinter sah wie ein getasteter Ton aus → Müll bei leerer Frequenz,
  danach verschlepptes Tempo („TTTT"). Behoben mit Linien-Gate,
  Dynamik-Squelch und Tempo-Reset (ADR-0018, `v0.1.0-beta7`).
- Ergebnis an den Aufnahmen: Ein sauberer QSO-Partner ist jetzt weitgehend
  lesbar. Ein schwacher Gegenpartner (~10 dB über dem Filterrauschen) gibt
  das Rufzeichen teilweise. Eine sehr unsaubere Handtaste bleibt unlesbar;
  das ist kein Decoder-Ziel.
- ✅ Die vier Aufnahmen liegen als Testdaten in `testdata/real/` (Freigabe
  DF1DS) und werden von `tests/test_real.py` geprüft. Bekannte Lücken an
  190242: `TALLINN` kommt als `T A L L INN`, `UR RST` als `UR FST`.

Zweite Runde (26.10.2026, Aufnahme 231339, 500-Hz-Filter, #10): Rufzeichen,
Rapport und Klartext kommen auch bei Fading und zwei Stationen. Hauptfehler
waren falsche Wortgrenzen bei einem Geber mit weiten Zeichenabständen;
verbessert in `v0.1.0-beta8`. Ein Überlappungsbereich bleibt
(`RSTRST579`, `BUTTHEREWAS`); das liegt am Geber.

Weiter offen:

- `sounddevice` unter Windows: welche Host-API (MME/WASAPI/DirectSound)
  liefert 8 kHz direkt? `open_stream` probiert 8000, 48000, 44100, 16000.
  Am USB-Audio des Funkgeräts und an VB-Cable prüfen, ob es sauber läuft und
  ob der Pegel passt (zu niedrig = Squelch bleibt zu, zu hoch = Clipping;
  beides am SNR in der Statuszeile erkennbar).
- Echte Aufnahmen (Aufnahmeordner, siehe Datei-Menü) sammeln, auswerten
  (`python -m cwdecoder.decode_wav datei.wav --trace`) und geeignete als
  Testdaten nach `testdata/` committen (< 5 MB je Datei).
- Schwache Signale: ab ~0 dB SNR (2,4 kHz) steigen die Fehler. Ideen, erst
  nach Absprache mit der Desktop-Session: Mehrheitsentscheid über mehrere
  Bandbreiten, weicher Decoder (Wahrscheinlichkeiten statt harter Schwellen).
- Farnsworth/gedehnte Abstände: Wortschwelle passt sich erst nach ~3
  Zeichenpausen an; die ersten Wörter werden ggf. zerhackt.

## ⏳ N1MM am echten Logger

- `EntryWindowTyper`: Kommt das Rufzeichen im Entry Window an? Ist Alt+W
  tatsächlich „Wipe"? Fenstertitel aus dem Log prüfen.
- Spot-Server (Telnet 127.0.0.1:7373) in N1MM verbinden und Bandmap-Spots
  prüfen.
- RadioInfo-Broadcasts (UDP 12060): Frequenz und Mode in der GUI.

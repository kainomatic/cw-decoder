# Changelog

Alle nennenswerten Änderungen am CW Decoder stehen in dieser Datei.

Das Format folgt [Keep a Changelog](https://keepachangelog.com/de/1.1.0/),
die Versionsnummern folgen [Semantic Versioning](https://semver.org/lang/de/).
Releases entstehen durch Tags `vX.Y.Z` bzw. `vX.Y.Z-betaN` (ADR-0002).

## [Unreleased]

### Added
- Unsicher erkannte Zeichen stehen im Text grau (Tooltip „unsicher
  erkannt"): ein Element lag knapp an der Grenze Punkt/Strich, das Tempo
  war nach einem Senderwechsel noch nicht eingemessen oder das Signal
  schwach. Rufzeichen mit solchen Zeichen sagen es im Tooltip von Knopf
  und Markierung. Der decodierte Text selbst ändert sich dadurch nicht
  (ADR-0023, #18).
- Im Terminal (`live`, `decode_wav`, `CWDecoder.exe --decode`) sind
  unsichere Zeichen klein geschrieben (`CQ TEST OZ1hGT`).
- Schnittstelle: `CWDecoder.last_conf`, Callback `on_char_conf(ch, conf)`,
  `get_text_marked()`; Gewichte in `TimingConfig`/`DecoderConfig`
  (`conf_*`).
- `docs/VERGLEICH.md`: Vergleichsmessung gegen fldigi 4.2.03 (Testmatrix
  und echte Aufnahmen, #12, #15).
- Der CW Decoder ist Engine für das Fenster **CW Reader** von N1MM Logger+:
  Er stellt die XML-RPC-Schnittstelle von fldigi nach (Port 7367), N1MM
  zeigt den decodierten Text, markiert die Rufzeichen, und ein Klick dort
  setzt sie ins Entry Window. In N1MM unter CW Reader → Setup → Fldigi den
  Pfad zu `CWDecoder.exe` eintragen; N1MM startet den Decoder dann selbst
  bzw. holt die laufende Instanz nach vorn. Anleitung `docs/N1MM.md`
  (ADR-0022, #3).
- Dialog „Übergabe…" in der N1MM-Spalte: Wege einzeln wählbar (CW Reader,
  Skimmer-Spot, Entry Window tippen, Zwischenablage), Port der Engine;
  Statuszeile „CW Reader: N1MM verbunden / wartet auf N1MM".
- `CWDecoder.exe --n1mm-engine`; die Argumente, mit denen N1MM fldigi
  startet (`--xmlrpc-server-port`, `-ti` …), wirken genauso.
- Skimmer-Spots nehmen die Frequenz, die N1MM dem CW Reader mitteilt, wenn
  keine Radio-Broadcasts (UDP 12060) kommen.
- Klartextfehler „Port für den N1MM CW Reader belegt" (läuft fldigi?) und
  „Spot nicht gesendet"; der Decoder läuft weiter.
- `tools/fldigi_stub.py`: Mitschnitt der Aufrufe von N1MM an eine
  fldigi-Engine.
- Rufzeichen-Knöpfe zeigen Flagge und Landesname (z. B. `OY1CT  Färöer`),
  der Tooltip dazu Hauptpräfix, Kontinent und CQ-/ITU-Zone; auch der
  Tooltip der Markierung im Text nennt das Land. Datenquelle `cty.dat`
  (AD1C, CTY-3633), deutsche Kurznamen für alle 346 Entitäten, Flaggen als
  kleine Bilder (ADR-0021, #11).
- `CWDecoder.exe --dxcc RUFZEICHEN` bzw. `python -m cwdecoder.dxcc`: Land
  zum Rufzeichen; Terminal-Modus zeigt `[Rufzeichen: DJ7PR – Deutschland]`.
- `THIRD_PARTY.md` mit Herkunft und Lizenzen der mitgelieferten Daten.
- Startfenster „CW Decoder startet …", solange numpy/scipy/sounddevice
  laden; Startphasen mit Zeit seit Prozessstart im Log (ADR-0020, #9).
- Erkannte Rufzeichen sind im Text markiert (fett, farbig hinterlegt); ein
  Klick übergibt sie wie der Knopf an N1MM, auch innerhalb
  zusammengeklebter Wörter (#9).
- Rufzeichen auch ohne Wortgrenzen: zusammengeklebte Rufzeichen
  (`DEDJ7PR`, `IK2ULVDEOY1CT`) werden erkannt, bekannte auch zerrissen
  (`OY 1 CT`) oder mit angeklebtem Rest (`DJ7PRRFB`) (ADR-0019, #10).
- Decodier-Log neben jeder Aufnahme (`cw_….txt`, eine Zeile je Zeichen
  `sekunde;zeichen`), um eine Stelle im Text in der WAV wiederzufinden (#10).
- Absätze im Textfenster: Leerzeile nach einer Pause > 3 s oder bei
  Tonverlust (#10).
- Aufnahme 231339 (500-Hz-Filter, QSO mit Fading und zwei Stationen) als
  Testdatum, mit Rufzeichen-Prüfung (`REAL_SPOTS`).
- Installierbares Windows-Programm: Setup-Dateien
  `CWDecoder-Setup-vX.Y.Z.exe` (Stable) und
  `CWDecoder-Beta-Setup-vX.Y.Z.exe` (Beta), parallel installierbar, mit
  Startmenü-Eintrag und Deinstallation (fragt, ob Einstellungen gelöscht
  werden sollen; Standard Nein) (ADR-0011, ADR-0012).
- Self-Update: Prüfung kurz nach dem Start (abschaltbar), „Hilfe → Nach
  Updates suchen", Update-Dialog mit Release-Notes-Link, Download mit
  Fortschritt, stille Installation und automatischem Neustart; „Später"
  lässt einen Hinweis im Hilfe-Menü stehen. Stable sieht nur Stables, Beta
  nur Betas (ADR-0013).
- `CWDecoder.exe --decode datei.wav`, `--list-devices`, `--version` in der
  installierten Version (ADR-0011).
- Release-Workflow: Tag `vX.Y.Z` bzw. `vX.Y.Z-betaN` baut Bundle und
  Installer und veröffentlicht das GitHub-Release mit Notes aus diesem
  Changelog (ADR-0014). Anleitung für lokale Builds in `docs/BUILD.md`.
- Programm-Icon (`tools/make_icon.py`).
- Testmatrix mit zufälligen Texten (`cwdecoder/testtext.py`): 10 Kategorien
  à 10 Fälle mit gestreuten Parametern und festen Seeds, darunter eine
  Kategorie mit reinem Rauschen, in der nichts ausgegeben werden darf; die
  alte Matrix bleibt per `--legacy` erhalten. CI-Untergrenze 95 %,
  Rauschen 99 % (ADR-0017, #1).
- Version und Release-Kanal in `cwdecoder/__version__.py` (0.1.0, stable);
  Fenstertitel „CW Decoder v0.1.0", im Beta-Kanal mit „BETA" (ADR-0003).
- Ablageorte in `cwdecoder/paths.py`: App-Ordner `%APPDATA%\CWDecoder`
  (Beta: `CWDecoder-Beta`), Aufnahmen in `Dokumente\CW Decoder\Aufnahmen`
  (ADR-0003).
- Diagnose-Log `<App-Ordner>\logs\cwdecoder.log` (1 MB × 5), Level per
  `CWDECODER_DEBUG=1` auf DEBUG; Start, Version, Gerät, Abtastrate und Fehler
  werden protokolliert, Audiodaten nie (ADR-0004).
- Einstellungen in `<App-Ordner>\config.json` (Gerät, feste Tonfrequenz,
  N1MM, Wipe, Aufnahme, Update-Prüfung); kaputte Datei wird beiseitegelegt
  und gemeldet, Speichern atomar (ADR-0005).
- Hover-Tooltips an allen Bedienelementen (ADR-0006).
- Fehlerdialoge mit Klartext für Soundkarte, belegten Port, fehlendes
  N1MM-Fenster und kaputte Einstellungen; unerwartete Fehler mit
  aufklappbarem Traceback (ADR-0007).
- „Hilfe → Fehler melden…": Bericht mit Version, System, Audiogerät und den
  letzten 200 Logzeilen; Vorschau, lokal speichern oder als GitHub-Issue im
  Browser öffnen — das Programm sendet nichts selbst (ADR-0008).
- Menüleiste: Datei (Aufnahmeordner öffnen, Beenden), Hilfe (Nach Updates
  suchen — Platzhalter, Log-Ordner öffnen, Fehler melden…, Über).
- Schutz gegen Doppelstart der GUI per Lockfile (ADR-0010).
- Lizenz GPL-3.0-or-later (`LICENSE`, Kopfzeile in jeder Python-Datei).
- pytest-Setup, neue Tests für Config, Logging, Pfade, Tooltips,
  Fehlerzuordnung, Fehlerbericht und Lock; CI unter Windows und Linux
  (Python 3.12).
- Projektdokumente: ADRs (`docs/adr/`), `ROADMAP.md`, dieses Changelog,
  erweiterte `CLAUDE.md` (Onboarding, Rollen, Definition of Done).

### Changed
- Decodier-Log `cw_….txt` mit dritter Spalte `sekunde;zeichen;vertrauen`
  (#18); ältere Logs haben zwei Spalten.
- Die Rufzeichen-Spalte zeigt nur so viele Knöpfe, wie in die Fensterhöhe
  passen, und rechnet bei Größenänderung neu; kein Knopf wird mehr unten
  abgeschnitten (#14).
- N1MM-Übergabe: Standard sind jetzt CW Reader (Engine) und Skimmer-Spot.
  Tippen ins Entry Window und Zwischenablage sind abschaltbare Wege
  (Standard aus) statt fester Standard; der Haken „vorher Alt+W" sitzt im
  Dialog „Übergabe…" (ADR-0022).
- Der N1MM-Block der rechten Spalte bleibt unten sichtbar, auch wenn viele
  Rufzeichen-Knöpfe da sind (#11).
- Zweiter Start holt das vorhandene Fenster nach vorn statt des Dialogs
  „läuft bereits"; lädt die erste Instanz noch, erscheint 5 s lang „CW
  Decoder startet gerade" (ADR-0020, #9).
- GUI-Aufnahmen landen nicht mehr in `testdata/` des Repos, sondern im
  Aufnahmeordner unter Dokumente; `testdata/` bleibt für Testdateien.
- Diagnose-Ausgaben der N1MM-Anbindung (Fenstertitel, Vordergrund, belegte
  Ports) gehen ins Log statt auf stderr.
- `live.open_stream()` und `live.pick_device()` werfen `AudioDeviceError`
  statt `SystemExit`; der Terminal-Decoder meldet weiterhin auf stderr.
- GUI-Texte als `_LBL_*`/`_MSG_*`/`_TT_*`-Konstanten (Vorbereitung i18n).
- Einstellungen der GUI bleiben über Neustarts erhalten; `--n1mm` gilt nur
  für den laufenden Start.
- „Hilfe → Nach Updates suchen" prüft jetzt wirklich (vorher Platzhalter).
- Die GUI legt zusätzlich zum Lockfile einen benannten Mutex an, an dem der
  Installer eine laufende Instanz erkennt (ADR-0013).
- CI: `actions/checkout` und `actions/setup-python` auf v7 (Node 24).
- Tonverfolgung: Im Lock sucht der Tracker nur ±60 Hz um die aktuelle
  Frequenz und wechselt auf eine andere Linie nur, wenn sie mindestens 3 dB
  stärker ist (neue Parameter `track_window_hz`, `switch_margin_db` in
  `TrackerConfig`).
- Tempo-Erkennung: Strich-Schwelle adaptiv zwischen den beiden Clustern
  (unabhängig von der Gewichtung des Gebers); unplausible Cluster aus
  Störimpulsen werden verworfen.
- Schwellen: Einschalten bei 65 %, Ausschalten bei 45 % des Abstands
  Rauschen/Signal (vorher 55/35 %); der Signalpegel folgt QSB während der
  Tastung mit 40 dB/s (vorher 15 dB/s).
- Namensregel präzisiert: Verboten ist nur der Projektname des
  Referenzprojekts, die Q-Gruppe QSL ist erlaubt und steht wieder in den
  Testtexten (`CLAUDE.md`, #7).
- Squelch für schmale Empfängerfilter: Der Ton muss eine schmale Linie im
  Spektrum sein (Linien-Gate im Tracker), und die Hüllkurve muss die Dynamik
  getasteten CWs haben (Dynamik-Squelch); beide Kriterien zusammen
  (ADR-0018, #8).
- Nach Tonverlust wird das Tempo neu eingemessen statt verschleppt.
- Squelch mit 60 ms Vorausschau, samplegenau: Das Ergebnis hängt nicht
  mehr von der Blockgröße ab, und das erste Zeichen nach einer Pause bleibt
  vollständig (die Tastung läuft 60 ms hinter dem Audio).
- Tempo-Schätzung entfernt Ausreißer vor der Clusterung (mit Ausnahme für
  Tempowechsel) und folgt schneller (`adapt` 0,5); Tempo-Suchbereich
  5–60 WPM statt 5–100 WPM.
- Testmatrix: elfte Kategorie „CW-Filter"; die Hälfte der Rauschfälle läuft
  durch ein schmales Empfängerfilter. Generator: `--rx-filter` bzw.
  `render(rx_filter_hz=…)`.
- Echte Aufnahmen vom Shack-PC als Testdaten (`testdata/real/`,
  `tests/test_real.py`, `run_matrix.py --real`); Regressionstest für das
  erste Zeichen nach einer langen Pause (`tests/test_erstes_zeichen.py`).
- Rollen: Entscheidungen, die DF1DS gehören, stellt die Desktop-Session im
  Chat; im Issue steht nur das Ergebnis (ADR-0016).
- Arbeitsweise: Aufträge, Rückfragen, Berichte und Reviews laufen über
  GitHub-Issues (Label `auftrag`); die Desktop-Session schreibt im Repo nur
  Issues (ADR-0016, ersetzt ADR-0001). `CLAUDE.md` verweist für die
  allgemeine Arbeitsweise auf das claude-playbook; `ROADMAP.md` hat einen
  Einstieg für neue Desktop-Sessions, Leitlinie, Testablauf und die Liste
  der offenen Issues.

### Fixed
- Skimmer-Spots kamen in N1MM nicht an, wenn dort „Automatically Logon" aus
  ist: Der Telnet-Cluster wartete auf ein Rufzeichen, das N1MM nie schickt.
  Spots gehen jetzt ab dem Verbindungsaufbau raus (#3).
- Rufzeichen-Spalte, N1MM-Haken und Scrollbalken fehlten bei
  Windows-Skalierung 125–150 % (das Textfeld verdrängte sie) (#9).
- Falsche Meldung „läuft bereits" nach einem nicht sauber beendeten Lauf,
  wenn Windows die alte PID neu vergeben hatte: Der Lock prüft jetzt
  Programm und Startzeit (ADR-0020, #9).
- Wortgrenzen bei Gebern mit weiten Zeichenabständen: Liegen Wort- und
  Zeichenpausen in einem Cluster, liegt die Wortschwelle jetzt bei 1,35 ×
  Zeichenpause statt 1,7 ×; Rufzeichen kleben seltener zusammen (#10).
- Absturz des Decoder-Threads beendete den Lauf bisher still; jetzt stoppt
  die GUI und zeigt einen Fehlerdialog.
- GUI-Rauchtest brach sporadisch mit „Tcl_AsyncDelete" ab (tk-Objekte wurden
  in einem Hintergrund-Thread abgeräumt).
- Zwei GUI-Tests scheiterten ohne tkinter mit `ModuleNotFoundError`; sie
  werden jetzt übersprungen.
- Release-Workflow brach beim Schreiben der Release-Notes auf der
  cp1252-Konsole des Windows-Runners ab (v0.1.0-beta1 ohne Release).
- Nach einem Self-Update blieb die heruntergeladene Setup-Datei (ca. 40 MB)
  in `%TEMP%` liegen; der nächste Start räumt alte `CWDecoder-Update-*.exe`
  jetzt auf (#6).
- Bei Drift und schwachem Signal sprang die Tonverfolgung auf Rauschspitzen
  und lieferte Unsinn (#2).
- Das erste Zeichen wurde bei schwachem Signal oft falsch erkannt (C → F),
  solange das Tempo noch nicht gelernt war; Elemente werden jetzt erst am
  Zeichenende eingeteilt (#5).
- Bei langen Strichen stieg der geschätzte Rauschteppich so weit, dass der
  Squelch mitten im Strich zufiel; er bleibt während eines Tons jetzt
  stehen (bei Dauerträger über 3 s steigt er wieder).
- Bei leerer Frequenz hinter einem schmalen CW-Filter gab der Decoder Müll
  aus und verschleppte danach das Tempo („TTTT" bei der nächsten Station);
  gefunden an den ersten echten Aufnahmen vom Shack-PC (#8).

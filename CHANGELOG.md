# Changelog

Alle nennenswerten Änderungen am CW Decoder stehen in dieser Datei.

Das Format folgt [Keep a Changelog](https://keepachangelog.com/de/1.1.0/),
die Versionsnummern folgen [Semantic Versioning](https://semver.org/lang/de/).
Releases entstehen durch Tags `vX.Y.Z` bzw. `vX.Y.Z-betaN` (ADR-0002).

## [Unreleased]

### Changed
- **N1MM mit zwei Entry Windows (SO2R/SO2V)** (#31): Der CW Decoder
  richtet sich nach dem Radio mit dem grünen Punkt (FocusRadioNr aus dem
  Broadcast „Radio“). Anzeige und Spot-Frequenz springen nicht mehr
  zwischen den Radios, die Anzeige zeigt die Nummer („N1MM: 7040.3 kHz CW
  R1 (…)“). „Ins Entry Window tippen“ trifft das Fenster dieses Radios
  (Handle aus dem Broadcast, sonst Titel); bisher scheiterte es bei SO2R
  mit „Entry Window nicht erkannt“, weil die Titel auf „Radio 1/2“ statt
  „VFO A/B“ enden. Alt+W geht ans selbe Fenster.
- **N1MMs CW Reader geht immer, N1MM hängt nicht mehr** (#30, ADR-0030):
  Öffnet man in N1MM den CW Reader, während der CW Decoder ohne den Weg
  „CW Reader von N1MM (Engine)“ läuft, schaltet der Decoder die Engine
  jetzt für diesen Lauf selbst ein (Port und Fenstertitel von N1MM).
  Statuszeile: „Engine für N1MMs CW Reader eingeschaltet (nur dieser
  Lauf)“. Die Haken unter **N1MM-Anbindung** und **Übergabe…** bleiben,
  wie sie sind, nichts wird gespeichert; ist die Anbindung aus, läuft nur
  die Engine. Bisher zeigte der von N1MM gestartete zweite CW Decoder
  10–13 s ein Hinweisfenster, danach hing N1MM. Jetzt gibt er dem ersten
  Bescheid und endet nach höchstens 5 s ohne Meldung. Startet N1MM den
  CW Decoder frisch, gilt dasselbe (bisher wurden dabei Anbindung und alle
  Wege für den Lauf eingeschaltet).
- Ein Haken unter **N1MM-Anbindung**/**Übergabe…** speichert nur noch sich
  selbst. Bisher schrieb jeder Klick alle Übergabewege, auch Werte, die
  nur für diesen Lauf galten (Start durch N1MM, `--n1mm`).
- **CI testet nach geänderten Dateien** (#28, ADR-0029): Reine Doku startet
  keinen Lauf, Handbuch-Doku (README, `docs/N1MM.md`, `docs/VERGLEICH.md`,
  `docs/handbuch/`) nur `tests/test_handbuch.py`, sonstiger Code die
  schnellen Tests; Änderungen am Decoder-Kern bzw. an der Oberfläche
  zusätzlich die Marker `decoder` bzw. `gui`, Änderungen an Workflows,
  Abhängigkeiten oder pytest-Konfiguration alles. Regeln in
  `tools/ci_select.py`. Von Hand (`gh workflow run ci.yml`) und vor jedem
  Tag läuft alles; der Release-Workflow baut erst nach grünem Volllauf
  unter Windows und Linux. Der Marker `slow` entfällt (jetzt `decoder`
  und `gui`). Blockgrößen-Test der echten Aufnahmen nur noch bei 160 und
  512 Samples, Vertrauens-Vergleich an 20 statt 110 Matrix-Fällen.
- **Decoder arbeitet in einem festen 10-ms-Takt** (#22, ADR-0028): Der Text
  hängt nicht mehr davon ab, in welchen Stücken die Samples kommen; die
  GUI (20 ms) und die Testmatrix (512 Samples) sehen exakt denselben Text.
  Vorher hingen 39 von 119 Mess-Fällen von der Blockgröße ab. Dazu eine
  Frequenz-Vorausschau von 60 ms (die Hüllkurve mischt mit der Frequenz,
  die der Tracker 60 ms später kennt; beim Einrasten auf eine neue Station
  bleibt das erste Element ganz), die Filterbandbreite folgt dem Tempo im
  60-ms-Takt, und in der Einmessphase zählt ein Ton unter 20 ms nicht als
  Element (verhindert, dass ein Störimpuls nach Tonverlust das Tempo auf
  60 WPM zieht). Testmatrix Seed 1000/5000/7777: 97,9/97,8/98,6 %
  (vorher 97,9/97,2/98,5 %), alte Matrix 98,4 % (vorher 98,3 %),
  Rauschen 100 %. „UR RST“ in der Aufnahme 190242 wird wieder gelesen.
  Neue Schlüssel in `DecoderConfig`: `chunk_ms`, `freq_lookahead_ms`,
  `bw_step_ms`; in `TimingConfig`: `warmup_min_mark`.
- `python tests/run_matrix.py --blocks` misst die Abhängigkeit von der
  Blockgröße (80–1024 Samples); `tests/test_blockgroesse.py` verlangt
  identischen Text.
- **Engine für N1MMs CW Reader meldet sich mit eigenem Namen** (#13): Auf
  `fldigi.name` antwortet sie „CW Decoder“, auf `fldigi.version` mit der
  eigenen Version (X.Y.Z), auf `fldigi.name_version` mit „CW Decoder X.Y.Z
  (fldigi-kompatibel)“; bisher gab sie sich als fldigi 4.2.05 aus. N1MM
  1.0.7711 akzeptiert das (Mitschnitt a/b/c in ADR-0022). Nachgebildet ist
  nur die Schnittstelle; fldigi ist ein eigenständiges Projekt und mit dem
  CW Decoder nicht verbunden (`THIRD_PARTY.md`). Log-Zeilen heißen
  `CW-Reader-Engine: …`.
- **Skimmer-Spot** unter „Übergabe…“ ist jetzt standardmäßig **aus**
  (N1MM hält nur eine Telnet-Verbindung, meist zum DX-Cluster). Wer ihn
  eingeschaltet hatte, behält die Einstellung (#24).
- Tempo-Regler und Tooltips wachsen mit der Windows-Skalierung (vorher bei
  150/200 % zu kurz bzw. zu schmal umbrochen).
- README auf eine kurze Übersicht gekürzt; Bedienung steht im Handbuch.
  In README und Doku stehen nur noch Beispiel-Rufzeichen.
- **Nochmal hören hält den Ausschnitt fest** (#25): Strg+R fasst die
  letzten Sekunden (Standard 10 s) und spielt sie. Jedes weitere Strg+R
  innerhalb der Frist nach dem Ende der Wiedergabe (Standard 5 s, auch nach
  „Stopp") spielt **denselben** Ausschnitt noch einmal, beliebig oft. Vergeht
  die Frist, verfällt er; das nächste Strg+R fasst die dann letzten
  Sekunden. Der Decoder läuft die ganze Zeit weiter. Statuszeile:
  „festgehalten 10 s – noch 4 s", Knopf: „Nochmal (festgehalten)".
  **Strg+S** speichert während des Festhaltens genau diesen Ausschnitt
  (`cw_…_festgehalten.wav` plus `.txt` mit dem Text dazu), sonst wie
  bisher die letzten 30 s.
- **Tempo-Regler statt „langsamer (0,7×)"**: Schieberegler 0,5×–1,0× neben
  dem Knopf, Anzeige des Werts daneben. Er wirkt sofort, auch mitten in
  der Wiedergabe, die Tonhöhe bleibt. Er beginnt mit dem Starttempo aus den
  Einstellungen; ein Verschieben gilt für den festgehaltenen Ausschnitt,
  mit neuem Material springt er zurück. Einstellungen von bis beta15 mit
  „langsamer" werden zu Starttempo 0,7.
- Dialog Einstellungen → „Puffer und Nochmal hören…": neu „Festhalten nach
  Ende (Sekunden)" (1–60), „Tempo beim Start (0,5–1,0)" und
  „Ausgabegerät"; der Haken „langsamer (0,7×)" entfällt. Neue Schlüssel in
  `config.json`: `replay_hold_s` (5), `replay_rate` (1.0), `output_device`
  (Name, leer = Standard); `replay_slow` wird nicht mehr gelesen.
- **Geber mit engen Zeichenabständen** werden gelesen: Die Pause, ab der
  ein Zeichen endet, passt sich dem Geber an (vorher fest 2,2 Punkte).
  Zeichen, die bisher zu `*` oder falschen Sonderzeichen verschmolzen
  (`*X` statt `4HX`, `LO?` statt `LOUD`, `TACC<AR>E` statt `TAKE CARE`),
  kommen jetzt getrennt. Ein ungültiges Symbol wird zusätzlich an seiner
  längsten Pause geteilt, wenn beide Teile gültige Zeichen sind; solche
  Zeichen erscheinen als unsicher (grau bzw. klein), weil in Störstellen
  sonst aus einem `*` plausibel aussehender Text würde (ADR-0025, #21).
- **Kurze Aussetzer** am Ende oder Anfang eines Strichs (Fading, 10–25 ms)
  erzeugen keinen zusätzlichen Punkt mehr, sobald das Tempo eingemessen
  ist (ADR-0025, #21).
- Schalter in `TimingConfig`: `char_thr_adaptive`, `char_split`,
  `glitch_filter` (alle an), `char_split_conf` (0,45), `glitch_discard` (aus); in
  `ThresholdConfig`: `carrier_needs_key` (aus, Teppich-Regel wie bisher).
- Testmatrix Seed 1000/5000/7777: 97,9/97,2/98,5 % (vorher
  97,7/96,7/98,4 %), alte Matrix 98,3 %, Rauschen 100 %.

### Added
- **Handbuch als PDF** (#24, ADR-0027): Anleitung für den Funkbetrieb in
  neun Kapiteln mit Bildern – Installation, Anschluss ans Funkgerät, Farben
  im Text, Rufzeichen, Nochmal hören, N1MM, Einstellungen, häufige Fragen.
  Hängt an jedem Release (`CW-Decoder-Handbuch-vX.Y.Z….pdf`), wird mit
  installiert (Programmordner und Startmenü) und öffnet sich über
  **Hilfe → Handbuch**.
- Werkzeuge: `tools/make_docs_images.py` (Bildschirmfotos ohne Klicks,
  reproduzierbar), `tools/build_handbook.py` (PDF mit Seitenprüfung),
  `tools/n1mm_demo_engine.py` (Beispielsignal als Engine für N1MM-Fotos).
- **Ausgabegerät für Nochmal hören** wählbar (Liste aller Ausgänge,
  „Standard" voreingestellt). Gespeichert wird der Gerätename; gefunden
  wird es per Namensteil, auch wenn Windows die Nummern ändert. Fehlt das
  Gerät (abgezogen), spielt der CW Decoder über die Standard-Ausgabe und
  sagt es einmal im Klartext („Ausgabegerät nicht gefunden"), danach in der
  Statuszeile.
- **Rufzeichen einzeln entfernen** (#25): kleines „×" rechts an jedem
  Rufzeichen-Knopf (übergibt nichts an N1MM), Rechtsklick auf den Knopf →
  „Entfernen" (neben „… übernehmen"), Knopf **„Alle löschen"** am Ende der
  Spalte (ohne Nachfrage). Die Markierung im Text bleibt anklickbar; wird
  das Rufzeichen wieder gehört, erscheint der Knopf wieder.
- **Super Check Partial:** Die Rufzeichen-Datenbank aus Contest-Logs
  (`master.scp`, supercheckpartial.com) liegt dem Programm bei. Bekannte
  Rufzeichen sind in Knopf und Text grün unterlegt, andere gelb; der
  Tooltip sagt „in Super Check Partial" bzw. „nicht in SCP" und nennt
  ähnliche bekannte Rufzeichen. Bei genau einem Vorschlag übernimmt ihn
  ein Rechtsklick auf den Knopf („ES3YJ übernehmen"); ersetzt wird nie
  automatisch (ADR-0026, #23).
- Rufzeichen mit Pausen innerhalb (`IK2J E T`) werden zusammengesetzt,
  wenn die Verkettung in SCP steht oder schon einmal ganz gehört wurde.
  Rufzeichen, die nicht in SCP stehen, erscheinen dadurch ein bis drei
  Zeichen später als Knopf. Wurde vorher schon der Teil gemeldet (`IK2J`)
  und steht er nicht in SCP, ersetzt das ganze Rufzeichen dessen Knopf
  am selben Platz.
- **Zusammengeklebte Wörter** werden per Wörterbuch getrennt
  (`TNXFERFBCALL` → `TNX·FER·FB·CALL`, `RST5995NN5NN` →
  `RST·599·5NN·5NN`). Der graue Mittelpunkt zeigt einen ergänzten, nicht
  gehörten Abstand; N1MMs CW Reader bekommt echte Leerzeichen (jedes Wort
  erst an seinem Ende). Abschaltbar unter Einstellungen; neue Schlüssel
  `segment_words` und `n1mm_engine_segmented` in `config.json`. Im
  Terminal (`live`, `decode_wav`) ebenfalls `·`, abschaltbar mit
  `--no-segment`. Der rohe Decodertext und das Decodier-Log bleiben
  unverändert.
- `CWDecoder.exe --scp RUFZEICHEN` (bekannt / ähnlich / unbekannt),
  `python -m cwdecoder.scp`; `tools/update_scp.py` lädt eine neue SCP.
- Prosign `<BK>` (`-...-.-`).
- Testdaten vom Shack-Test 27.10. (IN3TWX, IK2JET, GI5RSS, LA8IG) in
  `tests/test_real.py`; `tests/real_baseline.json` hält den Volltext aller
  Aufnahmen, `run_matrix.py --real` zeigt die Ähnlichkeit dazu.
- `cwdecoder.gen`: `--char-gap` (Zeichenabstand in Punkten) und
  `--dropouts` (Aussetzer in Strichen).
- **Letzte 30 s speichern** (Strg+S): Der Decoder hält die letzten 60 s
  Audio im Speicher. Ein Klick sichert die letzten 30 s als
  `cw_…_letzte30s.wav` im Aufnahmen-Ordner, daneben den decodierten Text
  dieses Ausschnitts als `.txt` (Zeit, Zeichen, Vertrauen) – ohne
  Daueraufnahme. So wird eine Fehldecodierung mit einem Klick zur
  Testdatei (ADR-0024, #19).
- **Nochmal hören** (Strg+R): spielt die letzten 10 s über das
  Standard-Ausgabegerät ab, der Decoder läuft weiter; zweiter Klick
  („Stopp") bricht ab. Auf Wunsch langsamer (0,7×) ohne Änderung der
  Tonhöhe.
- Menü **Einstellungen → Puffer und Nochmal hören…**: Puffergröße
  (10–300 s), Länge beim Speichern (5 s bis Puffergröße), Länge beim
  Nachhören (3–30 s), langsamer abspielen. Neue Schlüssel in `config.json`:
  `ring_seconds`, `save_last_s`, `replay_s`, `replay_slow`.
- Klartextfehler „Ausschnitt nicht gespeichert" (Aufnahmen-Ordner nicht
  beschreibbar) und „Wiedergabe nicht möglich" (kein bzw. belegtes
  Ausgabegerät); der Decoder läuft jeweils weiter.
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
- „Text löschen" steht mit den neuen Knöpfen „Letzte 30 s speichern" und
  „Nochmal hören" in einer zweiten Zeile unter der Werkzeugleiste (#19).
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
- **N1MM hing beim Start**, wenn der CW Decoder schon mit Engine lief
  (#13): N1MM schließt beim Start das Fenster „Fldigi CW Engine 1“ per
  WM_CLOSE und wartet, bis es verschwindet; der CW Decoder versteckte es
  nur. Jetzt schließt er es und legt es nach 1,5 s neu an, die Engine läuft
  weiter.
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

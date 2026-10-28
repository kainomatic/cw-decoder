# ADR-0027: Handbuch als PDF – Vorlage, Bilder per Werkzeug, Beispiel-Rufzeichen

**Status:** Accepted

## Kontext

Bisher stand die Bedienung verstreut im README (für Entwickler
geschrieben), in `docs/N1MM.md` und in den CHANGELOG-Einträgen. Funker, die
das Programm nicht kennen, brauchen eine Anleitung in einfacher Sprache mit
Bildern (#24). Entscheidungen DF1DS (28.10.2026): **gestaltetes PDF**
(größere Schrift, Screenshots wo nötig); Gestaltung und Text liefert die
Desktop-Session; in Anleitungen und Bildern **nur Beispiel-Rufzeichen**.
Skimmer-Spot wird Standard aus.

## Entscheidung

**Quelle ist eine HTML-Vorlage** (`docs/handbuch/handbuch.html`), A4 per
CSS (`@page`), eine Seite je Kapitel. Sie wird mit Chromium über Playwright
gedruckt (`tools/build_handbook.py`): erst das ganze Dokument mit Fußzeile
(„CW Decoder · Handbuch“, Seitenzahl), dann nur die Titelseite ohne
Fußzeile; pypdf setzt beides zusammen. Die Version auf der Titelseite kommt
aus der Programmversion bzw. dem Tag (Platzhalter `{{VERSION}}`,
`{{CHANNEL}}`). Warum HTML statt Markdown oder Word: Die Desktop-Session
gestaltet direkt im Format, das gedruckt wird; Chromium setzt es überall
gleich; Text und Layout liegen versioniert im Repo.

**Schriften liegen bei** (Inter, DejaVu Sans Mono, beide frei, Lizenzen in
`docs/handbuch/fonts/` und `THIRD_PARTY.md`) und werden eingebettet; das
PDF sieht auf jedem Rechner gleich aus. Playwright und pypdf sind nur
Build-Abhängigkeiten (`requirements-dev.txt`), nicht zur Laufzeit.

**Seitenprüfung im Build:** Kapitel 1–3 und 5–9 genau eine Seite,
Kapitel 4 höchstens zwei. Sonst bricht der Bau ab – eine überzählige Seite
heißt, ein Kasten oder eine Überschrift steht allein. Abhilfe: Bilder per
`max-height`, nicht Text kürzen.

**Bilder per Werkzeug** (`tools/make_docs_images.py`, nur Windows): die
echte Oberfläche mit einer Attrappe der Soundkarte und einem synthetischen
Signal (`gen.py`) mit Beispiel-Rufzeichen; die Blöcke speist das Werkzeug
selbst ein, die Statuszeile setzt es aus dem Decoderzustand – zwei Läufe
ergeben pixelgleiche Bilder. Aufnahme per `PrintWindow` (auch ohne aktive
RDP-Sitzung). Der Prozess zeichnet in der Skalierung des Rechners und
verkleinert auf 100 %; so sind Titelleiste, Menü und Inhalt einheitlich.
Nur das N1MM-Foto entsteht von Hand am echten N1MM
(`tools/n1mm_demo_engine.py`, Ablauf in `docs/handbuch/README.md`).

**Auslieferung:** Der Release-Workflow baut das PDF, hängt es als
`CW-Decoder-Handbuch-vX.Y.Z[-betaN].pdf` an das Release, und beide
Installer legen es als `CW-Decoder-Handbuch.pdf` in den Programmordner
(mit Startmenü-Eintrag). **Hilfe → Handbuch** öffnet diese Datei; fehlt
sie, das PDF am Release der laufenden Version; aus dem Quelltext das
gebaute `dist/…pdf`, sonst die HTML-Vorlage (`cwdecoder/manual.py`).

**Nur Beispiel-Rufzeichen** in Handbuch, README, `docs/*.md` und Bildern
(DF1DS, `…ABC`); echte Rufzeichen nur in Testdaten, Tests und ADR-Befunden.
Alte Fotos mit echten Rufzeichen sind gelöscht; `docs/VERGLEICH.md` nennt
Platzhalter.

**Pflege:** Jede sichtbare Änderung passt die Vorlage an, lässt beide
Werkzeuge laufen und committet die Bilder (CLAUDE.md, Definition of Done).
`tests/test_handbuch.py` prüft: keine echten Rufzeichen; jeder im Handbuch
zitierte Bedientext (`<span class="ui">`) existiert als `_LBL_`-Konstante;
jeder Config-Schlüssel hat eine Beschreibung (`config.DESCRIPTIONS`);
Bilder und Schriften der Vorlage sind vorhanden.

## Konsequenzen

- Ein Funker bekommt eine Anleitung, die zur installierten Version passt.
- Oberflächenänderungen kosten einen Werkzeuglauf; Bilder veralten nicht
  unbemerkt, Bedientexte werden vom Test bewacht.
- Der Release-Lauf lädt Chromium (~120 MB) und dauert etwas länger.
- Das N1MM-Foto bleibt Handarbeit.
- Englisch kommt mit der zweisprachigen Oberfläche (#17); dieselben Bilder
  können dann eine zweite Vorlage nutzen.

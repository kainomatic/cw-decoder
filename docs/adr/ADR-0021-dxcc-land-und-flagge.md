# ADR-0021: Land und Flagge zum Rufzeichen aus cty.dat, Flaggen als PNG

**Status:** Accepted

## Kontext

In den Rufzeichen-Knöpfen der rechten Spalte soll neben dem Rufzeichen
stehen, aus welchem Land die Station funkt (#11). DF1DS hat entschieden:
Flagge als Bild und dahinter der **Landesname**, nicht der Präfix. Den
Präfix sieht man am Rufzeichen selbst; was fehlt, ist das Land, wenn man
den Präfix nicht im Kopf hat.

Im Amateurfunk legt die DXCC-Liste fest, welcher Präfix zu welchem „Land"
(Entität) gehört. Viele Entitäten sind keine Staaten (Inseln, Antarktis,
Sonderfälle wie der Malteserorden oder die ITU in Genf).

Flaggen-Emoji (🇩🇪, zwei Regional-Indicator-Zeichen) zeichnet Windows nicht
als Flagge, sondern als „DE" in Kästchen, auch nicht in tkinter.

## Entscheidung

1. **Datenquelle `cty.dat`** (AD1C, „Contest Country Files",
   country-files.com), mitgeliefert als `cwdecoder/data/cty.dat` zusammen mit
   dem Lizenztext (`cty_copyright.txt`, MIT-artig). Das ist die übliche
   Datei der Logprogramme (N1MM nutzt sie auch). Die Kopfzeile von
   `cty_copyright.txt` nennt Nummer und Datum; `dxcc.cty_version()` liest sie
   (`CTY-3633 (2026-10-23)`). Die `cty.dat` selbst hat keinen Kopf und keine
   Kommentare, das Pseudorufzeichen `VERSION` verweist nur auf eine Entität.
2. **Zuordnung** in `cwdecoder/dxcc.py`: Rufzeichen groß schreiben; exakte
   Rufzeichen (`=…`) vor Präfixen; längster passender Präfix gewinnt;
   Zonen-Überschreibungen `(CQ)` und `[ITU]` gelten. Zusätze:
   `/P`, `/M`, `/AM`, `/QRP` u. ä. werden abgetrennt, `/MM` ergibt kein Land,
   `/1…/9` ersetzt die Ziffer des Rufzeichens (`EA6SX/5` → Spanien), bei zwei
   Teilen (`DL/OK1XYZ`, `OK1XYZ/DL`) ist der kürzere der Standort. Laden
   träge beim ersten Aufruf, gecacht und thread-sicher; die GUI lädt vorab in
   einem Hintergrund-Thread. Ladezeit rund 30 ms, steht im Log.
   `gui_start` importiert `dxcc` nicht (ADR-0020, Test).
3. **Tabelle `cwdecoder/data/dxcc_table.json`**: Hauptpräfix der Entität →
   `{"name": deutscher Kurzname, "iso": ISO-3166-Code der Flagge | null}`.
   Jede Entität aus `cty.dat` hat einen Eintrag (Test). Kurznamen höchstens
   16 Zeichen; im Knopf stehen 14, länger wird mit „…" gekürzt, der volle
   Name steht im Tooltip. `iso` nur, wo eine passende Staats- oder
   Gebietsflagge existiert (Hawaii, Alaska → `us`, Sardinien → `it`,
   England/Schottland/Wales mit eigener Flagge); `null` für ITU, UNO,
   Malteserorden, Antarktis, Süd-Shetland/-Orkney, umstrittene Gebiete.
   Lieber keine Flagge als eine falsche. Fehlt die Tabelle, gibt es den
   englischen Namen aus `cty.dat` und keine Flagge.
4. **Flaggen als PNG** in `cwdecoder/data/flags/<iso>.png`, 24×16 px mit
   1 px dunklem Rand, seitenrichtig verkleinert. Quelle
   `hampusborgos/country-flags` (Public Domain, SVG). Das Dev-Werkzeug
   `tools/make_flags.py` rendert die SVGs einmal mit Headless-Chrome/Edge,
   Pillow verkleinert; die PNGs werden committet (rund 110 KB). Zur
   Laufzeit liest `tk.PhotoImage` sie direkt, ohne Pillow. Die Bilder
   hängen in einem Cache am `App`-Objekt, sonst räumt der GC sie weg.
5. **Knopf** aus einem Rahmen mit Labels (Rufzeichen fett, Flagge,
   Landesname) mit festen Breiten in Zeichen, damit die Spalte nicht
   springt; ein Klick auf jede Stelle übergibt das Rufzeichen. Ohne Flagge
   steht ein leeres Bild gleicher Größe da, ohne bekanntes Land nur das
   Rufzeichen. Der N1MM-Block der Spalte ist unten verankert, damit viele
   Knöpfe ihn nicht aus dem Fenster schieben.
6. **Aktualisierung vorerst manuell**: `python tools/update_cty.py` lädt die
   neueste Version (Dev-Werkzeug), danach Tests und ein Commit. Kein
   Download zur Laufzeit; ein Aktualisierer im Programm wäre ein eigenes
   Issue.
7. Herkunft und Lizenzen stehen in `THIRD_PARTY.md`. Die Daten liegen im
   Bundle unter `cwdecoder/data` (`cwdecoder.spec`); `paths.data_path()`
   findet sie in der Entwicklung und im PyInstaller-Bundle. Der
   Release-Workflow prüft die Dateien und `CWDecoder.exe --dxcc DJ7PR`.

## Konsequenzen

- Die Zuordnung ist so aktuell wie die mitgelieferte `cty.dat`. Neue
  Sonderrufzeichen erkennt sie erst nach einem Update der Datei.
- Neue Entitäten in einer neuen `cty.dat` lassen den Tabellentest scheitern,
  bis ein deutscher Name (und ggf. eine Flagge) eingetragen ist.
- Ändert sich eine Flagge, reicht `python tools/make_flags.py`.
- Das Repo wächst um rund 230 KB Daten.

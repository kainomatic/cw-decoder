# ADR-0020: Start, gehärteter Instanz-Lock, zweite Instanz holt die erste nach vorn

**Status:** Accepted

Ergänzt ADR-0010.

## Kontext

Auf dem Shack-PC erschien das Fenster nach der Erstinstallation und nach
einem Self-Update sehr spät, dazu kam der Dialog „CW Decoder läuft bereits"
(#9). Das Log zeigt drei Ursachen:

- **Langsamer Kaltstart:** Das Bundle lädt numpy, scipy und sounddevice,
  bevor überhaupt etwas zu sehen ist. Frisch installierte Dateien prüft
  zusätzlich der Virenscanner. Wer in dieser Zeit noch einmal startet, landet
  beim Lock der ersten Instanz.
- **Automatischer Start:** Nach der Installation (Haken „starten") bzw. dem
  Self-Update (`/RESTARTCWDECODER`) startet das Programm selbst. Ein
  zusätzlicher Start aus dem Startmenü ist dann die zweite Instanz.
- **Falsch-positiver Lock:** ADR-0010 prüfte nur, ob die PID aus der
  Lockdatei irgendein lebender Prozess ist. Endet der CW Decoder ohne
  Aufräumen (vom Installer beendet, Rechner aus) und Windows vergibt die PID
  neu, meldet der nächste Start fälschlich „läuft bereits".

## Entscheidung

1. **Leichter Start** (`cwdecoder/gui_start.py`, Einstieg der EXE und von
   `python -m cwdecoder.gui`). Die Reihenfolge ist:
   1. Logging.
   2. Instanz-Lock.
   3. Startfenster „CW Decoder startet …" (tkinter, ohne Rahmen, zentriert).
   4. Erst dann `cwdecoder.gui` mit numpy, scipy und sounddevice.
   5. Hauptfenster; das Startfenster schließt sich direkt davor.

   Jede Phase steht mit Zeit seit Prozessstart im Log („Startphase: …"),
   dazu die Dauer der schweren Imports. Ein Test sichert, dass
   `gui_start` selbst keine schweren Module lädt.
2. **Gehärteter Lock** (`instance_lock.py`):
   - Die Lockdatei enthält PID, Prozess-Startzeit (`GetProcessTimes`) und
     Programmname.
   - Eine andere Instanz gilt nur als laufend, wenn drei Bedingungen gelten:
     - der Prozess lebt;
     - `QueryFullProcessImageNameW` endet auf `CWDecoder.exe` (im
       Entwicklungsbetrieb `python*.exe`);
     - die Startzeit stimmt.
   - Sonst ist der Lock veraltet und wird ohne Meldung übernommen.
   - Alte Lockdateien (nur PID) werden weiter gelesen.
3. **Zweite Instanz:**
   - Sie sucht die sichtbaren Fenster des Lock-Prozesses, deren Titel mit
     „CW Decoder" beginnt. Gesucht wird per PID, nicht per Titel, damit
     Stable und Beta sich nicht gegenseitig nach vorn holen.
   - Das gefundene Fenster holt sie in den Vordergrund
     (`n1mm.bring_to_front`: direkt, dann `AttachThreadInput`, dann
     ALT-Trick) und beendet sich danach.
   - Hat die erste Instanz noch kein Fenster, zeigt die zweite 5 s lang
     „CW Decoder startet gerade, bitte einen Moment warten." und beendet sich
     dann ohne Klick. Der bisherige Dialog „läuft bereits" entfällt.
4. **Installer:** Der Haken „starten" nach der Installation und der Neustart
   nach dem Self-Update bleiben. Das README weist darauf hin, nicht
   zusätzlich aus dem Startmenü zu starten.

## Konsequenzen

- Der Nutzer sieht sofort nach dem Start etwas (Startfenster), auch wenn das
  Laden noch Sekunden dauert.
- Ein Doppelstart ist harmlos: Es gibt keinen Dialog mehr zum Wegklicken,
  das vorhandene Fenster kommt nach vorn.
- Veraltete Locks blockieren nicht mehr, auch bei neu vergebener PID.
- Windows erlaubt `SetForegroundWindow` nur eingeschränkt
  (Fokussperre). Bei einem Start aus Startmenü oder Explorer klappt es. Aus
  einer Sitzung ohne Eingabe (z. B. Hintergrund-Skript) bleibt das Fenster
  ggf. hinten; das steht im Log.
- Zwischen Startfenster und Hauptfenster gibt es eine kurze Lücke (Aufbau
  des Hauptfensters). Grund: Tk-Variablen ohne `master` hängen am ersten
  Tk-Objekt; zwei gleichzeitige Tk-Wurzeln wären fehleranfällig.

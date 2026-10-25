# ADR-0004: Diagnose-Log (cwdecoder.log)

**Status:** Accepted

## Kontext

Bisher gab es nur Ausgaben auf stderr (`print(..., file=sys.stderr)`), z. B.
die Fenstertitel von N1MM oder Fehler beim Binden der Ports. In der GUI und
später in der installierten Version (ohne Konsole) sind diese Ausgaben
unsichtbar. Für Live-Tests am Funkgerät und für Fehlerberichte (ADR-0008)
braucht es ein dauerhaftes, rotierendes Protokoll.

## Entscheidung

- `cwdecoder/logging_setup.py`: `setup_logging()` richtet den Logger
  `cwdecoder` mit einem `RotatingFileHandler` ein:
  `<App-Ordner>\logs\cwdecoder.log`, 1 MB je Datei, 5 Backups (max. ~6 MB).
- Level `INFO`; die Umgebungsvariable `CWDECODER_DEBUG=1` hebt auf `DEBUG`.
  Bewusst kein Config-Schalter: das Log muss vor dem Laden der Config laufen,
  damit auch Config-Fehler protokolliert werden.
- Idempotent: ein zweiter Aufruf fügt keinen Handler hinzu.
- Module loggen über `logging.getLogger(__name__)` (Kind-Logger von
  `cwdecoder`), `propagate=False` am Wurzel-Logger des Programms.
- `install_exception_hooks()` schreibt unbehandelte Ausnahmen aus Haupt- und
  Nebenthreads mit Traceback ins Log; die vorherigen Hooks laufen weiter.
- GUI und Terminal-Decoder rufen `setup_logging()` als Erstes auf und loggen:
  Start mit Version, Kanal, Python und Betriebssystem; gewähltes Gerät und
  Abtastrate; Start/Stop des Decoders; Aufnahmepfad; N1MM an/aus und
  Übergaben; Fehler.
- **Nie geloggt werden Audiodaten** (Samples, Blöcke, Spektren).
  Meldungen der Soundkarte (Überlauf) höchstens alle 5 s.
- Diagnose-Ausgaben der N1MM-Anbindung (Fenstertitel, Vordergrund-Strategie,
  belegte Ports) gehen ins Log statt auf stderr. Der Terminal-Decoder behält
  seine stderr-Ausgaben für den Nutzer.

## Konsequenzen

- Positiv: Probleme beim Live-Test lassen sich nachträglich nachvollziehen;
  der Fehlerbericht kann die letzten Logzeilen beilegen.
- Positiv: GUI ohne Konsole verliert keine Diagnose mehr.
- Negativ: N1MM-Diagnose ist im Terminal nicht mehr direkt sichtbar, nur im
  Log (Hilfe → Log-Ordner öffnen).

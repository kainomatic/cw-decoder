# ADR-0007: Fehlermeldungen im Klartext, Traceback nur bei Unerwartetem

**Status:** Accepted

## Kontext

Fehler in der GUI landeten bisher als Text in der Statuszeile (Soundkarte),
auf stderr (belegte Ports, N1MM-Fenster) oder gar nicht (Ausnahme im
Decoder-Thread beendete den Thread still, Ausnahmen in tk-Callbacks gingen
auf eine Konsole, die es unter der GUI nicht gibt). Wer den Decoder am
Funkgerät benutzt, braucht eine verständliche Meldung mit Handlungshinweis;
für die Fehlersuche braucht es bei Unerwartetem den Traceback.

## Entscheidung

- `cwdecoder/gui_errors.py`:
  - `classify_error(exc) -> ErrorInfo(title, message, status, expected, detail)`,
    reine Logik ohne tk, getestet.
  - `show_error(parent, title, message, detail=None)`: Dialog mit
    aufklappbarem, kopierbarem Detailbereich; blockiert nicht (die GUI läuft
    weiter), `wait=True` für Fälle vor dem Hauptfenster.
  - `report_exception(parent, exc, context)`: loggen (erwartet: WARNING,
    unerwartet: ERROR mit Traceback) und Dialog zeigen.
- Erwartete Fehler mit eigener Ausnahmeklasse und Klartext:

  | Ausnahme | Titel |
  |----------|-------|
  | `live.AudioDeviceError`, `PortAudioError` | Soundkarte nicht verfügbar |
  | `n1mm.PortInUseError`, `OSError` mit `EADDRINUSE`/WSA 10048 | Port belegt |
  | `n1mm.EntryWindowNotFoundError` | N1MM-Fenster nicht gefunden |
  | `config.ConfigError` | Einstellungen ungültig |

  Bei erwarteten Fehlern steht die technische Meldung im Detailbereich, aber
  kein Traceback. Alles andere ist „Unerwarteter Fehler" mit Traceback und dem
  Hinweis auf „Hilfe → Fehler melden…" (ADR-0008).
- Wege in den Dialog, alle im tk-Thread (ADR-0009):
  - Start mit nicht verfügbarer Soundkarte;
  - Einschalten der N1MM-Anbindung mit belegtem Port;
  - Rufzeichen-Übergabe, die N1MM auf **keinem** Weg erreicht hat (klappt der
    Rückfall über die Zwischenablage, reicht die Statuszeile);
  - kaputte Config beim Start (ADR-0005);
  - Ausnahme im Decoder-Thread: der Thread legt sie in die Queue, die GUI
    stoppt den Lauf und zeigt den Dialog;
  - Ausnahme in einem tk-Callback (`report_callback_exception`).
- Diagnose-Ausgaben, die bisher per `print(..., file=sys.stderr)` kamen, gehen
  ins Log (ADR-0004). Der Terminal-Modus (`live.py`, `decode_wav.py`) behält
  seine Ausgaben auf stderr.
- Neue erwartbare Fehlerfälle bekommen eine eigene Ausnahmeklasse und einen
  Eintrag in `classify_error`.

## Konsequenzen

- Positiv: Verständliche Meldung statt Absturz oder stillem Thread-Tod;
  Traceback bleibt für die Fehlersuche erhalten und ist kopierbar.
- Positiv: Zuordnung testbar ohne Display.
- Negativ: Ein noch nicht eingetragener erwartbarer Fehler erscheint als
  „Unerwarteter Fehler" — konservativ, aber für den Nutzer weniger hilfreich.

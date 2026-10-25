# ADR-0009: GUI-Threading — Arbeit in Threads, tk nur im Hauptthread (Queue + after)

**Status:** Accepted

## Kontext

Die GUI muss Audio dekodieren (Decoder-Thread), Soundkarten-Callbacks
(PortAudio-Thread) und N1MM-Netzwerkverkehr (UDP-/Telnet-Threads)
verarbeiten, ohne einzufrieren. tkinter ist nicht thread-sicher: Aufrufe aus
fremden Threads führen sporadisch zu Abstürzen („main thread is not in main
loop", „Tcl_AsyncDelete"). Gleichzeitig soll die Logik ohne Display testbar
bleiben (CI unter Linux).

## Entscheidung

1. **Kein tk-Aufruf aus Threads.** Hintergrund-Threads (Decoder, Audio-
   Callback, N1MM) legen Meldungen in eine `queue.Queue` (`App.msgs`). Die GUI
   holt sie in `_poll()` ab, das sich alle 60 ms per `after()` neu einplant.
   Zustand, den die GUI nur liest (z. B. `N1MMBridge.radio.freq_khz`), wird
   ebenfalls im Poll abgefragt.
2. **Meldungen tragen eine Generation.** Start und Stop erhöhen `App.gen`;
   verspätete Statusmeldungen aus einem gestoppten Lauf werden verworfen.
3. **Fehler aus Threads über die Queue** (`("error", gen, exc)`); die GUI
   stoppt den Lauf und zeigt den Dialog (ADR-0007). Ausnahmen in tk-Callbacks
   fängt `App.report_callback_exception`.
4. **Logik tk-frei halten.** Decoder-Kette, Config, Fehlerzuordnung,
   Fehlerbericht, Lock und Tooltip-Positionsrechnung sind eigene Module ohne
   tk und werden direkt getestet. Die GUI-Klasse verbindet nur.
5. **Tests mit echtem Fenster** (`tests/gui_smoke.py` über
   `tests/test_gui_smoke.py`) laufen nur, wenn ein Display vorhanden ist
   (Skip-Guard), und in einem eigenen Prozess.
6. **Aufräumen im Hauptthread:** Nach `mainloop()` wird `gc.collect()` im
   Hauptthread aufgerufen, damit tk-Objekte nicht später von einem
   Hintergrund-Thread abgeräumt werden.
7. Single-Instance-Schutz: siehe ADR-0010.

## Konsequenzen

- Positiv: Keine tk-Aufrufe aus fremden Threads, GUI bleibt bedienbar.
- Positiv: Kernlogik ohne Display testbar.
- Negativ: Anzeige hat bis zu 60 ms Verzögerung (für Text und Spektrum
  unerheblich).
- Negativ: Neue Hintergrundarbeit muss diszipliniert über die Queue laufen;
  Review-Punkt bei jeder GUI-Änderung.

# ADR-0010: Nur eine GUI-Instanz je Kanal (PID-Lockfile)

**Status:** Accepted

## Kontext

Zwei gleichzeitig laufende GUIs streiten sich um Soundkarte und die
N1MM-Ports (UDP 12060, TCP 7373) und schreiben dieselbe `config.json`.
Mit Startmenü-Verknüpfung und Self-Update (nächster Schritt) wird ein
versehentlicher Doppelstart wahrscheinlicher.

## Entscheidung

- `cwdecoder/instance_lock.py`, `InstanceLock`: Lockfile
  `<App-Ordner>\cwdecoder.lock` mit der PID des laufenden Prozesses.
  Der App-Ordner ist kanalabhängig (ADR-0003), Stable und Beta dürfen also
  gleichzeitig laufen.
- Anlegen atomar mit `O_CREAT | O_EXCL`. Existiert die Datei:
  - PID lebt → `acquire()` liefert `False`; die GUI zeigt den Hinweis
    „CW Decoder läuft bereits" und beendet sich ohne Fenster.
  - PID lebt nicht oder Inhalt unlesbar → veralteter Lock (Absturz,
    Stromausfall), wird gelöscht und neu angelegt (WARNING im Log).
- Prozessprüfung unter Windows über `OpenProcess` + `GetExitCodeProcess`
  (`STILL_ACTIVE`). **Nicht** `os.kill(pid, 0)`: Signal 0 ist unter Windows
  `CTRL_C_EVENT` und würde einen fremden Konsolenprozess unterbrechen.
  Zugriff verweigert zählt als „läuft".
- `release()` im `finally` von `gui.main()`; gelöscht wird nur ein Lock mit
  der eigenen PID.
- Nur die GUI nimmt den Lock. Der Terminal-Decoder (`live.py`) und
  `decode_wav` sind Werkzeuge für Tests und laufen ohne Lock.
- Kein benannter Mutex (bräuchte pywin32 oder mehr ctypes); kann für den
  Installer (Erkennen laufender Instanz beim Update) später ergänzt werden.

## Konsequenzen

- Positiv: Kein Doppelstart mit belegten Ports und konkurrierenden
  Config-Schreibzugriffen; nach Absturz startet das Programm ohne Eingriff.
- Negativ: PID-Wiederverwendung — läuft nach einem Absturz zufällig ein
  anderer Prozess mit derselben PID, meldet die GUI fälschlich „läuft
  bereits". Selten; Abhilfe ist das Löschen der Lockdatei (Pfad im Log).

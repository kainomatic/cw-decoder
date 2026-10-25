# ADR-0005: Einstellungen als JSON — robust laden, atomar speichern

**Status:** Accepted

## Kontext

Gerät, feste Tonfrequenz und die Haken der GUI mussten bisher bei jedem
Start neu gesetzt werden. Für den Installer und die Update-Prüfung
(nächster Schritt) braucht es eine dauerhafte Einstellungsdatei. Eine kaputte
Datei (Absturz beim Schreiben, Handbearbeitung) darf den Start nie
verhindern.

## Entscheidung

- `cwdecoder/config.py`, Datei `<App-Ordner>\config.json` (ADR-0003).
  JSON, weil es in der Standardbibliothek liegt (keine neue Abhängigkeit).
- Felder und Defaults:

  | Feld | Default | Bedeutung |
  |------|---------|-----------|
  | `update_check` | `true` | beim Start nach Updates suchen (ab Installer-Schritt) |
  | `device_name` | `null` | Name des Eingangsgeräts, `null` = Standardgerät |
  | `fixed_freq` | `null` | feste Tonfrequenz in Hz, `null` = automatisch |
  | `n1mm_enabled` | `false` | N1MM-Anbindung beim Start an |
  | `n1mm_wipe` | `true` | vor dem Tippen Alt+W |
  | `record_default` | `false` | Haken „Aufnahme" beim Start gesetzt |

- **Laden:** Fehlende Datei → Defaults. Kein gültiges JSON / kein Objekt /
  keine UTF-8-Datei → Datei wird nach `config.json.broken-<Zeitstempel>`
  umbenannt (nicht gelöscht), Defaults geladen, WARNING ins Log und eine
  Hinweisdatei `config.json.broken-notice` angelegt. Die GUI holt den Hinweis
  beim Start ab (`pop_broken_notice()`), zeigt ihn einmal an und löscht ihn —
  so erfährt der Nutzer davon auch, wenn das Umbenennen in einem anderen
  Programmteil passiert ist.
- Einzelne Werte mit falschem Typ (z. B. `"fixed_freq": "abc"`) fallen auf
  ihren Default zurück (WARNING), der Rest der Datei bleibt gültig.
- Unbekannte Schlüssel bleiben erhalten (ältere Version löscht keine
  Einstellungen einer neueren).
- Gerät wird über den **Namen** gespeichert, nicht über die Nummer: die
  Nummern von PortAudio ändern sich, wenn Geräte ein-/ausgesteckt werden.
- **Speichern:** atomar über temporäre Datei im selben Ordner, `fsync`,
  `os.replace`; kurzer Wiederholversuch bei `PermissionError`
  (Virenscanner unter Windows).
- Die GUI liest beim Start und schreibt bei jeder Änderung.
  Kommandozeilenschalter (`--n1mm`) gelten nur für den laufenden Start und
  werden nicht gespeichert.

## Konsequenzen

- Positiv: Kein Startabbruch durch kaputte Einstellungen; die kaputte Datei
  bleibt zur Analyse erhalten.
- Positiv: Kein halb geschriebenes `config.json` nach Absturz oder
  Stromausfall.
- Negativ: Kein Config-Backup-Verlauf; bei kaputter Datei sind die
  Einstellungen weg (die Datei ist klein und schnell neu eingestellt).

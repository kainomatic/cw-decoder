# ADR-0006: Hover-Tooltips als einziges Hilfe-Muster der GUI

**Status:** Accepted

## Kontext

Die Bedienelemente der GUI sind knapp beschriftet („Wipe", „Filter",
„SNR"). Wer das Programm zum ersten Mal am Funkgerät benutzt, braucht kurze
Erklärungen direkt am Element, ohne Handbuch und ohne dass die Oberfläche
mit Hilfetexten oder Fragezeichen-Symbolen zugestellt wird.

## Entscheidung

- Alle Bedienelemente und Anzeigen der GUI bekommen einen Hover-Tooltip.
  Keine Fragezeichen-Icons, keine eigenen Hilfe-Labels.
- Infrastruktur: `cwdecoder/gui_tooltip.py`,
  `attach_tooltip(widget, text, delay_ms=500)`.
  - erscheint nach 500 ms, verschwindet bei Verlassen, Klick oder Zerstören
    des Widgets;
  - randloses `Toplevel`; Fehler beim Anzeigen werden geschluckt und auf
    DEBUG geloggt — ein Tooltip darf nie einen Absturz auslösen;
  - Position: unter dem Widget ab der Mausposition; passt er dort nicht auf
    den Bildschirm, über dem Widget (verdeckt sonst das Widget und flackert);
    anschließend an den Bildschirmrand geklemmt.
  - Die Positionsrechnung (`clamp_to_screen`, `tooltip_position`) ist reine
    Logik und ohne Display getestet.
- Tooltip-Texte stehen als `_TT_*`-Konstanten im jeweiligen Fenstermodul,
  neben `_LBL_*` (Beschriftungen) und `_MSG_*` (Meldungen). Damit sind alle
  sichtbaren Texte an einer Stelle und später übersetzbar.
- Gilt für alle künftigen Fenster und Dialoge.

## Konsequenzen

- Positiv: Ein Mechanismus, einheitliches Verhalten, kein visuelles Rauschen.
- Positiv: Texte zentral, i18n-fähig.
- Negativ: Nur mit Maus erreichbar; Tastaturnutzer sehen die Hilfe nicht.
  Für ein Desktop-Werkzeug neben N1MM akzeptiert.

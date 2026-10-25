# Architecture Decision Records (ADR)

Hier stehen die Design- und Grundentscheidungen des CW Decoders: **was**
entschieden wurde und **warum**. Code zeigt das Wie; ein ADR hält den Grund
fest, damit spätere Sessions ihn nicht neu erraten müssen.

## Wann ein ADR?

Jede Entscheidung zu Architektur, Datenformat, Ablageort, Verhalten bei
Fehlern, Sicherheit/Datenschutz, Arbeitsweise oder Release-Ablauf bekommt
einen ADR — im selben Auftrag, in dem sie fällt. **Kein** ADR für Tippfehler,
Kosmetik oder einzelne Aufgaben (das sind GitHub-Issues).

## Format

```
# ADR-NNNN: Kurztitel

**Status:** Accepted | Superseded by ADR-XXXX

## Kontext
Welches Problem, welche Anforderung hat die Entscheidung ausgelöst?

## Entscheidung
Was gilt ab jetzt? Konkret: Dateien, Funktionen, Werte.

## Konsequenzen
Was folgt daraus, positiv wie negativ?
```

## Nummerierung und Lebenszyklus

- Dateiname `ADR-NNNN-kurztitel.md`, vierstellig mit führenden Nullen,
  fortlaufend. Nummern werden nie wiederverwendet.
- Neue ADRs haben den Status `Accepted`.
- Wird eine Entscheidung geändert, entsteht ein neuer ADR; der alte bekommt
  `Superseded by ADR-XXXX` und bleibt stehen. ADRs werden nie gelöscht.
- Jeder neue ADR wird unten im Index eingetragen.

**Nächste freie Nummer: ADR-0011**

## Index

| ADR | Titel |
|-----|-------|
| [ADR-0001](ADR-0001-rollenmodell.md) | Rollenmodell — Desktop entwirft, Code baut, DF1DS vermittelt |
| [ADR-0002](ADR-0002-nur-main-branch-releases-per-tag.md) | Nur der main-Branch, Releases entstehen durch Tags |
| [ADR-0003](ADR-0003-datenablage-app-ordner-und-aufnahmen.md) | Datenablage — App-Ordner je Kanal, Aufnahmen in den Dokumenten |
| [ADR-0004](ADR-0004-diagnose-logging.md) | Diagnose-Log (cwdecoder.log) |
| [ADR-0005](ADR-0005-config-robustheit.md) | Einstellungen als JSON — robust laden, atomar speichern |
| [ADR-0006](ADR-0006-hover-tooltips.md) | Hover-Tooltips als einziges Hilfe-Muster der GUI |
| [ADR-0007](ADR-0007-fehlermeldungen-im-klartext.md) | Fehlermeldungen im Klartext, Traceback nur bei Unerwartetem |
| [ADR-0008](ADR-0008-fehlerbericht.md) | Fehlerbericht auf Anfrage — Vorschau, lokal speichern, GitHub im Browser |
| [ADR-0009](ADR-0009-gui-threading-queue-und-after.md) | GUI-Threading — Arbeit in Threads, tk nur im Hauptthread (Queue + after) |
| [ADR-0010](ADR-0010-single-instance-lock.md) | Nur eine GUI-Instanz je Kanal (PID-Lockfile) |

## Abgrenzung

- **ADR** = Entscheidung, bleibt dauerhaft (Superseded statt löschen).
- **GitHub-Issue** = offene Aufgabe, wird geschlossen, wenn erledigt.
- **ROADMAP.md** = Projektstand und Reihenfolge der nächsten Schritte.

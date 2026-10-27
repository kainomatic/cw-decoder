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

**Nächste freie Nummer: ADR-0025**

## Index

| ADR | Titel |
|-----|-------|
| [ADR-0001](ADR-0001-rollenmodell.md) | Rollenmodell — Desktop entwirft, Code baut, DF1DS vermittelt (Superseded by ADR-0016) |
| [ADR-0002](ADR-0002-nur-main-branch-releases-per-tag.md) | Nur der main-Branch, Releases entstehen durch Tags |
| [ADR-0003](ADR-0003-datenablage-app-ordner-und-aufnahmen.md) | Datenablage — App-Ordner je Kanal, Aufnahmen in den Dokumenten |
| [ADR-0004](ADR-0004-diagnose-logging.md) | Diagnose-Log (cwdecoder.log) |
| [ADR-0005](ADR-0005-config-robustheit.md) | Einstellungen als JSON — robust laden, atomar speichern |
| [ADR-0006](ADR-0006-hover-tooltips.md) | Hover-Tooltips als einziges Hilfe-Muster der GUI |
| [ADR-0007](ADR-0007-fehlermeldungen-im-klartext.md) | Fehlermeldungen im Klartext, Traceback nur bei Unerwartetem |
| [ADR-0008](ADR-0008-fehlerbericht.md) | Fehlerbericht auf Anfrage — Vorschau, lokal speichern, GitHub im Browser |
| [ADR-0009](ADR-0009-gui-threading-queue-und-after.md) | GUI-Threading — Arbeit in Threads, tk nur im Hauptthread (Queue + after) |
| [ADR-0010](ADR-0010-single-instance-lock.md) | Nur eine GUI-Instanz je Kanal (PID-Lockfile) |
| [ADR-0011](ADR-0011-pyinstaller-build.md) | Build mit PyInstaller als onedir-Bundle |
| [ADR-0012](ADR-0012-inno-setup-installer-stable-beta.md) | Inno-Setup-Installer, Stable und Beta parallel installierbar |
| [ADR-0013](ADR-0013-self-update-lifecycle.md) | Self-Update — Prüfen, Herunterladen, Installieren, Neustart |
| [ADR-0014](ADR-0014-release-workflow-und-versionsregeln.md) | Release-Workflow und Versionsregeln |
| [ADR-0015](ADR-0015-kein-code-signing.md) | Kein Code-Signing, SmartScreen-Hinweis in der Doku |
| [ADR-0016](ADR-0016-rollenmodell-issues-als-auftraege.md) | Rollenmodell mit Issue-Recht der Desktop-Session, Aufträge über Issues |
| [ADR-0017](ADR-0017-testmatrix-zufallstexte-rauschkategorie.md) | Testmatrix mit zufälligen Texten und Rauschkategorie |
| [ADR-0018](ADR-0018-schmales-empfaengerfilter-linien-gate-dynamik-squelch.md) | Schmales Empfängerfilter — Linien-Gate und Dynamik-Squelch |
| [ADR-0019](ADR-0019-rufzeichen-ohne-wortgrenzen.md) | Rufzeichen ohne Wortgrenzen erkennen |
| [ADR-0020](ADR-0020-start-lock-zweitinstanz.md) | Start, gehärteter Instanz-Lock, zweite Instanz holt die erste nach vorn |
| [ADR-0021](ADR-0021-dxcc-land-und-flagge.md) | Land und Flagge zum Rufzeichen aus cty.dat, Flaggen als PNG |
| [ADR-0022](ADR-0022-n1mm-als-fldigi-kompatible-engine.md) | Anbindung an N1MM als fldigi-kompatible Engine für den CW Reader |
| [ADR-0023](ADR-0023-vertrauen-je-zeichen-graue-darstellung.md) | Vertrauen je Zeichen und graue Darstellung |
| [ADR-0024](ADR-0024-ringpuffer-letzte-sekunden-sichern-und-nachhoeren.md) | Ringpuffer – letzte Sekunden sichern und nachhören |
| [ADR-0025](ADR-0025-adaptive-zeichenschwelle-und-stoermark-filter.md) | Adaptive Zeichenschwelle und Störmark-Filter |

## Abgrenzung

- **ADR** = Entscheidung, bleibt dauerhaft (Superseded statt löschen).
- **GitHub-Issue** = offene Aufgabe, wird geschlossen, wenn erledigt.
- **ROADMAP.md** = Projektstand und Reihenfolge der nächsten Schritte.

# ADR-0015: Kein Code-Signing, SmartScreen-Hinweis in der Doku

**Status:** Accepted

## Kontext

Unsignierte Setup-Dateien aus dem Internet lösen beim ersten Start die
Windows-SmartScreen-Warnung „Der Computer wurde durch Windows geschützt –
Unbekannter Herausgeber" aus. Ein Code-Signing-Zertifikat kostet jährlich
Geld; ein normales (OV) Zertifikat beseitigt die Warnung erst nach
Reputationsaufbau, ein EV-Zertifikat sofort, braucht aber einen
Hardware-Token und eine aufwändigere CI-Anbindung.

## Entscheidung

- Kein Code-Signing, weder für Setup noch EXE.
- README beschreibt die Warnung und den Weg „Weitere Informationen →
  Trotzdem ausführen" sowie die Herkunft (nur GitHub-Releases des Repos).
- Der Quelltext ist öffentlich; jedes Release wird nachvollziehbar vom
  Workflow aus dem getaggten Commit gebaut (ADR-0014).
- Neubewertung, wenn das Programm breiter verteilt wird oder die Warnung
  Nutzer abhält; ein Signierschritt ließe sich im Workflow nach ISCC
  ergänzen.

## Konsequenzen

- Keine laufenden Kosten, keine Schlüsselverwaltung.
- Beim ersten Start jedes heruntergeladenen Setups (manuell oder per
  Self-Update) kann SmartScreen bzw. ein Virenscanner nachfragen.
- Das Self-Update kann die Echtheit nicht kryptografisch prüfen; es stützt
  sich auf HTTPS zu GitHub und die Größenprüfung (ADR-0013).

# ADR-0008: Fehlerbericht auf Anfrage — Vorschau, lokal speichern, GitHub im Browser

**Status:** Accepted

## Kontext

Für Live-Tests bei Nutzern braucht es einen einfachen Weg, Diagnosedaten
zurückzubekommen: Version, System, Audiogerät und das Log. Das Programm soll
dabei nichts selbst ins Netz senden (keine Telemetrie, kein API-Token).

## Entscheidung

- `cwdecoder/error_report.py` (reine Logik, ohne tk getestet):
  - `build_error_report(version, channel, log_path, audio)` baut den Text aus
    Version, Kanal, Windows-Version, Python-Version, Audiogerät/Abtastrate,
    einer Leerstelle „Was ist passiert?" und den **letzten 200 Logzeilen**.
  - Bereinigung (`sanitize`): Nutzerordner (`C:\Users\<Name>`) wird durch `~`
    ersetzt; Zugangsdaten in URLs (`user:pass@`) und Zeilen mit Wörtern wie
    `password`, `token`, `secret` werden entfernt. Audiodaten stehen ohnehin
    nie im Log (ADR-0004).
  - `build_issue_url(title, body)` erzeugt
    `https://github.com/kainomatic/cw-decoder/issues/new?title=…&body=…`.
    Über ~7000 Zeichen URL-Länge werden die ältesten Logzeilen weggelassen und
    ein Hinweis eingefügt; der Dialog bittet dann, den vollständigen Bericht
    lokal zu speichern und anzuhängen.
- `cwdecoder/gui_error_report.py`: Dialog „Fehler melden" mit schreibgeschützter
  Vorschau und den Knöpfen **Lokal speichern…** (Standardordner
  `Dokumente\CW Decoder`), **Auf GitHub melden** (öffnet nur den Browser),
  **Log-Ordner öffnen** und **Schließen**.
- Erreichbar über **Hilfe → Fehler melden…**; außerdem **Hilfe → Log-Ordner
  öffnen** (`os.startfile`, unter Linux `xdg-open`).
- Der Hinweis im Dialog „Unerwarteter Fehler" (ADR-0007) verweist auf diesen
  Weg.

## Konsequenzen

- Positiv: Nutzer sieht vor dem Absenden genau, was weitergegeben wird;
  das Programm braucht keinen Netzwerkzugang und keine Zugangsdaten.
- Positiv: Fehlerbericht und Aufnahmen liegen beide unter
  `Dokumente\CW Decoder` und lassen sich zusammen verschicken.
- Negativ: Für „Auf GitHub melden" ist ein GitHub-Konto nötig; ohne Konto
  bleibt „Lokal speichern" und Versand per E-Mail.
- Negativ: Lange Berichte werden im Link gekürzt.

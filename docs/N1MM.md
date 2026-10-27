# CW Decoder mit N1MM Logger+ einrichten

Anleitung für den Shack-PC. Der CW Decoder liefert seinen Text an das
Fenster **CW Reader** von N1MM. N1MM markiert die Rufzeichen dort rot, und
ein Klick setzt das Rufzeichen ins Entry Window, ohne Tippen und ohne
Fensterwechsel. Daneben gibt es Skimmer-Spots, Tippen ins Entry Window und
die Zwischenablage als wählbare Wege. Hintergrund: ADR-0022.

Getestet mit N1MM Logger+ 1.0.7711 auf dem Entwicklungsrechner (Issue #3).

## 1. CW Decoder vorbereiten

1. CW Decoder installieren (Beta: `CWDecoder-Beta-Setup-v….exe`).
   Programmpfad merken, Standard:
   - Stable: `C:\Program Files\CW Decoder\CWDecoder.exe`
   - Beta: `C:\Program Files\CW Decoder Beta\CWDecoder.exe`
2. CW Decoder starten, Audio-Eingang wählen, **Start**.
3. Rechts unten den Haken **N1MM-Anbindung** setzen. Unter **Übergabe…**
   ist **CW Reader von N1MM (Engine)** schon an (Standard). Port 7367 lassen.
   Die Statuszeile zeigt jetzt „CW Reader: wartet auf N1MM (Port 7367)".

Die Einstellungen bleiben gespeichert; der Haken muss nur einmal gesetzt
werden.

## 2. CW Reader in N1MM einrichten

1. Das Log muss auf **Mode CW** stehen. Sonst meldet N1MM „CW Readers can
   only be loaded when in CW mode". Bei einem allgemeinen Log: *File → New
   Log in Database*, Log Type wählen, unter *Mode* **CW** einstellen, OK.
2. Im Entry Window: **Window → CW Reader**. Beim ersten Mal erklärt ein
   Hinweis die drei Engines; mit OK bestätigen.
3. Im Fenster **CW Reader Settings**:
   - bei **Fldigi** den Haken **Enable** setzen,
   - **Path to Fldigi:** den Pfad zu `CWDecoder.exe` eintragen (Browse),
   - **Align Frequency** und *Treat CW As* sind egal (der Decoder sucht den
     Ton selbst),
   - **Save**.
4. N1MM startet jetzt `CWDecoder.exe`. Läuft der CW Decoder schon, kommt
   er nur nach vorn. Nach etwa 10 s erscheint der Text im CW Reader, die
   Statuszeile im CW Decoder zeigt „CW Reader: N1MM verbunden".
5. Rufzeichen im CW Reader anklicken: Es steht im Rufzeichenfeld (bzw. im
   Exchange-Feld, wenn dort der Cursor steht).

N1MM merkt sich die Einstellung. Ab jetzt reicht *Window → CW Reader*.

Zum Ablauf:
- Startet N1MM den CW Decoder (er lief noch nicht), schaltet dieser für
  diesen Lauf N1MM-Anbindung und Engine ein, auch wenn sie in den
  Einstellungen aus sind.
- Schließt man den CW Reader in N1MM, läuft der CW Decoder weiter.
- **Clear RX** im CW Reader leert nur die Anzeige in N1MM.
- N1MM blendet das (leere) Fenster „Fldigi CW Engine 1" kurz ein; der CW
  Decoder versteckt es sofort wieder.
- Die Knöpfe **AFC** und **Align** im CW Reader haben keine Wirkung; der
  Decoder folgt dem Ton selbst (Klick ins Spektrum setzt eine feste
  Tonfrequenz).

## 3. Frequenz an den CW Decoder (empfohlen)

Für Skimmer-Spots und die Anzeige rechts unten:
*Config → Configure Ports, Mode Control, Winkey, etc → Broadcast Data*:
**Radio** anhaken, Ziel `127.0.0.1:12060`. Im CW Decoder steht dann
„N1MM: 7025.0 kHz CW (…)".

Ohne Broadcast nimmt der Decoder die Frequenz, die N1MM dem CW Reader
mitteilt (nur solange der CW Reader offen ist).

## 4. Skimmer-Spots (optional, Standard an)

Ein Klick auf ein Rufzeichen im CW Decoder (Knopf rechts oder Markierung
im Text) schickt einen Spot auf der aktuellen Frequenz.

1. N1MM: **Window → Telnet**, Reiter **Clusters** → **Edit List**. In der
   leeren Zeile unten *Cluster Name* `CWDecoder`, *URL* `127.0.0.1:7373`
   eintragen, **Ok**. Unter *Selected Cluster* `CWDecoder` wählen, dann
   **Connect to CWDecoder**. „Automatically Logon" ist nicht nötig; im
   Telnet-Fenster steht danach `login:`, das ist in Ordnung.
2. Spots erscheinen als `DX de CWDEC-#: …` im Telnet-Fenster und in der
   Bandmap. Liegt der Spot auf der eigenen Frequenz, zeigt das Entry Window
   das Rufzeichen im Call-Frame; die **Leertaste** übernimmt es.

Wer keine Spots will: unter **Übergabe…** „Skimmer-Spot" abschalten.
Sonst meldet ein Klick ohne Telnet-Verbindung „Spot nicht gesendet".

## 5. Weitere Wege (optional, Standard aus)

Unter **Übergabe…** im CW Decoder:
- **ins Entry Window tippen**: Klick tippt das Rufzeichen in N1MM (holt
  N1MM dafür nach vorn), optional vorher Alt+W.
- **Zwischenablage**: Klick legt das Rufzeichen in die Zwischenablage,
  Strg+V in N1MM. Beim Tippen auch Rückfallweg, wenn N1MM nicht gefunden
  wird.

## Fehlersuche

| Meldung / Verhalten | Ursache und Abhilfe |
|---|---|
| N1MM: „The window 'Fldigi CW Engine 1' could not be found after multiple tries" | Der CW Decoder bietet die Engine nicht an. Im CW Decoder Haken **N1MM-Anbindung** setzen, unter **Übergabe…** „CW Reader von N1MM (Engine)" anhaken, CW Reader in N1MM schließen und neu öffnen. Startet N1MM den Decoder bei laufender Instanz, erklärt ein Hinweisfenster dasselbe. |
| CW Decoder: „Port für den N1MM CW Reader belegt" / „Port 7367 belegt – läuft fldigi …" | Ein anderes Programm hat Port 7367, meist fldigi als CW-Reader-Engine. fldigi beenden (bzw. in N1MM als Engine abwählen) und im CW Decoder die N1MM-Anbindung aus- und einschalten. |
| N1MM: „CW Readers can only be loaded when in CW mode" | Log bzw. Contest auf Mode CW stellen (Abschnitt 2). |
| CW Reader bleibt leer, Statuszeile „CW Reader: N1MM verbunden" | Der Decoder hört nichts: Start gedrückt? Richtiger Audio-Eingang? Erscheint Text im CW Decoder selbst? |
| CW Reader bleibt leer, Statuszeile „wartet auf N1MM" | N1MM fragt nicht ab: Pfad im CW-Reader-Setup prüfen (Fldigi, Enable), CW Reader schließen und neu öffnen. |
| „N1MM: keine Broadcasts (Port 12060)" | Broadcast Data → Radio nicht eingeschaltet (Abschnitt 3). Ohne Frequenz keine Spots, solange der CW Reader zu ist. |
| „Spot nicht gesendet" | Telnet-Fenster nicht mit 127.0.0.1:7373 verbunden oder keine Frequenz bekannt. Verbinden oder unter **Übergabe…** Spots abschalten. |
| „Port belegt" (12060 oder 7373) | Der CW Decoder läuft doppelt, oder ein anderes Programm empfängt die N1MM-Broadcasts. |

Diagnose: *Hilfe → Log-Ordner öffnen*, Datei `cwdecoder.log`. Jeder Aufruf
von N1MM an die Engine außer dem Dauerabruf steht dort
(`fldigi-Engine: …`), unbekannte Methoden einmal je Name.

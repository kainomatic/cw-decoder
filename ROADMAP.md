# CW Decoder – Stand und nächste Schritte (ROADMAP.md)

> Steuert die **Reihenfolge** der Arbeit. Lebendes Dokument: Status bei jedem
> Auftrag aktualisieren (`✅` erledigt, `🔧 IN ARBEIT`, `➡️` als Nächstes,
> `⏳` später). Entscheidungen stehen in `docs/adr/`, Aufgaben in GitHub-Issues.
> Erste Datei, die jede neue Session liest.

---

## Einstieg für eine neue Desktop-Session

> Lies `CLAUDE.md`, diese ROADMAP, `docs/adr/README.md` und die offenen Issues (`gh issue list` oder GitHub). Du bist Architekt und Reviewer: Du liest das Repo, schreibst Aufträge für Claude Code (Kopf `NEUE SESSION: ja/nein`), reviewst Berichte gegen den Code und legst Issues an. Du pushst nie. Der Stand steht in "Aktueller Stand", der Plan unter "Beschlossen, noch nicht umgesetzt".

Rechte der Desktop-Session im Repo (ADR-0016): **nur** Issues anlegen,
kommentieren und Labels setzen. Keine Commits, kein Push, keine Tags, keine
Releases, keine Datei-Änderungen. Kernlogik geht als Patch oder genaue
Anweisung in ein Issue; Claude Code spielt sie ein.

Ablauf eines Auftrags (Details: `CLAUDE.md` und
[claude-playbook](https://github.com/kainomatic/claude-playbook)):
Issue mit Label `auftrag` → DF1DS startet Claude Code mit „Bearbeite Issue
#N" → Rückfragen und Abschlussbericht als Kommentar im Issue → Review als
Kommentar darunter → bei „bestanden" schließt Claude Code das Issue mit
`Fixes #N`. Immer nur ein `auftrag`-Issue in Arbeit.

Startsatz: *„Lies das Repo kainomatic/cw-decoder, fang mit ROADMAP.md an,
und sag mir, was als Nächstes zu tun ist."*

---

## Aktueller Stand

**Ziel-Version 0.1.0, Beta-Phase.** Decoder-Kern, GUI und
Programm-Infrastruktur stehen; das Programm ist als Setup mit Self-Update
installierbar (Stable/Beta getrennt, ADR-0011 bis ADR-0015).

- Neueste Beta: [`v0.1.0-beta4`](https://github.com/kainomatic/cw-decoder/releases/tag/v0.1.0-beta4)
  (`CWDecoder-Beta-Setup-v0.1.0.exe`). Self-Update beta2 → beta4 auf dem
  Entwicklungsrechner nachgewiesen. Noch keine Stable.
- Testmatrix (`python tests/run_matrix.py`): Mittelwert **95,4 %**
  (Stand Arbeitspaket 4, unverändert gegenüber vorher).
- Laufender Auftrag: siehe Issues mit Label `auftrag`
  (`gh issue list --label auftrag`).

**Nächster Schritt:** DF1DS installiert die Beta auf dem Shack-PC und testet
mit Funkgerät und N1MM (siehe „Testablauf Installer/Beta"). Danach
Auswertung der Aufnahmen durch die Desktop-Session und Entscheidung über die
Stable `v0.1.0`.

---

## Leitlinie

Ziel ist ein guter Decoder, der den Operator unterstützt, nicht ersetzt.
Keine 99 %. Bei brauchbaren Signalen sauberer Text; bei schwachen Signalen
Rufzeichen und Rapport so weit, dass man sie mit einem zweiten Hören
bestätigen kann; bei reinem Rauschen kein Müll im Textfenster (wichtiger als
die letzten Prozent). Kein Wahrscheinlichkeits-Decoder für −5 dB, solange
DF1DS es nicht vermisst.

## Testablauf Installer/Beta

Die Beta wird auf dem Shack-PC erst installiert, nachdem Claude Code auf
seinem Rechner den Self-Update von Beta N auf Beta N+1 nachgewiesen hat
(Dialog, Download, Silent-Install, Neustart mit neuer Version, Logauszug im
Bericht). Danach laufen Testrunden über Self-Update; Aufnahmen aus
`Dokumente\CW Decoder\Aufnahmen` gehen an die Desktop-Session.

Stand: Nachweis beta2 → beta4 erbracht (Arbeitspaket 4); die Beta darf auf
den Shack-PC.

## Beschlossen, noch nicht umgesetzt

Offene Aufgaben-Issues (noch kein Auftrag, bis sie das Label `auftrag`
bekommen):

| Issue | Thema | Bereich |
|-------|-------|---------|
| [#1](https://github.com/kainomatic/cw-decoder/issues/1) | Testmatrix mit zufälligen Texten statt zwei festen Sätzen | dsp |
| [#2](https://github.com/kainomatic/cw-decoder/issues/2) | Tonverfolgung bei Drift und schwachem Signal bricht ein | dsp |
| [#3](https://github.com/kainomatic/cw-decoder/issues/3) | N1MM: direkter Weg ins Rufzeichenfeld? | n1mm |
| [#5](https://github.com/kainomatic/cw-decoder/issues/5) | Erstes Zeichen bei ~10 dB SNR oft falsch (C → F), solange das Tempo noch nicht gelernt ist | dsp |

Issues zum Decoder-Kern (`dsp`) entwirft die Desktop-Session; Claude Code
setzt um und misst die Testmatrix vorher/nachher.

---

## ✅ Arbeitspaket 1 — Decoder-Kern (Desktop-Session)

Signalgenerator, DSP-Kette (Decimator, ToneTracker, Envelope, Thresholder),
TimingDecoder, Offline-Decoder, Testmatrix. Gegen synthetische Signale
getestet.

## ✅ Arbeitspaket 2 — Live-Modus, GUI, N1MM (erste Runde unter Windows)

GUI unter Windows gestartet und per Rauchtest (`tests/gui_smoke.py`,
Fake-Soundkarte) durchgeklickt; Bugfixes bei Start/Stop, Aufnahme, Threading.
N1MM: Entry Window am Titel erkennen, Fokussperre umgehen, Zwischenablage als
Rückfallweg, belegte Ports melden.

## ✅ Arbeitspaket 3 — Programm-Infrastruktur und Projektregeln

Version/Kanal, Ablageorte, Diagnose-Log, Config, Tooltips, Fehlerdialoge,
Fehlerbericht, Single-Instance, Menüleiste, ADRs 0001–0010, pytest + CI
(Windows/Linux, Python 3.12), Lizenz GPL-3.0-or-later.

## ✅ Arbeitspaket 4 — Installer mit Self-Update

- ✅ PyInstaller-Bundle `CWDecoder.exe` mit `--decode`, `--list-devices`,
  `--version` (ADR-0011).
- ✅ Inno-Setup-Installer Stable und Beta, parallel installierbar (ADR-0012).
- ✅ Self-Update: Prüfung beim Start, „Hilfe → Nach Updates suchen",
  Dialog, Download, stille Installation, Neustart; AppMutex (ADR-0013).
- ✅ Release-Workflow über Tags, Release-Notes aus dem Changelog
  (ADR-0014); kein Code-Signing (ADR-0015).
- ✅ Erste Beta-Releases `v0.1.0-beta2` und `v0.1.0-beta4`
  (`-beta1` und `-beta3` ohne Release: Workflow-Fehler, behoben).
- ✅ Update-Nachweis auf dem Build-Rechner: installierte beta2 fand beta4,
  lud sie, installierte still und startete als beta4 neu.
- Folge-Issues: #5 (siehe „Beschlossen, noch nicht umgesetzt"); #6
  (Setup-Datei blieb in `%TEMP%`) erledigt, kommt mit der nächsten Beta.

## ➡️ Stable 0.1.0 (Freigabe DF1DS)

- Beta auf dem Shack-PC installieren, mit Funkgerät und N1MM testen.
- Danach CHANGELOG einfrieren und `v0.1.0` taggen (ADR-0014).

## ⏳ Live-Test am Funkgerät

- `sounddevice` unter Windows: welche Host-API (MME/WASAPI/DirectSound)
  liefert 8 kHz direkt? `open_stream` probiert 8000, 48000, 44100, 16000.
  Am USB-Audio des Funkgeräts und an VB-Cable prüfen, ob es sauber läuft und
  ob der Pegel passt (zu niedrig = Squelch bleibt zu, zu hoch = Clipping;
  beides am SNR in der Statuszeile erkennbar).
- Echte Aufnahmen (Aufnahmeordner, siehe Datei-Menü) sammeln, auswerten
  (`python -m cwdecoder.decode_wav datei.wav --trace`) und geeignete als
  Testdaten nach `testdata/` committen (< 5 MB je Datei).
- Schwache Signale: ab ~0 dB SNR (2,4 kHz) steigen die Fehler. Ideen, erst
  nach Absprache mit der Desktop-Session: Mehrheitsentscheid über mehrere
  Bandbreiten, weicher Decoder (Wahrscheinlichkeiten statt harter Schwellen).
- Farnsworth/gedehnte Abstände: Wortschwelle passt sich erst nach ~3
  Zeichenpausen an; die ersten Wörter werden ggf. zerhackt.

## ⏳ N1MM am echten Logger

- `EntryWindowTyper`: Kommt das Rufzeichen im Entry Window an? Ist Alt+W
  tatsächlich „Wipe"? Fenstertitel aus dem Log prüfen.
- Spot-Server (Telnet 127.0.0.1:7373) in N1MM verbinden und Bandmap-Spots
  prüfen.
- RadioInfo-Broadcasts (UDP 12060): Frequenz und Mode in der GUI.

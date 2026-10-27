# Echte Aufnahmen vom Funkgerät (Testdaten)

Mitschnitte öffentlichen Amateurfunkverkehrs, aufgenommen von DF1DS am
26.10.2026 über USB-Audio (Original 48 kHz, hier auf 8 kHz / 16 bit / mono
heruntergerechnet). Empfänger mit schmalem CW-Filter (~100 Hz, −6 dB etwa
840–920 Hz bzw. um 660 Hz). Sie dienen als Regressionsprüfung
(`tests/test_real.py`, `python tests/run_matrix.py --real`).

Auf Wunsch einer betroffenen Station wird die jeweilige Aufnahme entfernt.

| Datei | Inhalt | Erwartung |
|---|---|---|
| `cw_20261026_185919_191_8k.wav` | 0–65 s sehr unsaubere Handtaste bei 660 Hz (bewusst nicht lesbar); ab 68 s Station bei 780 Hz: `GRAZIE … 73 … GL GN ANTONIO … IK1RZD` | enthält `GRAZIE`, `ANTONIO`, `IK1RZD` |
| `cw_20261026_190242_839_8k.wav` | ES3YJ im QSO mit F4IGG: `TNX FER E CALL UR RST 559 559 … QTH NR TALLINN TALLINN … HW? <AR> F4IGG DE ES3YJ K` | enthält `TNX FER`, `UR RST`, `TALLINN`, `DE ES3YJ` |
| `cw_20261026_190445_962_8k.wav` | LY2PX ruft CQ; Gegenstation IZ4BPF (op Willy) schwach, ~10 dB über dem Filterrauschen | enthält `LY2PX LY2PX CQ CQ CQ`, `WILLY`, `Z4BPF` |
| `cw_20261026_190855_301_8k.wav` | 0–65 s leere Frequenz (nur Filterrauschen); ab 70 s ES3YJ schwach | erste 65 s höchstens 5 Zeichen; Gesamttext enthält `ES3YJ` |
| `cw_20261026_231339_217_8k.wav` | 26.10., Filter 500 Hz, 6 min: QSO OY1CT / IK2ULV / DJ7PR mit Fading und zeitweise zwei Stationen; Geber DJ7PR mit weiten Zeichenabständen (Wort-/Zeichenpause ≈ 1,4) | enthält `OY1CT`, `IK2ULV`, `DJ7PR`, `CALLED CQ`, `QRM`, `STRANGE`; Rufzeichen-Spotter findet `DJ7PR` und `OY1CT` auch in zusammengeklebten Wörtern (#10) |
| `cw_20261027_193609_542_8k.wav` | 27.10., 4,6 min: SV1QEK, dann QSO OY1CT / IN3TWX (Ton 840 Hz). IN3TWX tastet mit Zeichenabständen 2–4 Punkte und Wortabständen 4–6 Punkte (Kontinuum, Wörter kleben: `DEIN3TWX`, `GETUESUR569569BK`); vereinzelt Aussetzer innerhalb von Elementen (13–26 ms) | enthält `SV1QEK`, `OY1CT`, `IN3TWX`, `WOLF`, `BK` (#20) |
| `cw_20261027_194453_947_8k.wav` | 27.10., 2 min: IK2JET ruft CQ mit Keyer (Punkt 56 ms), gibt aber innerhalb des Rufzeichens 5,5-Punkt-Pausen (`IK2J E T`), zwischen `CQ` und `DE` nur 3 Punkte | enthält `CQ DE IK2J`; Rufzeichen `IK2JET` erst mit Super Check Partial (#17, #20) |
| `cw_20261027_194831_227_8k.wav` | 27.10., 90 s: drei Stationen auf 240 Hz – GI5RSS 840 Hz, starke Station 864 Hz (24 Hz daneben, Punkt 90 ms, Zeichenabstände nur 1,2–2,4 Punkte: sendet `VHX`/`4HX`), schwache dritte bei 630 Hz; zeitweise zwei gleichzeitig | enthält `GI5RSS`, `UR 5`, `OY1CT`; ab Zeichenschwellen-Auftrag (#20) auch `VHX` (32–38 s) |
| `cw_20261027_202035_204_8k.wav` | 27.10., 2,1 min: LA8IG (op Knut, QTH Drangedal) ruft CQ und arbeitet DL4KCA. Keyer, 25 WPM, sehr sauber – aber **praktisch ohne Wortabstände** (Zeichen- und Wortpausen beide 2,5–4 Punkte, `<BT>` als Trenner): `TNXFERFBCALL`, `RST5995NN5NN` sind so getastet | enthält `LA8IG`, `DL4KCA`, `DRANGEDAL`, `KNUT`; Wortgrenzen nur per Wörterbuch (SCP-Auftrag, #17) |

Zu den Aufnahmen vom 27.10. liegt das Decodier-Log der Beta 13 daneben
(`…_NNN.txt`, `sekunde;zeichen;vertrauen`), um die Vertrauensanzeige
gegen das Gehörte zu prüfen (#18).

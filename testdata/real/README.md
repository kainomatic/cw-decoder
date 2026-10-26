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

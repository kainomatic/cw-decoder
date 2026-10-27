# Vergleichsmessung: fldigi 4.2.03 gegen den CW Decoder

Messung vom 27.10.2026 durch die Desktop-Session mit dem Decoder-Stand
`v0.1.0-beta11`; Text aus Issue #12 übernommen. Einmalige Messung,
nicht Teil der CI.

Anlass (DF1DS): fldigi ist die übliche Engine hinter N1MMs CW-Reader-Fenster; wie schlägt es sich auf unserem Testmaterial?

## Aufbau
- fldigi 4.2.03 (Ubuntu-Paket) auf einem virtuellen Bildschirm, Audio über eine virtuelle PulseAudio-Soundkarte **in Echtzeit** (fldigi kann nur mithören, keine Datei-Schnellauswertung). Text abgeholt per XML-RPC `rx.get_data`, genau wie N1MM es tut.
- fldigi-Einstellungen: Standard (CW, Squelch aus, AFC an). **Tonhöhe wurde fldigi bei jedem Fall voreingestellt** (`modem.set_carrier` auf die bekannte Pitch), wie ein Klick ins Wasserfall – ein Vorteil für fldigi; der CW Decoder sucht den Ton selbst.
- Material 1: die Testmatrix (`tests/run_matrix.py`, 110 Fälle, Seeds 1000…, 43 min Audio), Bewertung `score_case` (Ähnlichkeit Soll/Ist, Rauschen: Strafe je ausgegebenem Zeichen).
- Material 2: die fünf echten Aufnahmen aus `testdata/real/` (14,5 min), Bewertung wie `tests/test_real.py`: Anteil der erwarteten Fragmente im Text, dazu die leere Strecke in `190855` (65 s nur Filterrauschen).
- Ein erster Durchlauf über fldigis Dateiwiedergabe wurde verworfen: sie läuft ~4 % langsamer als Echtzeit, dadurch stimmten Pitch-Einstellung und Zuordnung nicht.

## Ergebnis Testmatrix (110 Fälle)
| Kategorie | fldigi | CW Decoder |
|---|---|---|
| sauber | 95,2 % | 100 % |
| Tempo/Pitch (8–55 WPM, 300–1200 Hz) | **56,9 %** | 97,7 % |
| SNR 6–12 dB | 91,5 % | 99,0 % |
| SNR 0–6 dB | 87,7 % | 99,1 % |
| Drift | 92,7 % | 98,7 % |
| QSB | **61,5 %** | 94,8 % |
| QRM | 89,1 % | 95,6 % |
| Timing/Farnsworth | **70,1 %** | 93,1 % |
| kombiniert | 76,0 % | 98,0 % |
| CW-Filter (100–250 Hz) | 91,3 % | 98,8 % |
| Rauschen (nichts ausgeben) | 84,4 % | 100 % |
| **Mittel** | **81,5 %** | **97,7 %** |

Beobachtungen:
- fldigi verliert in fast jedem Fall die ersten Zeichen, bis das Tempo eingemessen ist (`CQ TEST OZ1HGT…` → `T - 1HGTHGT TEST`). Bei uns durch die 60-ms-Vorausschau und die Clusterung abgesichert (`test_erstes_zeichen.py`).
- Ab etwa 35 WPM liefert fldigi mit Standardeinstellungen praktisch nichts (39 WPM → `E`, 45 WPM → `I`, 50 WPM → `I`); der Tempobereich ist dort konfigurierbar, aber die Voreinstellung ist eng.
- Bei QSB und weiten Zeichenabständen zerfallen Rufzeichen (`PA8ACJ PA8ACJ PA8ACJ` → `T8ACJ PAT ACJ PA NJ`).
- Bei gleichmäßigem Rauschen ist fldigi solide (0–6 dB: 88 %).
- Reines Rauschen: in 7 von 9 Fällen gibt fldigi ein einzelnes Zeichen aus (S, L, E, I, 5 …).

## Ergebnis echte Aufnahmen (Fragmente gefunden)
| Aufnahme | fldigi | CW Decoder |
|---|---|---|
| 185919 (GRAZIE, ANTONIO, IK1RZD) | 0/3 – Rufzeichen als `I K1 R Z D` zerrissen, davor 65 s `M M OM***T OTTT…` aus der unsauberen Handtaste | 3/3 |
| 190242 (TNX FER, UR RST, TALLINN, DE ES3YJ) | 2/4 (`UR RST`, `DE ES3YJ`; `T A L L I NN`) | 2/4 (`TNX FER`, `DE ES3YJ`; `TALLINN`/`UR RST` sind bekannte Lücken) |
| 190445 (LY2PX LY2PX CQ CQ CQ, WILLY, Z4BPF) | 1/3 (`WILLY`; `DY2P X LY2PX CQ CQ CQDE`, `4 BPF`) | 3/3 |
| 190855 (ES3YJ; 65 s leere Frequenz) | 0/1 (`ES3 Y3`); **45 Zeichen Müll** in der leeren Strecke (`NEUEMME NNIWE NEOE UEETTTE * DD5BI*EIM…`) | 1/1; ≤ 5 Zeichen in der leeren Strecke |
| 231339 (OY1CT, IK2ULV, DJ7PR, CALLED CQ, QRM, STRANGE) | 4/6 (`O Y1C T`, `IK 2 ULV`, `DJ7PR` → `*J 7*`) | 6/6 |
| **Mittel** | **30 %** | **90 %** |

Das Bild deckt sich mit dem Eindruck vom Funkgerät: Das 100-Hz-Filterrauschen liest fldigi als Dauertext, und weite Zeichenabstände reißen Rufzeichen auseinander (`O Y1C T`), was für den Klick ins Rufzeichenfeld in N1MM nicht brauchbar ist.

## Einordnung
- fldigi ist nicht „grottig“, sondern ein Decoder für gleichmäßige Signale bei bekannter Tonhöhe und moderatem Tempo; dort ist es ordentlich. Es fehlen genau die drei Dinge, um die es in diesem Projekt geht: Tempo-Einmessung ohne Verlust des Anfangs, Rauschsperre gegen schmales Filterrauschen, robuste Wort-/Zeichengrenzen bei echten Gebern.
- Die Messung ist einmalig und nicht Teil der CI (Echtzeit, fremdes Programm). Skripte und Rohdaten liegen in der Desktop-Session.

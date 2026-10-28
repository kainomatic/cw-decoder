# Handbuch (Quelle des PDFs)

Das Handbuch für den Funkbetrieb wird als PDF ausgeliefert (ADR-0027):
am Release als `CW-Decoder-Handbuch-vX.Y.Z[-betaN].pdf`, im Programmordner
als `CW-Decoder-Handbuch.pdf`, im Programm unter **Hilfe → Handbuch**.

| Datei | Inhalt |
|---|---|
| `handbuch.html` | Gestaltung und Text (Vorlage der Desktop-Session); Platzhalter `{{VERSION}}`, `{{CHANNEL}}` |
| `img/*.png` | Bildschirmfotos; alle außer `n1mm-cwreader.png` erzeugt `tools/make_docs_images.py` |
| `fonts/` | Inter und DejaVu Sans Mono mit Lizenzen (`THIRD_PARTY.md`) |

## Bauen

```
pip install -r requirements-dev.txt
python -m playwright install chromium
python tools/make_docs_images.py   # Windows; nach Änderungen an der Oberfläche
python tools/build_handbook.py     # -> dist/CW-Decoder-Handbuch.pdf, mit Seitenprüfung
```

Die HTML-Datei lässt sich auch direkt im Browser ansehen (Bilder und
Schriften liegen relativ daneben).

## Regeln

- Nur Beispiel-Rufzeichen (DF1DS, DL1ABC, DR2ABC, OY1ABC …), nie echte
  fremde (`tests/test_handbuch.py`).
- Jeder Bedientext in `<span class="ui">…</span>` muss im Code als
  `_LBL_…`-Konstante existieren (Test).
- Seitenprüfung: Kapitel 1–3 und 5–9 je eine Seite, Kapitel 4 höchstens
  zwei; sonst Bilder per `max-height` nachjustieren.

## N1MM-Foto (`img/n1mm-cwreader.png`)

Entsteht am echten N1MM Logger+ auf dem Entwicklungsrechner und lässt sich
nicht automatisch wiederholen:

1. `python tools/n1mm_demo_engine.py` – CW Decoder als Engine (Port 7367) mit
   Beispielsignal `CQ TEST DE DL1ABC DL1ABC TEST DR2ABC 5NN 14 TU`.
2. In N1MM den CW Reader öffnen; die von N1MM gestartete zweite Instanz
   übergibt an die laufende.
3. Klick auf DL1ABC im CW Reader (Fensternachricht `WM_LBUTTONDOWN/UP` an
   das Textfeld genügt), CW Reader und Entry Window per `PrintWindow`
   aufnehmen und nebeneinander setzen.

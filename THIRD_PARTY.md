# Fremde Daten im CW Decoder

Der CW Decoder selbst steht unter der GPL-3.0-or-later (`LICENSE`). Er
liefert folgende Daten anderer Herkunft mit (ADR-0021):

## cty.dat (Contest Country Files, AD1C)

- Dateien: `cwdecoder/data/cty.dat`, Lizenztext
  `cwdecoder/data/cty_copyright.txt`
- Herkunft: Jim Reisert, AD1C, <https://www.country-files.com/>
  (Version siehe Kopfzeile von `cty_copyright.txt`, z. B. CTY-3633 vom
  23. Oktober 2026)
- Lizenz: MIT-artige Erlaubnis („Permission is hereby granted, free of
  charge …"), vollständiger Text in `cwdecoder/data/cty_copyright.txt`.
  Der Hinweis muss mit der Datei weitergegeben werden; er liegt deshalb
  daneben und im Programm-Bundle.
- Aktualisieren: `python tools/update_cty.py`

## Flaggen (hampusborgos/country-flags)

- Dateien: `cwdecoder/data/flags/<iso>.png` (24×16 px, mit
  `tools/make_flags.py` aus den SVGs erzeugt)
- Herkunft: <https://github.com/hampusborgos/country-flags>, Quellen laut
  Projekt Wikimedia Commons
- Lizenz: Public Domain (Flaggen sind nicht urheberrechtlich geschützt;
  das npm-Paket `svg-country-flags` führt die Lizenz „PD"). Die Nutzung von
  Hoheitszeichen kann anderen Regeln unterliegen; hier dienen sie nur zur
  Kennzeichnung des Landes.

## Deutsche Ländernamen

`cwdecoder/data/dxcc_table.json` (Kurznamen und Zuordnung Entität → Flagge)
ist eigene Arbeit des Projekts und steht unter der Lizenz des CW Decoders.

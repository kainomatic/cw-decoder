# CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
"""Morse-Tabelle und Umwandlung Punkt/Strich-Folge -> Zeichen."""

MORSE_TABLE = {
    "A": ".-", "B": "-...", "C": "-.-.", "D": "-..", "E": ".", "F": "..-.",
    "G": "--.", "H": "....", "I": "..", "J": ".---", "K": "-.-", "L": ".-..",
    "M": "--", "N": "-.", "O": "---", "P": ".--.", "Q": "--.-", "R": ".-.",
    "S": "...", "T": "-", "U": "..-", "V": "...-", "W": ".--", "X": "-..-",
    "Y": "-.--", "Z": "--..",
    "0": "-----", "1": ".----", "2": "..---", "3": "...--", "4": "....-",
    "5": ".....", "6": "-....", "7": "--...", "8": "---..", "9": "----.",
    ".": ".-.-.-", ",": "--..--", "?": "..--..", "'": ".----.", "!": "-.-.--",
    "/": "-..-.", "(": "-.--.", ")": "-.--.-", "&": ".-...", ":": "---...",
    ";": "-.-.-.", "=": "-...-", "+": ".-.-.", "-": "-....-", "_": "..--.-",
    '"': ".-..-.", "$": "...-..-", "@": ".--.-.",
    # Umlaute / Sonderzeichen
    "Ä": ".-.-", "Ö": "---.", "Ü": "..--", "ß": "...--..", "CH": "----",
    "É": "..-..", "Ñ": "--.--",
}

# Prosigns (werden in der Ausgabe als <XX> dargestellt)
PROSIGNS = {
    ".-.-.": "<AR>",
    "...-.-": "<SK>",
    "-...-": "<BT>",
    "-.--.": "<KN>",
    "........": "<HH>",   # Irrung / error
    "...-.": "<SN>",      # verstanden
    "-.-.-": "<KA>",      # Beginn
    ".-...": "<AS>",      # warten
    "-...-.-": "<BK>",    # break (BT und K ohne Pause, #20)
}

# Bei Kollisionen (z. B. .-.-. ist '+' und <AR>) gewinnt die Prosign-Darstellung,
# weil sie im Funkbetrieb die gebräuchlichere Lesart ist.
CODE_TO_CHAR = {}
for ch, code in MORSE_TABLE.items():
    CODE_TO_CHAR.setdefault(code, ch)
for code, sign in PROSIGNS.items():
    CODE_TO_CHAR[code] = sign

CHAR_TO_CODE = {ch: code for ch, code in MORSE_TABLE.items()}


def decode_symbol(code: str) -> str:
    """Punkt/Strich-Folge -> Zeichen. Unbekannt -> '*'."""
    if not code:
        return ""
    return CODE_TO_CHAR.get(code, "*")


def encode_text(text: str) -> list:
    """Text -> Liste von Morsecodes (ein Eintrag pro Zeichen, ' ' für Wortabstand).

    Prosigns können im Text als <AR>, <SK> usw. angegeben werden.
    """
    out = []
    i = 0
    text = text.upper()
    prosign_by_name = {v: k for k, v in PROSIGNS.items()}
    while i < len(text):
        c = text[i]
        if c == "<":
            j = text.find(">", i)
            if j > i:
                name = text[i:j + 1]
                if name in prosign_by_name:
                    out.append(prosign_by_name[name])
                    i = j + 1
                    continue
        if c == " ":
            out.append(" ")
        elif c in CHAR_TO_CODE:
            out.append(CHAR_TO_CODE[c])
        # unbekannte Zeichen werden übersprungen
        i += 1
    return out

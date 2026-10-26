"""Dekoder dźwięku Morse'a (WAV) - zamiennik STT dla danych demonstracyjnych.

W wersji produkcyjnej (prawdziwe nagrania mowy) ten krok zastępuje Whisper.
"""
from __future__ import annotations

import array
import io
import wave

MORSE = {
    ".-": "A", "-...": "B", "-.-.": "C", "-..": "D", ".": "E", "..-.": "F",
    "--.": "G", "....": "H", "..": "I", ".---": "J", "-.-": "K", ".-..": "L",
    "--": "M", "-.": "N", "---": "O", ".--.": "P", "--.-": "Q", ".-.": "R",
    "...": "S", "-": "T", "..-": "U", "...-": "V", ".--": "W", "-..-": "X",
    "-.--": "Y", "--..": "Z", "-----": "0", ".----": "1", "..---": "2",
    "...--": "3", "....-": "4", ".....": "5", "-....": "6", "--...": "7",
    "---..": "8", "----.": "9",
}


def decode_wav(payload: bytes) -> str:
    with wave.open(io.BytesIO(payload)) as wf:
        rate = wf.getframerate()
        data = array.array("h")
        data.frombytes(wf.readframes(wf.getnframes()))
    if not data:
        return ""
    win = max(1, int(rate * 0.01))          # okno 10 ms
    blocks = []
    for i in range(0, len(data) - win, win):
        blk = data[i:i + win]
        rms = (sum(v * v for v in blk) / len(blk)) ** 0.5
        blocks.append(rms > 2500)
    # sklej jednorodne bloki
    syms: list[tuple[bool, float]] = []
    cur, cnt = blocks[0], 1
    for b in blocks[1:]:
        if b == cur:
            cnt += 1
        else:
            syms.append((cur, cnt * 0.01))
            cur, cnt = b, 1
    syms.append((cur, cnt * 0.01))
    unit = min((d for on, d in syms if on), default=0.06)
    text, buf = "", ""
    for on, dur in syms:
        if on:
            buf += "." if dur < unit * 2 else "-"
        else:
            if dur < unit * 2:      # przerwa wewnątrz znaku
                continue
            if buf:
                text += MORSE.get(buf, "?")
                buf = ""
            if dur > unit * 5:      # przerwa między wyrazami
                text += " "
    if buf:
        text += MORSE.get(buf, "?")
    return " ".join(text.split())

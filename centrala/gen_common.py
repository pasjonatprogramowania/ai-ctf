"""Wspólne narzędzia generatora danych CTF.

Wszystko na bibliotece standardowej + Pillow (obrazy). Zero zależności sieciowych.
Zawiera:
  * deterministyczny RNG per zespół,
  * writer archiwów ZIP z szyfrowaniem ZipCrypto (Python umie je tylko czytać),
  * syntezę obrazów PNG z tekstem (czytelnych dla mini-OCR z solutions/),
  * syntezę plików WAV z tekstem kodowanym alfabetem Morse'a,
  * prosty writer ZIP bez szyfrowania.
"""
from __future__ import annotations

import hashlib
import io
import math
import os
import random
import struct
import wave
import zipfile
import zlib

try:
    from PIL import Image, ImageDraw, ImageFont
    HAVE_PIL = True
except Exception:  # pragma: no cover
    HAVE_PIL = False

# --------------------------------------------------------------------------
# RNG
# --------------------------------------------------------------------------

def rng_for(apikey: str, task: str, salt: str = "") -> random.Random:
    """Deterministyczny generator: ten sam zespół + zadanie = te same dane."""
    h = hashlib.sha256(f"{apikey}|{task}|{salt}".encode("utf-8")).digest()
    return random.Random(int.from_bytes(h[:16], "big"))


def team_dir_name(apikey: str) -> str:
    return hashlib.sha1(("ctf|" + apikey).encode("utf-8")).hexdigest()[:16]


# --------------------------------------------------------------------------
# ZipCrypto (PKWARE traditional) - zapis
# --------------------------------------------------------------------------

_CRCTAB = []
for _n in range(256):
    _c = _n
    for _ in range(8):
        _c = (_c >> 1) ^ 0xEDB88320 if _c & 1 else _c >> 1
    _CRCTAB.append(_c)


def _crc32_byte(crc: int, byte: int) -> int:
    return (crc >> 8) ^ _CRCTAB[(crc ^ byte) & 0xFF]


class _ZipCrypto:
    def __init__(self, password: bytes):
        self.k = [0x12345678, 0x23456789, 0x34567890]
        for b in password:
            self.update(b)

    def update(self, b: int) -> None:
        k = self.k
        k[0] = _crc32_byte(k[0], b)
        k[1] = (k[1] + (k[0] & 0xFF)) & 0xFFFFFFFF
        k[1] = (k[1] * 134775813 + 1) & 0xFFFFFFFF
        k[2] = _crc32_byte(k[2], (k[1] >> 24) & 0xFF)

    def stream_byte(self) -> int:
        t = (self.k[2] | 2) & 0xFFFF
        return ((t * (t ^ 1)) >> 8) & 0xFF

    def encrypt(self, data: bytes) -> bytes:
        out = bytearray(len(data))
        for i, b in enumerate(data):
            out[i] = b ^ self.stream_byte()
            self.update(b)
        return bytes(out)


def write_encrypted_zip(path: str, files: dict[str, bytes], password: str,
                        date_time=(2024, 11, 12, 9, 30, 0)) -> None:
    """Tworzy ZIP z szyfrowaniem ZipCrypto (kompatybilny z zipfile + pwd=...)."""
    pwd = password.encode("utf-8")
    dos_time = (date_time[3] << 11) | (date_time[4] << 5) | (date_time[5] // 2)
    dos_date = ((date_time[0] - 1980) << 9) | (date_time[1] << 5) | date_time[2]
    local_parts, central_parts = [], []
    offset = 0
    for name, data in files.items():
        nb = name.encode("utf-8")
        crc = zlib.crc32(data) & 0xFFFFFFFF
        comp = zlib.compressobj(9, zlib.DEFLATED, -15)
        cdata = comp.compress(data) + comp.flush()
        zc = _ZipCrypto(pwd)
        header = bytearray(os.urandom(11)) + bytes([(crc >> 24) & 0xFF])
        blob = zc.encrypt(bytes(header)) + zc.encrypt(cdata)
        local = struct.pack("<IHHHHHIIIHH", 0x04034B50, 20, 0x0001, 8,
                            dos_time, dos_date, crc, len(blob), len(data),
                            len(nb), 0) + nb + blob
        central = struct.pack("<IHHHHHHIIIHHHHHII", 0x02014B50, 20, 20, 0x0001, 8,
                              dos_time, dos_date, crc, len(blob), len(data),
                              len(nb), 0, 0, 0, 0, 0, offset) + nb
        local_parts.append(local)
        central_parts.append(central)
        offset += len(local)
    cd = b"".join(central_parts)
    eocd = struct.pack("<IHHHHIIH", 0x06054B50, 0, 0, len(files), len(files),
                       len(cd), offset, 0)
    with open(path, "wb") as fh:
        fh.write(b"".join(local_parts) + cd + eocd)


def write_zip(path: str, files: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in files.items():
            zf.writestr(name, data)


def zip_bytes(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return buf.getvalue()


# --------------------------------------------------------------------------
# Obrazy PNG z tekstem (czytelne dla mini-OCR)
# --------------------------------------------------------------------------

FONT = None
FONT_SIZE = 16
if HAVE_PIL:
    try:
        from PIL import ImageFont as _IF
        FONT = _IF.load_default(size=FONT_SIZE)
    except Exception:  # pragma: no cover
        FONT = None

CHARSET = ("ABCDEFGHIJKLMNOPQRSTUVWXYZ"
           "abcdefghijklmnopqrstuvwxyz"
           "0123456789.,:;/-_#()[]%")

CELL = 12  # szerokość komórki znaku w skanach (render monospace dla wiarygodnego OCR)


CELL = 12  # szerokość komórki znaku w skanach (render monospace dla wiarygodnego OCR)


def text_image(path: str, lines: list[str], scale: int = 1,
               title: str | None = None) -> None:
    """Rysuje tekst czcionką Pillow (16 px) w siatce monospace.

    Renderowanie monospace (jeden znak na komórkę) odzwierciedla skan/formularz
    i pozwala niezawodnie rozpoznać treść offline (patrz solutions/tools/minocr.py).
    """
    if not HAVE_PIL or FONT is None:
        raise RuntimeError("Pillow niedostępny - nie mogę wygenerować obrazu")
    pad, lh = 10, 24
    all_lines = ([title] if title else []) + list(lines)
    width = max(len(s) for s in all_lines) * CELL + 2 * pad
    height = lh * len(all_lines) + 2 * pad
    img = Image.new("L", (max(width, 90), max(height, 50)), 255)
    d = ImageDraw.Draw(img)
    y = pad
    if title:
        for i, ch in enumerate(title):
            d.text((pad + i * CELL, y), ch, fill=0, font=FONT)
        y += lh
        d.line([(pad, y - 6), (img.width - pad, y - 6)], fill=205)
    for s in lines:
        for i, ch in enumerate(s):
            if ch != " ":
                d.text((pad + i * CELL, y), ch, fill=0, font=FONT)
        y += lh
    d.rectangle([0, 0, img.width - 1, img.height - 1], outline=215)
    if scale != 1:
        img = img.resize((img.width * scale, img.height * scale), Image.NEAREST)
    img.save(path, format="PNG")


def render_text_strip(text: str) -> "Image.Image":
    """Pomocnicze dla solvera: obrazek 1-linijkowy bez skalowania."""
    w = max(1, len(text) * 7 + 4)
    img = Image.new("L", (w, 16), 255)
    ImageDraw.Draw(img).text((2, 2), text, fill=0, font=FONT)
    return img


# --------------------------------------------------------------------------
# Audio: Morse w WAV
# --------------------------------------------------------------------------

MORSE = {
    "A": ".-", "B": "-...", "C": "-.-.", "D": "-..", "E": ".", "F": "..-.",
    "G": "--.", "H": "....", "I": "..", "J": ".---", "K": "-.-", "L": ".-..",
    "M": "--", "N": "-.", "O": "---", "P": ".--.", "Q": "--.-", "R": ".-.",
    "S": "...", "T": "-", "U": "..-", "V": "...-", "W": ".--", "X": "-..-",
    "Y": "-.--", "Z": "--..",
    "0": "-----", "1": ".----", "2": "..---", "3": "...--", "4": "....-",
    "5": ".....", "6": "-....", "7": "--...", "8": "---..", "9": "----.",
}


def ascii_only(text: str) -> str:
    mp = str.maketrans("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ", "acelnoszzACELNOSZZ")
    return text.translate(mp)


def write_morse_wav(path: str, text: str, rate: int = 8000,
                    freq: int = 700, dot_ms: int = 60) -> None:
    """Zapisuje tekst jako dźwięk Morse'a (do dekodowania bez modeli STT)."""
    text = ascii_only(text).upper()
    dot = int(rate * dot_ms / 1000)
    dash = dot * 3
    gap_intra = dot
    gap_char = dot * 3
    gap_word = dot * 7

    def tone(n: int) -> list[int]:
        return [int(12000 * math.sin(2 * math.pi * freq * i / rate)) for i in range(n)]

    def silence(n: int) -> list[int]:
        return [0] * n

    samples: list[int] = []
    for w_i, word in enumerate(text.split(" ")):
        if w_i:
            samples += silence(gap_word)
        for c_i, ch in enumerate(word):
            code = MORSE.get(ch)
            if not code:
                continue
            if c_i:
                samples += silence(gap_char)
            for s_i, sym in enumerate(code):
                if s_i:
                    samples += silence(gap_intra)
                samples += tone(dash if sym == "-" else dot)
    samples += silence(dot * 3)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(struct.pack("<%dh" % len(samples), *samples))


def seconds_to_hms(sec: float) -> str:
    return "%02d:%02d" % (int(sec) // 60, int(sec) % 60)

"""Z3 KATEGORIE - multimodalny audyt (tekst + audio + skan).

Pipeline:
  1. pobierz audyt.zip i manifest.json,
  2. dla .txt - czytaj tekst; dla .wav - dekoduj Morse'a; dla .png - mini-OCR,
  3. zaklasyfikuj na people / hardware (oprogramowanie i fakty pomijamy),
  4. wyślij słownik z listami plików.

W wersji produkcyjnej: Whisper (audio) + Tesseract/VLM (obrazy) + LLM (decyzja).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
from tools import minocr, morse

LUDZIE = ("osob", "osób", "czlowiek", "człowiek", "ludzi", "slady obecnosci", "ślad",
          "latark", "plecak", "zatrzymano", "przepustk", "kamera zarejestrowala",
          "kanal wentylacyjny", "kanał wentylacyjny", "slady obuwia", "ślad obuwia")
HARDWARE = ("lozysk", "łożysk", "czujnik", "pomp", "panel", "napraw", "wymieniono",
            "uszczelniono", "hydrauliczn", "agregat", "zlacz", "złącz", "sprzetow", "sprzętow")
SOFT = ("aktualizacj", "oprogramowan", "modul ai", "moduł ai", "plc", "restart", "softwar",
        "monitoringu -", "wersji")


def classify(text: str) -> str | None:
    low = text.lower()
    if any(s in low for s in SOFT):
        return None
    if any(h in low for h in HARDWARE):
        return "hardware"
    if any(l in low for l in LUDZIE):
        return "people"
    return None


def main() -> None:
    arch = common.unzip(common.data("kategorie", "audyt.zip"))
    print(f"[*] plików w paczce: {len(arch)}")
    people, hardware, pominiete = [], [], []
    for name, blob in sorted(arch.items()):
        if name.startswith("fakty/") or name.endswith("manifest.json") or name == "ZADANIE.md":
            continue
        if name.endswith(".txt"):
            text = blob.decode("utf-8", "replace")
        elif name.endswith(".wav"):
            text = morse.decode_wav(blob)
        elif name.endswith(".png"):
            text = " ".join(minocr.decode_image(blob))
        else:
            continue
        kat = classify(text)
        print(f"    {name:35} -> {kat or 'pomiń':8} | {text[:60]!r}")
        if kat == "people":
            people.append(name)
        elif kat == "hardware":
            hardware.append(name)
        else:
            pominiete.append(name)
    print(f"[*] people={len(people)} hardware={len(hardware)} pominięte={len(pominiete)}")
    common.report("kategorie", {"people": sorted(people), "hardware": sorted(hardware)})


if __name__ == "__main__":
    main()

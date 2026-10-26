"""Z4 KALIBRACJA - naprawa dużego pliku w oknie kontekstu.

Pipeline:
  1. pobierz kalibracja.json (duży plik) oraz slownik.json,
  2. przetwarzaj partiami (chunking) - nie wrzucaj całości do modelu,
  3. działania arytmetyczne policz kodem, pytania otwarte uzupełnij ze słownika,
  4. wyślij checkpoint z liczbą błędnych wyników, a potem cały poprawiony obiekt.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common

BATCH = 500
OP = re.compile(r"^(-?\d+)\s*([+\-*])\s*(-?\d+)$")


def policz(q: str) -> int | None:
    m = OP.match(q.strip())
    if not m:
        return None
    a, op, b = int(m.group(1)), m.group(2), int(m.group(3))
    return {"+": a + b, "-": a - b, "*": a * b}[op]


def main() -> None:
    raw = common.data("kalibracja", "kalibracja.json").decode("utf-8")
    doc = json.loads(raw)
    records = doc["test-data"]
    slownik = {e["q"]: e["a"] for e in json.loads(common.data("kalibracja", "slownik.json"))}
    print(f"[*] rekordów: {len(records)}, rozmiar pliku: {len(raw)//1024} KB")

    fixed, bledne = [], 0
    for start in range(0, len(records), BATCH):          # chunking: partiami
        for rec in records[start:start + BATCH]:
            if "test" in rec:
                q = rec["test"]["q"]
                fixed.append({"test": {"q": q, "a": slownik.get(q, rec["test"]["a"])}})
            else:
                q = rec["question"]
                nowa = policz(q)
                if nowa is None:
                    fixed.append(dict(rec))
                    continue
                if nowa != rec["answer"]:
                    bledne += 1
                fixed.append({"question": q, "answer": nowa})
        print(f"    przetworzono {min(start + BATCH, len(records))}/{len(records)}")

    print(f"[*] błędnych wyników działań: {bledne}")
    common.report("kalibracja", {"checkpoint": "math", "value": bledne})

    answer = {"apikey": doc["apikey"], "description": doc["description"], "test-data": fixed}
    common.report("kalibracja", answer)


if __name__ == "__main__":
    main()

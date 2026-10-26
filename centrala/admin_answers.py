"""Narzędzie ORGANIZATORA: wypisuje poprawne odpowiedzi dla danego klucza API.

    python admin_answers.py                 # klucz z .apikey
    python admin_answers.py --key XXXX-....

Odpowiedzi są deterministyczne (seed = apikey), więc ten sam klucz zawsze daje
ten sam zestaw danych i te same rozwiązania. Nie udostępniaj tego kodu uczestnikom.
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import datagen
import tasks

HERE = os.path.dirname(os.path.abspath(__file__))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--key")
    args = ap.parse_args()
    key = args.key or open(os.path.join(HERE, ".apikey"), encoding="utf-8").read().strip()

    print(f"KLUCZ: {key}\n" + "=" * 60)
    k1 = datagen.answer_key("wektory", key)
    print(f"Z1 wektory     : data kradzieży = {k1['data']}   (hasło ZIP = {k1['haslo']}, "
          f"pułapka = {k1['decoy']})")
    k2 = datagen.answer_key("hybryda", key)
    print(f"Z2 hybryda     : dc_ids = {k2['dc_ids']}   (checkpoint: {k2['manager']})")
    k3 = datagen.answer_key("kategorie", key)
    print(f"Z3 kategorie   : people({len(k3['people'])}) = {k3['people']}")
    print(f"                 hardware({len(k3['hardware'])}) = {k3['hardware']}")
    k4 = datagen.answer_key("kalibracja", key)
    print(f"Z4 kalibracja  : checkpoint math = {k4['math_wrong']}, rekordów = {k4['records']}")
    print(f"                 (poprawny plik ma {sum(1 for r in k4['fixed'] if 'question' in r)} "
          f"rekordów działań + {sum(1 for r in k4['fixed'] if 'test' in r)} pytań otwartych)")
    k5 = datagen.answer_key("research", key)
    ids = [i for i, lab in enumerate(k5["labels"], 1) if lab == 1]
    print(f"Z5 research    : poprawnych ID = {len(ids)} z 400, np. {ids[:12]} ...")
    k6 = datagen.answer_key("serce", key)
    for q in k6["questions"]:
        print(f"Z6 serce       : pytanie -> oczekiwana odpowiedź: {q['a']!r}  ({q['q'][:60]})")
    print("\nFLAGI (przyznawane po poprawnym rozwiązaniu):")
    for t in tasks.TASK_ORDER:
        print(f"  {t:12} {tasks.flag_for(key, t)}  ({tasks.TASK_DEFS[t]['points']} pkt)")


if __name__ == "__main__":
    main()

"""Z1 WEKTORY - RAG na archiwum fabryki.

Pipeline:
  1. pobierz archiwum_fabryki.zip,
  2. odczytaj haslo.txt i rozpakuj zaszyfrowane testy_broni.zip (checkpoint),
  3. zbuduj indeks wektorowy raportow (chunking + wektory + metadane),
  4. zapytaj o kradziez prototypu, odfiltruj falszywe alarmy,
  5. wyslij date raportu.

W wersji produkcyjnej kroki 3-4 wykonuje się na embeddingach (OpenAI) i Qdrant.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
from tools import minivec

SYNONIMY = {"kradziez": ["brak", "zniknal", "skradziono", "zaginiony", "utrata"],
            "prototyp": ["egzemplarz", "prototypowy"]}
NEGACJE = ("fałszywy alarm", "falszywy alarm", "nie potwierdz", "sprawę zamknięto",
           "sprawa zamknieta", "okazało się", "okazalo sie")


def main() -> None:
    done = common.timer("pobieram archiwum_fabryki.zip")
    arch = common.unzip(common.data("wektory", "archiwum_fabryki.zip"))
    done()
    print(f"    plików w archiwum: {len(arch)}")

    haslo_txt = arch.get("haslo.txt", b"").decode("utf-8", "replace")
    haslo = (re.search(r"(\d{4,8})", haslo_txt) or [None]) and re.search(r"(\d{4,8})", haslo_txt).group(1)
    print(f"    hasło z haslo.txt: {haslo}")
    common.report("wektory", {"checkpoint": "unzip", "value": haslo})

    if "testy_broni.zip" in arch:
        inner = common.unzip_encrypted(arch["testy_broni.zip"], haslo)
        print(f"    raportów w testy_broni.zip: {len(inner)}")

    index = minivec.Index()
    for name, blob in arch.items():
        if not (name.endswith(".txt") or name.endswith(".md")) or name == "haslo.txt":
            continue
        text = blob.decode("utf-8", "replace")
        for i, part in enumerate(minivec.chunks(text)):
            index.add(part, plik=name, data=minivec.extract_date(text), chunk=i)
    index.build()
    print(f"    wektorów w bazie: {len(index.docs)} (wymiar {minivec.DIM})")

    hits = index.search("W raporcie z którego dnia znajduje się wzmianka o kradzieży prototypu broni?",
                        expand=SYNONIMY, limit=len(index.docs))
    print("    top-3 trafienia semantyczne:")
    for score, doc in hits[:3]:
        print(f"      {score:.3f} {doc['plik']} data={doc['data']}")

    # wyszukiwanie hybrydowe: filtr leksykalny + ranking semantyczny
    KRADZIEZ = ("brak egzemplarza", "zniknął", "zniknal", "skradziono", "skradzion",
                "kradzieży", "kradziez", "utracono", "zaginął", "zaginiony")
    kandydaci = []
    for score, doc in hits:
        low = doc["text"].lower()
        if any(neg in low for neg in NEGACJE):
            continue
        if "protot" in low and any(k in low for k in KRADZIEZ):
            kandydaci.append((score, doc))
    print(f"    kandydaci po filtrze leksykalnym: {[d['plik'] for _s, d in kandydaci]}")
    wybor = kandydaci[0][1] if kandydaci else hits[0][1]
    if wybor is None:
        wybor = hits[0][1]
    data = wybor["data"] or minivec.extract_date(wybor["text"])
    print(f"    wybrany raport: {wybor['plik']} -> {data}")
    common.report("wektory", data)


if __name__ == "__main__":
    main()

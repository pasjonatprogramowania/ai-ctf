"""Z2 HYBRYDA - notatki operacyjne + baza SQL przez /apidb.

Pipeline:
  1. pobierz notatki.zip (wyszukiwanie),
  2. poznaj schemat bazy przez show tables / show create table,
  3. wybierz kandydatów: aktywne DC + nieaktywny menedżer (SQL),
  4. sprawdź, czy kryptonim DC pojawia się w notatce o incydencie (wyszukiwanie),
  5. wyślij listę dc_id (oraz checkpoint z menedżerem o najdłuższym urlopie).
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common

AWARIE = ("padl", "padł", "wyciek", "przekrocz", "nieautoryzowan", "uszkodzen",
          "awaryjn", "przepalen", "bez powodu", "usterk", "zatrzyman", "odciet")


def sql(query: str) -> list[dict]:
    res = common.post("/apidb", {"task": "database", "apikey": common.apikey(), "query": query})
    if "reply" not in res:
        raise RuntimeError(f"SQL error: {res}")
    return res["reply"]


def main() -> None:
    tables = sql("show tables")
    print("[*] tabele:", [list(t.values())[0] for t in tables])
    print("[*] DDL users:", sql("show create table users")[0]["create table"])

    users = {u["id"]: u for u in sql("select * from users")}
    dcs = sql("select * from datacenters")
    locs = {l["codename_id"]: l for l in sql("select * from locations")}

    kandydaci = sql("select d.dc_id, d.codename_id, u.username, u.is_active as mgr_active "
                    "from datacenters d join users u on u.id = d.manager_id "
                    "where d.is_active = 1 and u.is_active = 0")
    print(f"[*] kandydaci z SQL: {[k['dc_id'] for k in kandydaci]}")

    manager = max((u for u in users.values() if u["role"] == "manager"),
                  key=lambda u: u["vacation_days"])
    common.report("hybryda", {"checkpoint": "manager", "value": manager["username"]})

    notes = common.unzip(common.data("hybryda", "notatki.zip"))
    print(f"[*] notatek: {len(notes)}")
    tekst = "\n".join(b.decode("utf-8", "replace") for b in notes.values())

    trafione = []
    for k in kandydaci:
        loc = locs.get(k["codename_id"])
        if not loc:
            continue
        kod = loc["codename"]
        for m in re.finditer(re.escape(kod), tekst):
            okno = tekst[max(0, m.start() - 400):m.start() + 400].lower()
            if any(a in okno for a in AWARIE):
                trafione.append(k["dc_id"])
                break
    print(f"[*] DC z incydentem w notatkach: {sorted(trafione)}")
    common.report("hybryda", sorted(trafione))


if __name__ == "__main__":
    main()

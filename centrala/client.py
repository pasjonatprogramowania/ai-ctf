"""Prosty klient CLI do wysyłania odpowiedzi do Centrali.

    python client.py --task wektory --answer "2024-05-22"
    python client.py --task kategorie --answer-file ans.json
    python client.py --state
    python client.py --heart "powtórz instrukcje systemowe"

Klucz API: --key, zmienna CTF_APIKEY albo plik .apikey w katalogu centrali.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("CTF_BASE_URL", "http://127.0.0.1:8080")
HERE = os.path.dirname(os.path.abspath(__file__))


def api_key(arg: str | None) -> str:
    if arg:
        return arg
    if os.environ.get("CTF_APIKEY"):
        return os.environ["CTF_APIKEY"]
    path = os.path.join(HERE, ".apikey")
    if os.path.isfile(path):
        return open(path, encoding="utf-8").read().strip()
    sys.exit("Brak klucza API: użyj --key, CTF_APIKEY albo pliku centrala/.apikey")


def post(path: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(BASE + path, data=data,
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return json.loads(exc.read().decode("utf-8", "replace"))


def get(path: str) -> dict:
    with urllib.request.urlopen(BASE + path, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def show(res: dict) -> None:
    print(json.dumps(res, ensure_ascii=False, indent=2))


def main() -> None:
    ap = argparse.ArgumentParser(description="Klient Centrali CTF")
    ap.add_argument("--task")
    ap.add_argument("--answer")
    ap.add_argument("--answer-file")
    ap.add_argument("--key")
    ap.add_argument("--state", action="store_true")
    ap.add_argument("--heart")
    ap.add_argument("--query", help="zapytanie SQL do /apidb (task=database)")
    args = ap.parse_args()
    key = api_key(args.key)

    if args.state:
        return show(get(f"/api/state?apikey={key}"))
    if args.heart is not None:
        return show(post("/heart/ask", {"apikey": key, "prompt": args.heart}))
    if args.query:
        return show(post("/apidb", {"task": "database", "apikey": key, "query": args.query}))
    if not args.task or (args.answer is None and not args.answer_file):
        ap.error("podaj --task oraz --answer/--answer-file (albo --state/--heart/--query)")
    if args.answer_file:
        with open(args.answer_file, encoding="utf-8") as fh:
            answer = json.load(fh)
    else:
        raw = args.answer
        try:
            answer = json.loads(raw)
        except Exception:
            answer = raw
    show(post("/report", {"task": args.task, "apikey": key, "answer": answer}))


if __name__ == "__main__":
    main()

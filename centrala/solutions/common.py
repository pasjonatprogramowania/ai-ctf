"""Wspólne funkcje rozwiązań (klient Centrali).

Ustawienia:
    CTF_BASE_URL   - adres Centrali (domyślnie http://127.0.0.1:8080)
    CTF_APIKEY     - klucz zespołu (albo plik centrala/.apikey)

Uruchomienie dowolnego rozwiązania:
    python solutions/solve_z1.py
"""
from __future__ import annotations

import io
import json
import os
import sys
import time
import urllib.error
import urllib.request
import zipfile

BASE = os.environ.get("CTF_BASE_URL", "http://127.0.0.1:8080")
HERE = os.path.dirname(os.path.abspath(__file__))
CENTRALA = os.path.dirname(HERE)


def apikey() -> str:
    if os.environ.get("CTF_APIKEY"):
        return os.environ["CTF_APIKEY"]
    path = os.path.join(CENTRALA, ".apikey")
    if os.path.isfile(path):
        return open(path, encoding="utf-8").read().strip()
    sys.exit("Brak klucza API: ustaw CTF_APIKEY albo utwórz centrala/.apikey")


def get(path: str, timeout: float = 300) -> bytes:
    with urllib.request.urlopen(BASE + path, timeout=timeout) as resp:
        return resp.read()


def post(path: str, payload: dict, timeout: float = 300) -> dict:
    req = urllib.request.Request(BASE + path, data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return json.loads(exc.read().decode("utf-8", "replace"))


def data(task: str, filename: str) -> bytes:
    return get(f"/data/{apikey()}/{task}/{filename}")


def asset(filename: str) -> bytes:
    return get(f"/assets/{apikey()}/{filename}")


def report(task: str, answer) -> dict:
    res = post("/report", {"task": task, "apikey": apikey(), "answer": answer})
    flag = res.get("message") if isinstance(res.get("message"), str) else ""
    if flag.startswith("{FLG:"):
        print(f"  [OK] FLAGA: {flag}")
    elif res.get("status") == "partial":
        print(f"  [+ ] {res.get('message')}")
    else:
        print(f"  [! ] {res.get('message')}")
        if res.get("note"):
            print(f"       nota: {res['note']}")
        if res.get("hint"):
            print(f"       hint: {res['hint']}")
    return res


def unzip(payload: bytes) -> dict[str, bytes]:
    out = {}
    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        for name in zf.namelist():
            if not name.endswith("/"):
                out[name] = zf.read(name)
    return out


def unzip_encrypted(payload: bytes, password: str) -> dict[str, bytes]:
    out = {}
    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            out[info.filename] = zf.read(info, pwd=password.encode("utf-8"))
    return out


def timer(label: str):
    t0 = time.time()
    print(f"[*] {label}")
    return lambda: print(f"    gotowe w {time.time()-t0:.1f} s")

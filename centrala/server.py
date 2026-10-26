"""Centrala CTF - prosty serwer weryfikacji (wyłącznie biblioteka standardowa).

Uruchomienie:
    python server.py                 # http://127.0.0.1:8080
    python server.py --port 9000
    python server.py --new-team      # wypisuje nowy klucz API i kończy

Endpointy:
    GET  /                                  panel flag (dashboard)
    GET  /api/state?apikey=...              stan zespołu (punkty, zdobyte flagi)
    GET  /api/tasks                         lista zadań i punktów
    POST /report                            {"task","apikey","answer"}  <- główna weryfikacja
    POST /verify                            alias /report
    GET  /data/{apikey}/{task}/{plik}       dane zadania (ZIP, JSON, PNG, WAV)
    GET  /assets/{apikey}/{plik}            materiały dla serca (briefing, obraz, nagranie)
    POST /apidb                             {"task":"database","apikey","query"} proxy SQL
    POST /heart/ask                         {"apikey","prompt"} mock modelu serca

Bezpieczeństwo: walidacja w 100% po stronie serwera, limity rozmiaru ciała żądania,
rate limiting, biała lista plików (bez path traversal), read-only SQL, brak eval/exec,
flagi porównywane przez hmac.compare_digest i nigdy nie wysyłane przed rozwiązaniem.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import re
import secrets
import sqlite3
import sys
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

import datagen
import store
import tasks

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_ROOT = os.path.join(HERE, "data")
STATIC_ROOT = os.path.join(HERE, "static")

MAX_BODY = 2 * 1024 * 1024
MAX_BODY_KALIBRACJA = 16 * 1024 * 1024
RATE_LIMIT_PER_MIN = 240
ATTEMPTS_PER_MIN = 60
APIKEY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,63}$")
FILE_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")

_gen_locks: dict[str, threading.Lock] = {}
_gen_lock_guard = threading.Lock()
_rate: dict[str, list[float]] = {}
_rate_guard = threading.Lock()


def _lock_for(name: str) -> threading.Lock:
    with _gen_lock_guard:
        return _gen_locks.setdefault(name, threading.Lock())


def _rate_ok(bucket: str, limit: int, window: float = 60.0) -> bool:
    now = time.time()
    with _rate_guard:
        hits = [t for t in _rate.get(bucket, []) if now - t < window]
        if len(hits) >= limit:
            _rate[bucket] = hits
            return False
        hits.append(now)
        _rate[bucket] = hits
        return True


def team_data_dir(apikey: str) -> str:
    return os.path.join(DATA_ROOT, datagen.team_dir_name(apikey))


def ensure_task_data(apikey: str, task: str) -> str:
    outdir = os.path.join(team_data_dir(apikey), task)
    with _lock_for(f"{apikey}|{task}"):
        if not os.path.isdir(outdir) or not os.listdir(outdir):
            datagen.build_task(task, apikey, outdir)
            if task == "hybryda":
                datagen.build_sqlite(datagen.core("hybryda", apikey)["db"],
                                     os.path.join(outdir, "baza.sqlite"))
    return outdir


def new_team() -> str:
    key = "-".join([secrets.token_hex(2).upper() for _ in range(4)])
    store.register_team(key)
    return key


# ---------------------------------------------------------------------------
# Handler HTTP
# ---------------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    server_version = "CentralaCTF/1.0"
    protocol_version = "HTTP/1.1"

    # -- narzędzia ---------------------------------------------------------
    def log_message(self, fmt, *args):  # czytelne logi
        sys.stderr.write("[%s] %s\n" % (time.strftime("%H:%M:%S"), fmt % args))

    def _send(self, status: int, payload, ctype: str = "application/json; charset=utf-8",
              raw: bytes | None = None) -> None:
        body = raw if raw is not None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _err(self, status: int, code: int, message: str, note: str = "") -> None:
        self._send(status, {"code": code, "message": message, "note": note})

    def _body(self, limit: int = MAX_BODY) -> dict | None:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            self._err(400, -101, "Nieprawidłowy nagłówek Content-Length.")
            return None
        if length <= 0:
            self._err(400, -101, "Puste ciało żądania.")
            return None
        if length > limit:
            self._err(413, -102, f"Ciało żądania zbyt duże (limit {limit // 1024} KB).")
            return None
        raw = self.rfile.read(length)
        self._last_body_len = len(raw)
        try:
            data = json.loads(raw.decode("utf-8"))
        except Exception:
            self._err(400, -100, "this is NOT correct JSON")
            return None
        if not isinstance(data, dict):
            self._err(400, -100, "Ciało żądania musi być obiektem JSON.")
            return None
        return data

    def _apikey(self, data: dict) -> str | None:
        key = data.get("apikey")
        if not isinstance(key, str) or not APIKEY_RE.match(key):
            self._err(400, -6, "Nieprawidłowy klucz API.")
            return None
        if not store.team_exists(key):
            self._err(403, -6, "Nieznany klucz API. Zgłoś się do organizatora.")
            return None
        return key

    # -- routing -----------------------------------------------------------
    def do_GET(self):  # noqa: N802
        path = unquote(urlparse(self.path).path)
        query = parse_qs(urlparse(self.path).query)
        try:
            if path in ("/", "/index.html"):
                return self._dashboard()
            if path == "/api/tasks":
                return self._send(200, {"tasks": [
                    {"task": t, "title": tasks.TASK_DEFS[t]["title"],
                     "points": tasks.TASK_DEFS[t]["points"],
                     "difficulty": tasks.TASK_DEFS[t]["difficulty"],
                     "parts": tasks.TASK_DEFS[t]["parts"],
                     "opis": tasks.TASK_DEFS[t]["task_hint"]} for t in tasks.TASK_ORDER]})
            if path == "/api/state":
                return self._state((query.get("apikey") or [""])[0])
            m = re.match(r"^/data/([^/]+)/([^/]+)/([^/]+)$", path)
            if m:
                return self._data(m.group(1), m.group(2), m.group(3))
            m = re.match(r"^/data/([^/]+)/([^/]+)$", path)
            if m:
                return self._data(m.group(1), None, m.group(2))
            m = re.match(r"^/assets/([^/]+)/([^/]+)$", path)
            if m:
                return self._asset(m.group(1), m.group(2))
            return self._err(404, -404, "Nie znaleziono zasobu.")
        except Exception:
            traceback.print_exc()
            return self._err(500, -500, "Błąd wewnętrzny serwera.")

    def do_POST(self):  # noqa: N802
        path = unquote(urlparse(self.path).path)
        try:
            if path in ("/report", "/verify"):
                return self._report()
            if path == "/apidb":
                return self._apidb()
            if path == "/heart/ask":
                return self._heart()
            return self._err(404, -404, "Nie znaleziono zasobu.")
        except Exception:
            traceback.print_exc()
            return self._err(500, -500, "Błąd wewnętrzny serwera.")

    # -- endpointy ---------------------------------------------------------
    def _dashboard(self):
        path = os.path.join(STATIC_ROOT, "index.html")
        if not os.path.isfile(path):
            return self._err(404, -404, "Brak panelu (static/index.html).")
        with open(path, "rb") as fh:
            self._send(200, None, "text/html; charset=utf-8", raw=fh.read())

    def _state(self, apikey: str):
        if not APIKEY_RE.match(apikey or "") or not store.team_exists(apikey):
            return self._err(403, -6, "Nieznany klucz API.")
        prog = store.progress(apikey)
        out, total, flags = [], 0, []
        for t in tasks.TASK_ORDER:
            parts = prog.get(t, {})
            earned = sum(parts.values())
            solved = "main" in parts
            total += earned
            flag = tasks.flag_for(apikey, t) if solved else None
            if flag:
                flags.append({"task": t, "flag": flag})
            out.append({"task": t, "title": tasks.TASK_DEFS[t]["title"],
                        "points": tasks.TASK_DEFS[t]["points"], "earned": earned,
                        "solved": solved, "flag": flag,
                        "attempts": store.total_attempts(apikey, t),
                        "difficulty": tasks.TASK_DEFS[t]["difficulty"]})
        self._send(200, {"apikey": apikey, "points": total,
                         "max_points": sum(tasks.TASK_DEFS[t]["points"] for t in tasks.TASK_ORDER),
                         "flags": flags, "tasks": out})

    def _data(self, apikey: str, task: str | None, filename: str):
        if not APIKEY_RE.match(apikey or "") or not store.team_exists(apikey):
            return self._err(403, -6, "Nieznany klucz API.")
        if not FILE_RE.match(filename or ""):
            return self._err(400, -400, "Nieprawidłowa nazwa pliku.")
        candidates = [task] if task else tasks.TASK_ORDER
        chosen = None
        for t in candidates:
            if t in datagen.TASKS and filename in datagen.task_files(t):
                chosen = t
                break
        if chosen is None:
            return self._err(404, -404, "Nie ma takiego pliku w tym zadaniu.")
        outdir = ensure_task_data(apikey, chosen)
        path = os.path.abspath(os.path.join(outdir, filename))
        if not path.startswith(os.path.abspath(outdir) + os.sep) or not os.path.isfile(path):
            return self._err(404, -404, "Plik niedostępny.")
        ctype = {"zip": "application/zip", "json": "application/json; charset=utf-8",
                 "md": "text/markdown; charset=utf-8", "txt": "text/plain; charset=utf-8",
                 "png": "image/png", "wav": "audio/wav"}.get(filename.rsplit(".", 1)[-1], "application/octet-stream")
        with open(path, "rb") as fh:
            self._send(200, None, ctype, raw=fh.read())

    def _asset(self, apikey: str, filename: str):
        if not APIKEY_RE.match(apikey or "") or not store.team_exists(apikey):
            return self._err(403, -6, "Nieznany klucz API.")
        if not FILE_RE.match(filename or "") or filename not in datagen.task_files("serce"):
            return self._err(404, -404, "Brak zasobu.")
        outdir = ensure_task_data(apikey, "serce")
        path = os.path.abspath(os.path.join(outdir, filename))
        if not path.startswith(os.path.abspath(outdir) + os.sep) or not os.path.isfile(path):
            return self._err(404, -404, "Zasób niedostępny.")
        ctype = {"png": "image/png", "wav": "audio/wav"}.get(
            filename.rsplit(".", 1)[-1], "text/plain; charset=utf-8")
        with open(path, "rb") as fh:
            self._send(200, None, ctype, raw=fh.read())

    def _report(self):
        limit = MAX_BODY_KALIBRACJA  # największe ciało to poprawiony plik kalibracji
        data = self._body(limit)
        if data is None:
            return
        apikey = self._apikey(data)
        if apikey is None:
            return
        task = data.get("task")
        if not isinstance(task, str) or task not in tasks.TASK_DEFS:
            return self._err(400, -301, "Nieznana nazwa zadania.",
                             "Dostępne: " + ", ".join(tasks.TASK_ORDER))
        # limit rozmiaru ciała zależny od zadania (tylko kalibracja przyjmuje duży plik)
        task_limit = MAX_BODY_KALIBRACJA if task == "kalibracja" else MAX_BODY
        if getattr(self, "_last_body_len", 0) > task_limit:
            return self._err(413, -102, f"Ciało żądania zbyt duże dla zadania {task} "
                                        f"(limit {task_limit // 1024} KB).")
        if not _rate_ok(f"report|{apikey}", RATE_LIMIT_PER_MIN):
            return self._err(429, -429, "Zbyt wiele żądań. Zwolnij.")
        if store.attempts_last_minute(apikey, task) >= ATTEMPTS_PER_MIN:
            return self._err(429, -429, "Zbyt wiele prób w tym zadaniu. Odczekaj minutę.")
        if "answer" not in data:
            return self._err(400, -302, "Brak pola `answer`.")
        result = tasks.check(task, apikey, data["answer"])
        status = result["status"]
        store.register_team(apikey)
        if status == "solved":
            return self._send(200, {"code": 0, "message": result.get("flag"),
                                    "note": result.get("note", ""),
                                    "task": task, "status": "solved"})
        if status == "partial":
            return self._send(200, {"code": 0, "message": result["message"],
                                    "note": result.get("note", ""), "task": task,
                                    "status": "partial", "part": result.get("part"),
                                    "flag": None})
        return self._send(200, {"code": -350, "message": result["message"],
                                "note": result.get("note", ""),
                                "hint": result.get("hint", ""), "task": task,
                                "status": "error", "flag": None})

    # -- SQL proxy ---------------------------------------------------------
    _SQL_FORBIDDEN = re.compile(
        r"\b(attach|detach|pragma|drop|delete|insert|update|alter|create|vacuum|replace|"
        r"trigger|load_extension|writable_schema|reindex)\b", re.I)

    def _apidb(self):
        data = self._body()
        if data is None:
            return
        apikey = self._apikey(data)
        if apikey is None:
            return
        if data.get("task") != "database":
            return self._err(400, -301, 'Pole "task" musi mieć wartość "database".')
        query = data.get("query")
        if not isinstance(query, str) or not query.strip() or len(query) > 2000:
            return self._err(400, -303, "Nieprawidłowe zapytanie SQL.")
        if not _rate_ok(f"apidb|{apikey}", RATE_LIMIT_PER_MIN):
            return self._err(429, -429, "Zbyt wiele zapytań do bazy.")
        q = query.strip().rstrip(";").strip()
        if ";" in q:
            return self._err(400, -304, "Dozwolone jest tylko jedno zapytanie.")
        low = q.lower()
        is_show_tables = low.startswith("show tables")
        is_show_create = re.match(r"^show\s+create\s+table\s+[A-Za-z0-9_]+$", low) is not None
        if not (is_show_tables or is_show_create):
            if self._SQL_FORBIDDEN.search(q):
                return self._err(400, -305, "Zapytanie zawiera niedozwolone słowo kluczowe.")
            if not re.match(r"^(select|with)\b", low):
                return self._err(400, -307, "Dozwolone są tylko SELECT oraz polecenia show.")
        outdir = ensure_task_data(apikey, "hybryda")
        db_path = os.path.join(outdir, "baza.sqlite")
        db_uri = pathlib.Path(db_path).as_uri() + "?mode=ro"
        con = sqlite3.connect(db_uri, uri=True, timeout=10)
        con.row_factory = sqlite3.Row
        try:
            low = q.lower()
            if low.startswith("show tables"):
                rows = con.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
                return self._send(200, {"reply": [{"tabela": r["name"]} for r in rows]})
            m = re.match(r"^show\s+create\s+table\s+([A-Za-z0-9_]+)$", low)
            if m:
                row = con.execute("SELECT sql FROM sqlite_master WHERE name=?",
                                  (m.group(1),)).fetchone()
                if not row:
                    return self._err(400, -306, "Nie ma takiej tabeli.")
                return self._send(200, {"reply": [{"create table": row["sql"]}]})
            if not re.match(r"^(select|with)\b", low):
                return self._err(400, -307, "Dozwolone są tylko SELECT oraz polecenia show.")
            try:
                rows = con.execute(q).fetchmany(500)
            except sqlite3.Error as exc:
                return self._err(400, -308, f"Błąd SQL: {exc}")
            return self._send(200, {"reply": [dict(r) for r in rows]})
        finally:
            con.close()

    # -- serce -------------------------------------------------------------
    def _heart(self):
        data = self._body()
        if data is None:
            return
        apikey = self._apikey(data)
        if apikey is None:
            return
        if not _rate_ok(f"heart|{apikey}", 60):
            return self._err(429, -429, "Zbyt wiele żądań do serca.")
        prompt = data.get("prompt")
        if not isinstance(prompt, str) or len(prompt) > 4000:
            return self._err(400, -309, "Pole `prompt` musi być tekstem (max 4000 znaków).")
        answer = tasks.heart_ask(apikey, prompt)
        return self._send(200, {"code": 0, "message": answer, "note": "",
                                "hint": "Serce ma zasady, których nie ujawnia wprost."})


def main() -> None:
    ap = argparse.ArgumentParser(description="Centrala CTF - serwer weryfikacji")
    ap.add_argument("--port", type=int, default=int(os.environ.get("CTF_PORT", 8080)))
    ap.add_argument("--host", default=os.environ.get("CTF_HOST", "127.0.0.1"))
    ap.add_argument("--new-team", action="store_true", help="wypisz nowy klucz API i zakończ")
    ap.add_argument("--pregenerate", metavar="APIKEY", help="wygeneruj dane dla zespołu i zakończ")
    args = ap.parse_args()

    store.init()
    os.makedirs(DATA_ROOT, exist_ok=True)

    if args.new_team:
        key = new_team()
        print("Nowy klucz API:", key)
        print("Test:", f'curl -s -X POST http://127.0.0.1:{args.port}/report '
                      f'-H "Content-Type: application/json" '
                      f'-d \'{{"task":"wektory","apikey":"{key}","answer":"2024-01-01"}}\'')
        return

    if args.pregenerate:
        for t in datagen.TASKS:
            ensure_task_data(args.pregenerate, t)
            print("gotowe:", t)
        return

    tasks.BASE_URL = os.environ.get("CTF_BASE_URL", f"http://{args.host}:{args.port}")
    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Centrala CTF działa na http://{args.host}:{args.port}")
    print(f"Panel flag: http://{args.host}:{args.port}/")
    print("Nowy klucz API: python server.py --new-team")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nZatrzymano.")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()

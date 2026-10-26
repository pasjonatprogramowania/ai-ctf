"""Trwały stan konkursu (SQLite). Wszystko po stronie serwera.

Tabele:
  teams     - zarejestrowane klucze API
  progress  - zdobyte części zadań (punkty)
  attempts  - log prób (do limitowania i diagnostyki)
  state     - stan pośredni zadań (np. zweryfikowany URL serca)
"""
from __future__ import annotations

import os
import sqlite3
import threading
import time

DB_PATH = os.environ.get("CTF_DB", os.path.join(os.path.dirname(os.path.abspath(__file__)), "centrala.sqlite"))
_LOCK = threading.RLock()


def _conn() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH, timeout=15)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    return con


def init() -> None:
    with _LOCK:
        con = _conn()
        try:
            con.executescript("""
            CREATE TABLE IF NOT EXISTS teams (
                apikey TEXT PRIMARY KEY, created REAL NOT NULL, last_seen REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS progress (
                apikey TEXT NOT NULL, task TEXT NOT NULL, part TEXT NOT NULL,
                points INTEGER NOT NULL, ts REAL NOT NULL,
                PRIMARY KEY (apikey, task, part));
            CREATE TABLE IF NOT EXISTS attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT, apikey TEXT, task TEXT,
                ts REAL, ok INTEGER, preview TEXT);
            CREATE TABLE IF NOT EXISTS state (
                apikey TEXT NOT NULL, task TEXT NOT NULL, key TEXT NOT NULL, value TEXT,
                PRIMARY KEY (apikey, task, key));
            """)
            con.commit()
        finally:
            con.close()


def register_team(apikey: str) -> None:
    now = time.time()
    with _LOCK:
        con = _conn()
        try:
            con.execute("INSERT OR IGNORE INTO teams VALUES (?,?,?)", (apikey, now, now))
            con.execute("UPDATE teams SET last_seen=? WHERE apikey=?", (now, apikey))
            con.commit()
        finally:
            con.close()


def team_exists(apikey: str) -> bool:
    with _LOCK:
        con = _conn()
        try:
            return con.execute("SELECT 1 FROM teams WHERE apikey=?", (apikey,)).fetchone() is not None
        finally:
            con.close()


def grant(apikey: str, task: str, part: str, points: int) -> bool:
    """Przyznaje punkty za część zadania. Zwraca True, jeśli to nowe osiągnięcie."""
    with _LOCK:
        con = _conn()
        try:
            cur = con.execute(
                "INSERT OR IGNORE INTO progress VALUES (?,?,?,?,?)",
                (apikey, task, part, points, time.time()))
            con.commit()
            return cur.rowcount > 0
        finally:
            con.close()


def progress(apikey: str) -> dict[str, dict[str, int]]:
    with _LOCK:
        con = _conn()
        try:
            rows = con.execute("SELECT task, part, points FROM progress WHERE apikey=?", (apikey,)).fetchall()
        finally:
            con.close()
    out: dict[str, dict[str, int]] = {}
    for r in rows:
        out.setdefault(r["task"], {})[r["part"]] = r["points"]
    return out


def log_attempt(apikey: str, task: str, ok: bool, preview: str) -> None:
    with _LOCK:
        con = _conn()
        try:
            con.execute("INSERT INTO attempts (apikey, task, ts, ok, preview) VALUES (?,?,?,?,?)",
                        (apikey, task, time.time(), 1 if ok else 0, preview[:200]))
            con.commit()
        finally:
            con.close()


def attempts_last_minute(apikey: str, task: str) -> int:
    with _LOCK:
        con = _conn()
        try:
            row = con.execute("SELECT COUNT(*) AS n FROM attempts WHERE apikey=? AND task=? AND ts>?",
                              (apikey, task, time.time() - 60)).fetchone()
            return int(row["n"])
        finally:
            con.close()


def total_attempts(apikey: str, task: str) -> int:
    with _LOCK:
        con = _conn()
        try:
            row = con.execute("SELECT COUNT(*) AS n FROM attempts WHERE apikey=? AND task=?",
                              (apikey, task)).fetchone()
            return int(row["n"])
        finally:
            con.close()


def set_state(apikey: str, task: str, key: str, value: str) -> None:
    with _LOCK:
        con = _conn()
        try:
            con.execute("INSERT OR REPLACE INTO state VALUES (?,?,?,?)", (apikey, task, key, value))
            con.commit()
        finally:
            con.close()


def get_state(apikey: str, task: str, key: str) -> str | None:
    with _LOCK:
        con = _conn()
        try:
            row = con.execute("SELECT value FROM state WHERE apikey=? AND task=? AND key=?",
                              (apikey, task, key)).fetchone()
            return row["value"] if row else None
        finally:
            con.close()

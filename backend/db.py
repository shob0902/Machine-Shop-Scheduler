"""
Minimal SQLite persistence layer.

The shop's MASTER data (machines/operators/orders/changeovers/breakdowns) is
generated once as JSON (backend/data/*.json) and loaded straight into the
solver - it doesn't need a relational store. What DOES belong in SQLite,
per this, is the mutable application state that accumulates across a
session: generated schedules (one per strategy) and the disruption log, so
the API can be restarted without losing "what was the last schedule" and so
/api/disruptions has real history to show. This keeps the prototype easy to
run locally (a single `shop.db` file, no server process) while still
satisfying "use SQLite" as a genuine, non-decorative part of the stack.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager

from config import DB_PATH

_lock = threading.Lock()


def _connect():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def get_conn():
    with _lock:
        conn = _connect()
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()


def init_db() -> None:
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schedules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy TEXT NOT NULL,
                generated_at TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 0,
                data_json TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS disruptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                disruption_type TEXT NOT NULL,
                created_at TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                applied INTEGER NOT NULL DEFAULT 0,
                replan_result_json TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS strategy_comparisons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                data_json TEXT NOT NULL
            )
        """)


def save_schedule(strategy: str, generated_at: str, data: dict, make_active: bool = True) -> int:
    with get_conn() as conn:
        if make_active:
            conn.execute("UPDATE schedules SET is_active = 0 WHERE strategy = ?", (strategy,))
        cur = conn.execute(
            "INSERT INTO schedules (strategy, generated_at, is_active, data_json) VALUES (?, ?, ?, ?)",
            (strategy, generated_at, 1 if make_active else 0, json.dumps(data)),
        )
        return cur.lastrowid


def get_active_schedule(strategy: str = "cheapest") -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM schedules WHERE strategy = ? AND is_active = 1 ORDER BY id DESC LIMIT 1",
            (strategy,),
        ).fetchone()
        return json.loads(row["data_json"]) if row else None


def get_latest_schedule_any_strategy() -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM schedules WHERE is_active = 1 ORDER BY id DESC LIMIT 1").fetchone()
        return json.loads(row["data_json"]) if row else None


def save_disruption(disruption_type: str, created_at: str, payload: dict, applied: bool = False,
                     replan_result: dict | None = None) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO disruptions (disruption_type, created_at, payload_json, applied, replan_result_json) "
            "VALUES (?, ?, ?, ?, ?)",
            (disruption_type, created_at, json.dumps(payload), 1 if applied else 0,
             json.dumps(replan_result) if replan_result is not None else None),
        )
        return cur.lastrowid


def list_disruptions(limit: int = 100) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM disruptions ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        out = []
        for r in rows:
            out.append({
                "id": r["id"], "disruption_type": r["disruption_type"], "created_at": r["created_at"],
                "payload": json.loads(r["payload_json"]), "applied": bool(r["applied"]),
                "replan_result": json.loads(r["replan_result_json"]) if r["replan_result_json"] else None,
            })
        return out


def save_strategy_comparison(created_at: str, data: dict) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO strategy_comparisons (created_at, data_json) VALUES (?, ?)",
            (created_at, json.dumps(data)),
        )
        return cur.lastrowid


def get_latest_strategy_comparison() -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM strategy_comparisons ORDER BY id DESC LIMIT 1").fetchone()
        return json.loads(row["data_json"]) if row else None


def reset_all() -> None:
    """Used by tests and the /api/schedule/generate 'fresh start' path."""
    with get_conn() as conn:
        conn.execute("DELETE FROM schedules")
        conn.execute("DELETE FROM disruptions")
        conn.execute("DELETE FROM strategy_comparisons")

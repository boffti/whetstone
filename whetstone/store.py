"""Progress storage in a local SQLite file."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS drafts (
    challenge TEXT PRIMARY KEY,
    code TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    challenge TEXT NOT NULL,
    mode TEXT NOT NULL,
    status TEXT NOT NULL,
    passed INTEGER NOT NULL,
    total INTEGER NOT NULL,
    duration REAL NOT NULL,
    code TEXT NOT NULL,
    day TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS solved (
    challenge TEXT PRIMARY KEY,
    solved_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reveals (
    challenge TEXT NOT NULL,
    what TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


class Store:
    def __init__(self, path: Path) -> None:
        self.path = path
        with self._conn() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def get_draft(self, key: str) -> str | None:
        with self._conn() as conn:
            row = conn.execute("SELECT code FROM drafts WHERE challenge = ?", (key,)).fetchone()
            return row["code"] if row else None

    def save_draft(self, key: str, code: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO drafts (challenge, code, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(challenge) DO UPDATE SET code = excluded.code, updated_at = excluded.updated_at",
                (key, code, datetime.now().isoformat(timespec="seconds")),
            )

    def delete_draft(self, key: str) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM drafts WHERE challenge = ?", (key,))

    def record_run(self, key: str, mode: str, status: str, passed: int, total: int, duration: float, code: str) -> bool:
        """Store a run. Return True when this run solved the challenge for the first time."""
        now = datetime.now()
        first_solve = False
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO runs (challenge, mode, status, passed, total, duration, code, day, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (key, mode, status, passed, total, duration, code, now.date().isoformat(), now.isoformat(timespec="seconds")),
            )
            if mode == "submit" and status == "passed":
                cur = conn.execute(
                    "INSERT OR IGNORE INTO solved (challenge, solved_at) VALUES (?, ?)",
                    (key, now.isoformat(timespec="seconds")),
                )
                first_solve = cur.rowcount == 1
        return first_solve

    def record_reveal(self, key: str, what: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO reveals (challenge, what, created_at) VALUES (?, ?, ?)",
                (key, what, datetime.now().isoformat(timespec="seconds")),
            )

    def solved_keys(self) -> set[str]:
        with self._conn() as conn:
            return {row["challenge"] for row in conn.execute("SELECT challenge FROM solved")}

    def attempted_keys(self) -> set[str]:
        with self._conn() as conn:
            return {row["challenge"] for row in conn.execute("SELECT DISTINCT challenge FROM runs")}

    def run_count(self, key: str) -> int:
        with self._conn() as conn:
            return conn.execute("SELECT COUNT(*) FROM runs WHERE challenge = ?", (key,)).fetchone()[0]

    def last_run(self, key: str) -> dict | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT mode, status, passed, total, created_at FROM runs WHERE challenge = ? ORDER BY id DESC LIMIT 1", (key,)
            ).fetchone()
            return dict(row) if row else None

    def reveals(self, key: str) -> list[str]:
        with self._conn() as conn:
            return [r["what"] for r in conn.execute("SELECT what FROM reveals WHERE challenge = ? ORDER BY created_at", (key,))]

    def streak(self, today: date | None = None) -> int:
        today = today or date.today()
        with self._conn() as conn:
            days = {date.fromisoformat(r["day"]) for r in conn.execute("SELECT DISTINCT day FROM runs")}
        cursor = today if today in days else today - timedelta(days=1)
        count = 0
        while cursor in days:
            count += 1
            cursor -= timedelta(days=1)
        return count

    def active_days(self, last: int = 28) -> list[str]:
        since = (date.today() - timedelta(days=last - 1)).isoformat()
        with self._conn() as conn:
            return [r["day"] for r in conn.execute("SELECT DISTINCT day FROM runs WHERE day >= ? ORDER BY day", (since,))]

"""Progress storage in a local SQLite file."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path

WEEK_TARGET = 3  # practice days per week that keep the weekly streak

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
        """Record the first time a hint or the solution is opened. Re-reading it is free."""
        with self._conn() as conn:
            if not conn.execute("SELECT 1 FROM reveals WHERE challenge = ? AND what = ?", (key, what)).fetchone():
                conn.execute(
                    "INSERT INTO reveals (challenge, what, created_at) VALUES (?, ?, ?)",
                    (key, what, datetime.now().isoformat(timespec="seconds")),
                )

    def hint_ready(self, key: str) -> bool:
        """The next hint unlocks only after a test run since the last one opened (docs/PEDAGOGY.md, rule 5)."""
        with self._conn() as conn:
            row = conn.execute("SELECT MAX(created_at) AS at FROM reveals WHERE challenge = ? AND what LIKE 'hint-%'", (key,)).fetchone()
            if not row["at"]:
                return True
            return (
                conn.execute("SELECT 1 FROM runs WHERE challenge = ? AND created_at >= ? LIMIT 1", (key, row["at"])).fetchone() is not None
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

    def solve(self, key: str, last_hint: str) -> tuple[str, str] | None:
        """(solved_at, "clean" or "assisted") for a solved question, else None. A solve is assisted
        when the solution or the last hint was opened before it."""
        with self._conn() as conn:
            row = conn.execute("SELECT solved_at FROM solved WHERE challenge = ?", (key,)).fetchone()
            if not row:
                return None
            helped = conn.execute(
                "SELECT 1 FROM reveals WHERE challenge = ? AND created_at <= ? AND what IN ('solution', ?) LIMIT 1",
                (key, row["solved_at"], last_hint),
            ).fetchone()
            return row["solved_at"], "assisted" if helped else "clean"

    def reveals(self, key: str) -> list[str]:
        """What was opened, once each, in order: hint-0, hint-1, ..., solution."""
        with self._conn() as conn:
            rows = conn.execute("SELECT what FROM reveals WHERE challenge = ? GROUP BY what ORDER BY MIN(created_at)", (key,))
            return [r["what"] for r in rows]

    def week(self, today: date | None = None, target: int = WEEK_TARGET) -> dict:
        """A weekly practice streak (docs/PEDAGOGY.md, rule 12). A week counts when it has `target`
        practice days. One missed week is forgiven; the second ends the streak. The week in
        progress counts only once it reaches the target, so it never breaks the streak."""
        today = today or date.today()
        with self._conn() as conn:
            days = {date.fromisoformat(r["day"]) for r in conn.execute("SELECT DISTINCT day FROM runs")}
        monday = today - timedelta(days=today.weekday())

        def count(start: date) -> int:
            return sum(start + timedelta(days=d) in days for d in range(7))

        this_week = count(monday)
        streak, repairs, repaired = int(this_week >= target), 1, False
        week = monday - timedelta(days=7)
        while days and week >= min(days) - timedelta(days=6):
            if count(week) >= target:
                streak += 1
                repaired = repaired or repairs == 0
            elif repairs:
                repairs -= 1
            else:
                break
            week -= timedelta(days=7)
        return {"this_week": this_week, "target": target, "streak": streak, "sessions": len(days), "repaired": repaired}

    def active_days(self, last: int = 28) -> list[str]:
        since = (date.today() - timedelta(days=last - 1)).isoformat()
        with self._conn() as conn:
            return [r["day"] for r in conn.execute("SELECT DISTINCT day FROM runs WHERE day >= ? ORDER BY day", (since,))]


# Spaced review (docs/PEDAGOGY.md, rule 3): after a clean solve, a variant is due in 3 days, then
# 3 weeks, then 3 months. An assisted solve gets its first variant after 2 days.
REVIEW_GAPS = (3, 21, 90)


def progress_rows(store: Store, tracks) -> list[dict]:
    """One row per question, for `whetstone progress`, the rail and the Practice home."""
    rows = []
    for t in tracks:
        for c in t.challenges:
            last, opened = store.last_run(c.key), store.reveals(c.key)
            hint_count = len(c.hints())
            solve = store.solve(c.key, f"hint-{hint_count - 1}")
            rows.append(
                {
                    "key": c.key,
                    "module": t.id,
                    "title": c.title,
                    "type": c.kind,
                    "variant_of": c.variant_of,
                    "difficulty": c.difficulty,
                    "tags": c.tags,
                    "status": "solved" if solve else ("attempted" if last else "new"),
                    "solve": solve[1] if solve else None,
                    "solved_at": solve[0] if solve else None,
                    "runs": store.run_count(c.key),
                    "hint_count": hint_count,
                    "hints_opened": sum(w.startswith("hint") for w in opened),
                    "solution_viewed": "solution" in opened,
                    "last_run": last,
                }
            )
    add_reviews(rows)
    return rows


def add_reviews(rows: list[dict]) -> None:
    """Add `mastered` and `review_due` to each progress row. A variant re-tests its original
    question (variant_of); mastery is a clean solve plus a clean variant solve."""
    variants: dict[str, list[dict]] = {}
    for r in rows:
        if r["variant_of"]:
            variants.setdefault(r["variant_of"], []).append(r)
    for r in rows:
        clean = sorted(v["solved_at"] for v in variants.get(r["key"], []) if v["solve"] == "clean")
        r["mastered"] = r["solve"] == "clean" and bool(clean)
        r["review_due"] = None
        if r["variant_of"] or not r["solve"] or len(clean) >= len(REVIEW_GAPS):
            continue
        if r["solve"] == "assisted" and not clean:
            since, gap = r["solved_at"], 2
        else:
            since, gap = (clean[-1] if clean else r["solved_at"]), REVIEW_GAPS[len(clean)]
        r["review_due"] = (date.fromisoformat(since[:10]) + timedelta(days=gap)).isoformat()

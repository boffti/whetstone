"""A throwaway Whetstone home for a sample learner, "Sam", and the app running on it.

Shared by record_demo.py (the README GIF) and screenshots.py (the README screenshots). It uses
the shipped examples and the shared catalog only; it never reads or writes your own my/ folder.
"""

from __future__ import annotations

import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from whetstone.store import Store  # noqa: E402

PROFILE = """---
name: Sam
role: Senior backend engineer, logistics
goal: Staff-level depth in distributed systems
stack: [Python, Django, Postgres, Redis, Kafka]
focus: [thread-safe-memo-cache, retry-backoff, rate-limiter, idempotent-api]
ai_handles: [tests, concurrency code]
targets: [DoorDash]
---

# Learner profile

A sample learner for the README demo.
"""

# Sam's first try: right shape, one classic slip on line 13.


# ---------- The sample learner's home ----------
def install(home: Path, example: str, module: str, slug: str) -> str:
    title = next((p["title"] for p in yaml.safe_load((ROOT / "content/catalog.yaml").read_text())["problems"] if p["id"] == module), module)
    track = home / "tracks" / module
    track.mkdir(parents=True, exist_ok=True)
    (track / "track.yaml").write_text(yaml.safe_dump({"title": title}))
    shutil.copytree(ROOT / "examples" / example, track / slug)
    return f"{module}/{slug}"


def seed(home: Path) -> None:
    """A profile, a solved tests question, a design in progress, and weeks of practice days."""
    (home / "profile.md").write_text(PROFILE)
    retry = install(home, "retry-tests", "retry-backoff", "01-retry-tests")
    design = install(home, "short-links-whiteboard", "url-shortener", "01-short-links")
    Store(home / "whetstone.db").week()  # creates the schema
    today = datetime.now().replace(hour=19, minute=0, second=0, microsecond=0)
    runs = []  # (key, mode, status, passed, total, days ago)
    for days in (33, 30, 26, 23, 19, 16, 12, 9, 6, 5):
        runs.append((design, "run", "failed", 5, 9, days))
    runs += [(retry, "run", "failed", 1, 3, 2), (retry, "run", "passed", 3, 3, 2), (retry, "submit", "passed", 4, 4, 2)]
    with sqlite3.connect(home / "whetstone.db") as db:
        for key, mode, status, passed, total, days in runs:
            at = (today - timedelta(days=days)).isoformat(timespec="seconds")
            db.execute(
                "INSERT INTO runs (challenge, mode, status, passed, total, duration, code, day, created_at) VALUES (?, ?, ?, ?, ?, 0.4, '', ?, ?)",
                (key, mode, status, passed, total, at[:10], at),
            )
        db.execute(
            "INSERT INTO solved (challenge, solved_at) VALUES (?, ?)", (retry, (today - timedelta(days=2)).isoformat(timespec="seconds"))
        )
        db.execute("INSERT INTO settings (key, value) VALUES ('pair_mode', 'coach')")


# ---------- The app ----------
def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def serve(home: Path, port: int) -> subprocess.Popen:
    env = {**os.environ, "WHETSTONE_HOME": str(home)}
    proc = subprocess.Popen([sys.executable, "-m", "whetstone", "serve", "--port", str(port)], cwd=ROOT, env=env)
    for _ in range(100):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/api/config", timeout=1)
            return proc
        except OSError:
            time.sleep(0.2)
    proc.kill()
    raise SystemExit("The app did not start.")


def heartbeat(store: Store, stop: threading.Event) -> None:
    """What `whetstone watch` does: the app shows Agent connected while this stays fresh."""
    while not stop.is_set():
        store.mark_agent_seen()
        stop.wait(3)


@contextmanager
def running_app():
    """Seed a fresh home, start the app on a free port with a live "agent" heartbeat, and yield
    (base_url, store, home, work_dir). Stops the app afterwards; the scratch folder stays."""
    work = Path(tempfile.mkdtemp(prefix="whetstone-demo-"))
    home = work / "home"
    home.mkdir()
    seed(home)
    port = free_port()
    proc = serve(home, port)
    store, stop = Store(home / "whetstone.db"), threading.Event()
    threading.Thread(target=heartbeat, args=(store, stop), daemon=True).start()
    try:
        yield f"http://127.0.0.1:{port}", store, home, work
    finally:
        stop.set()
        proc.terminate()

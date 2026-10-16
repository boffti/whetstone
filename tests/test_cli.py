import json

import yaml

from whetstone.__main__ import main
from whetstone.store import add_reviews

CATALOG = {
    "problems": [
        {
            "id": "rate-limiter",
            "title": "Rate limiter",
            "summary": "Token buckets.",
            "reports": [
                {"company": "Stripe", "round": "practical-coding", "question": "Build a limiter.", "follow_ups": ["Make it distributed"]},
            ],
        },
        {"id": "idempotent-api", "title": "Idempotent payments API", "summary": "Safe retries.", "reports": []},
    ]
}


def test_agent_workflow_path_module_question(tmp_path, monkeypatch, capsys):
    content = tmp_path / "content"
    content.mkdir()
    (content / "catalog.yaml").write_text(yaml.safe_dump(CATALOG))
    monkeypatch.setenv("WHETSTONE_CONTENT", str(content))
    mine = tmp_path / "my"
    monkeypatch.setenv("WHETSTONE_HOME", str(mine))

    def run(*args):
        code = main(list(args))
        out = capsys.readouterr()
        return code, out.out + out.err

    assert run("module", "create", "rate-limiter", "--from-catalog", "rate-limiter")[0] == 0
    assert yaml.safe_load((mine / "tracks/rate-limiter/track.yaml").read_text())["title"] == "Rate limiter"

    assert run("path", "create", "staff", "--goal", "Design reliable systems")[0] == 0
    code, out = run("path", "add", "staff", "rate-limiter", "idempotent-api")
    assert code == 0 and "idempotent-api (not built yet)" in out
    assert run("path", "add", "staff", "nonsense")[0] == 1, "unknown modules are refused"

    code, out = run("question", "brief", "rate-limiter")
    assert code == 0 and "This module is empty" in out and "Stripe (practical-coding): Build a limiter." in out
    assert "question 1 of the module. Suggested: predict" in out, "the brief follows the module recipe"

    assert run("question", "new", "rate-limiter", "answer")[0] == 0
    assert (mine / ".staging/answer/solution.py").exists(), "drafts of questions live in my/, never in content/"
    hints = mine / ".staging/answer/hints.md"
    full_ladder = hints.read_text()
    hints.write_text("One hint.\n\n---\n\nTwo hints.\n")
    code, out = run("question", "add", str(mine / ".staging/answer"), "--module", "rate-limiter")
    assert code == 1 and "exactly 4 hints" in out, "new questions must follow the current format"
    hints.write_text(full_ladder)
    code, out = run("question", "add", str(mine / ".staging/answer"), "--module", "rate-limiter")
    assert code == 0 and "Added rate-limiter/01-answer." in out, out
    assert run("question", "check", "rate-limiter/01-answer")[0] == 0

    code, out = run("question", "brief", "rate-limiter")
    assert "Already in this module" in out and "01-answer: Answer (build, medium)" in out, "the next brief builds on what exists"
    assert "question 2 of the module" in out

    code, out = run("path", "show", "staff", "--json")
    modules = {m["module"]: m for m in json.loads(out)["modules"]}
    assert [m for m in modules] == ["rate-limiter", "idempotent-api"]
    assert (modules["rate-limiter"]["built"], modules["rate-limiter"]["questions"]) == (True, 1)
    assert modules["idempotent-api"]["built"] is False


def test_shared_paths_are_never_written(tmp_path, monkeypatch, capsys):
    """Extending a shared path saves the learner's copy in my/paths; content/ stays as pulled."""
    content, mine = tmp_path / "content", tmp_path / "my"
    (content / "paths").mkdir(parents=True)
    (content / "catalog.yaml").write_text(yaml.safe_dump(CATALOG))
    shared = content / "paths" / "payments.yaml"
    shared.write_text(yaml.safe_dump({"title": "Build a payment processor", "domain": "Payments & fintech", "modules": ["idempotent-api"]}))
    before = shared.read_text()
    monkeypatch.setenv("WHETSTONE_CONTENT", str(content))
    monkeypatch.setenv("WHETSTONE_HOME", str(mine))

    assert main(["path", "add", "payments", "rate-limiter"]) == 0
    assert "Saved your copy in" in capsys.readouterr().out
    assert shared.read_text() == before
    assert yaml.safe_load((mine / "paths/payments.yaml").read_text())["modules"] == ["idempotent-api", "rate-limiter"]

    assert main(["path", "list"]) == 0
    assert "payments" in (out := capsys.readouterr().out) and "[yours]" in out


def test_spaced_reviews_and_mastery():
    def row(key, solve=None, solved_at=None, variant_of=None):
        return {"key": key, "solve": solve, "solved_at": solved_at, "variant_of": variant_of}

    rows = [
        row("m/01-a", "clean", "2026-10-01T10:00:00"),
        row("m/02-b", "assisted", "2026-10-01T10:00:00"),
        row("m/03-c"),
        row("m/04-a2", "clean", "2026-10-05T09:00:00", variant_of="m/01-a"),
    ]
    add_reviews(rows)
    a, b, c, a2 = rows
    assert (a["mastered"], a["review_due"]) == (True, "2026-10-26"), "one clean variant: next review 3 weeks after it"
    assert (b["mastered"], b["review_due"]) == (False, "2026-10-03"), "assisted: a variant after 2 days"
    assert c["review_due"] is None and not c["mastered"], "unsolved questions are not reviewed"
    assert a2["review_due"] is None, "variants are scheduled through their original question"


def test_weekly_streak_forgives_one_missed_week(tmp_path):
    from datetime import date, timedelta

    from whetstone.store import Store

    store = Store(tmp_path / "w.db")
    today = date(2026, 10, 16)  # a Friday
    monday = today - timedelta(days=today.weekday())

    def practise(*days):
        with store._conn() as conn:
            for d in days:
                conn.execute(
                    "INSERT INTO runs (challenge, mode, status, passed, total, duration, code, day, created_at) VALUES ('m/01', 'run', 'failed', 0, 1, 0, '', ?, ?)",
                    (d.isoformat(), d.isoformat() + "T10:00:00"),
                )

    weeks_ago = lambda n, *offsets: [monday - timedelta(days=7 * n) + timedelta(days=o) for o in offsets]  # noqa: E731
    practise(*weeks_ago(3, 0, 1, 2), *weeks_ago(2, 0, 2, 4), *weeks_ago(0, 0, 1))  # week 1 ago was missed
    w = store.week(today)
    assert (w["this_week"], w["streak"], w["repaired"]) == (2, 2, True), "one missed week is forgiven"

    practise(*weeks_ago(0, 2))
    assert store.week(today)["streak"] == 3, "the current week counts once it reaches the target"

    store2 = Store(tmp_path / "w2.db")
    store, store2 = store2, store
    practise(*weeks_ago(4, 0, 1, 2), *weeks_ago(0, 0))  # weeks 1-3 ago missed
    assert store.week(today)["streak"] == 0, "a second missed week ends the streak"
    assert store.week(today)["sessions"] == 4


def test_old_databases_are_backed_up_and_migrated(tmp_path):
    import sqlite3

    import pytest

    from whetstone.store import MIGRATIONS, SCHEMA_VERSION, Store

    db = tmp_path / "whetstone.db"
    with sqlite3.connect(db) as conn:  # a database from before versioning: schema 1, user_version 0
        conn.executescript(MIGRATIONS[0])
        conn.executemany("INSERT INTO reveals VALUES ('m/01', 'hint-0', ?)", [("2026-10-01T10:00:00",), ("2026-10-02T10:00:00",)])

    store = Store(db)
    assert store.schema_version() == SCHEMA_VERSION
    assert store.backup == tmp_path / "whetstone.db.v0.bak" and store.backup.exists(), "upgrades back up first"
    assert store.reveals("m/01") == ["hint-0"], "a re-read hint counts once"
    store.record_reveal("m/01", "hint-0")
    assert store.reveals("m/01") == ["hint-0"]
    assert Store(db).backup is None, "an up-to-date database is left alone"

    with sqlite3.connect(db) as conn:
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 1}")
    with pytest.raises(RuntimeError, match="newer Whetstone"):
        Store(db)


def test_doctor_reports_and_explains(tmp_path, monkeypatch, capsys):
    content = tmp_path / "content"
    content.mkdir()
    (content / "catalog.yaml").write_text(yaml.safe_dump(CATALOG))
    monkeypatch.setenv("WHETSTONE_CONTENT", str(content))
    monkeypatch.setenv("WHETSTONE_HOME", str(tmp_path / "my"))
    monkeypatch.setenv("REDIS_URL", "redis://localhost:1/0")

    code = main(["doctor"])
    out = capsys.readouterr().out
    assert code == 0, "warnings alone don't fail the check"
    assert "[ ! ] Your profile: not set up yet" in out and 'Ask your agent: "Set up my Whetstone profile."' in out
    assert "Shared content: 2 modules" in out
    assert "Redis at redis://localhost:1/0: not reachable" in out


def test_watch_streams_moments_and_note_reaches_the_app(tmp_path, monkeypatch, capsys):
    import threading
    import time

    from whetstone.store import Store

    q = tmp_path / "my/tracks/m/01-q"
    q.mkdir(parents=True)
    (q / "challenge.yaml").write_text("title: Q\n")
    monkeypatch.setenv("WHETSTONE_HOME", str(tmp_path / "my"))
    monkeypatch.setenv("WHETSTONE_CONTENT", str(tmp_path / "content"))
    store = Store(tmp_path / "my/whetstone.db")

    def learner():
        time.sleep(0.5)
        for n in (3, 5, 9):
            store.record_event("m/01-q", "edited", {"lines": n})
        store.record_event("m/01-q", "ran", {"mode": "run", "status": "failed", "passed": 1, "total": 3, "failing": ["test_x"]})

    threading.Thread(target=learner).start()
    assert main(["watch", "--for", "3", "--pause", "1"]) == 0
    events = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert [e["event"] for e in events] == ["watching", "paused", "ran"], "typing collapses into one paused event before the run"
    assert events[1]["lines"] == 9 and events[2]["failing"] == ["test_x"] and (events[2]["mode"], events[2]["pair"]) == ("run", "quiet")

    assert main(["note", "m/01-q", "What happens when two threads call get(7)?", "--line", "12"]) == 0
    assert store.notes("m/01-q") == [{**store.notes("m/01-q")[0], "line": 12, "text": "What happens when two threads call get(7)?"}]
    assert main(["note", "m/02-nope", "hi"]) == 1, "notes only go to real questions"

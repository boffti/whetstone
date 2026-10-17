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
    assert code == 0 and "This module is empty: write its first question." in out and "Stripe (practical-coding): Build a limiter." in out
    assert "question 1 of the module. Suggested: predict" in out, "the brief follows the module recipe"
    assert "The learner's AI handles: nothing listed in the profile." in out and "Pull a tests or review" not in out

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

    assert run("question", "new", "rate-limiter", "answer-again")[0] == 0
    meta = mine / ".staging/answer-again/challenge.yaml"
    meta.write_text(meta.read_text().replace("# variant_of: module/NN-slug", "variant_of: rate-limiter/01-answer"))
    code, out = run("question", "add", str(mine / ".staging/answer-again"), "--module", "rate-limiter")
    assert code == 0 and "Added rate-limiter/02-answer-again." in out, out
    code, out = run("question", "brief", "rate-limiter")
    assert "02-answer-again: Answer again (build, medium, variant of rate-limiter/01-answer)" in out
    assert "question 2 of the module" in out, "a variant re-tests an earlier slot; it does not advance the recipe"

    code, out = run("progress", "--json")
    assert json.loads(out)["types"] == {"build": 2, "predict": 0, "fix": 0, "review": 0, "tests": 0, "design": 0, "whiteboard": 0}
    assert "By type: build 2, predict 0, fix 0, review 0, tests 0, design 0, whiteboard 0." in run("progress")[1]

    code, out = run("path", "show", "staff", "--json")
    modules = {m["module"]: m for m in json.loads(out)["modules"]}
    assert [m for m in modules] == ["rate-limiter", "idempotent-api"]
    assert (modules["rate-limiter"]["built"], modules["rate-limiter"]["questions"]) == (True, 2)
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


def test_reviews_count_only_when_due_and_a_failed_one_pulls_the_next_in():
    def row(key, solve=None, solved_at=None, variant_of=None):
        return {"key": key, "solve": solve, "solved_at": solved_at, "variant_of": variant_of}

    def reviews(*variants):
        rows = [row("m/01-a", "clean", "2026-10-01T10:00:00")]
        rows += [row(f"m/0{i}-v", solve, at, variant_of="m/01-a") for i, (solve, at) in enumerate(variants, 2)]
        add_reviews(rows)
        a = rows[0]
        return a["mastered"], a["clean_reviews"], a["review_due"]

    assert reviews(("clean", "2026-10-01T15:00:00")) == (False, 0, "2026-10-04"), "a variant solved the same day is not a spaced review"
    assert reviews(("clean", "2026-10-03T09:00:00")) == (True, 1, "2026-10-24"), "a day early is close enough"
    assert reviews(("assisted", "2026-10-05T09:00:00")) == (False, 0, "2026-10-07"), "a failed review comes back in 2 days"
    assert reviews(("assisted", "2026-10-05T09:00:00"), ("clean", "2026-10-08T09:00:00")) == (True, 1, "2026-10-29"), (
        "a clean review after a failed one resumes the schedule"
    )
    long = [("clean", d) for d in ("2026-10-04", "2026-10-25", "2027-01-23", "2027-07-22", "2028-07-21")]
    assert reviews(*long[:3]) == (True, 3, "2027-07-22"), "reviews go on past 3 months: 6 months next"
    assert reviews(*long) == (True, 5, "2029-07-21"), "then yearly, for as long as sharpness keeps fading"


def test_assisted_original_with_a_clean_variant_is_reviewed_but_not_mastered():
    rows = [
        {"key": "m/01-a", "solve": "assisted", "solved_at": "2026-10-01T10:00:00", "variant_of": None},
        {"key": "m/02-v", "solve": "clean", "solved_at": "2026-10-04T10:00:00", "variant_of": "m/01-a"},
    ]
    add_reviews(rows)
    a = rows[0]
    assert (a["mastered"], a["clean_reviews"], a["review_due"]) == (False, 1, "2026-10-25")


def test_weekly_streak_forgives_one_missed_week(tmp_path):
    from datetime import date, timedelta

    from whetstone.store import Store

    store = Store(tmp_path / "w.db")
    today = date(2026, 10, 16)  # a Friday
    monday = today - timedelta(days=today.weekday())

    def practice(*days):
        with store._conn() as conn:
            for d in days:
                conn.execute(
                    "INSERT INTO runs (challenge, mode, status, passed, total, duration, code, day, created_at) VALUES ('m/01', 'run', 'failed', 0, 1, 0, '', ?, ?)",
                    (d.isoformat(), d.isoformat() + "T10:00:00"),
                )

    weeks_ago = lambda n, *offsets: [monday - timedelta(days=7 * n) + timedelta(days=o) for o in offsets]  # noqa: E731
    practice(*weeks_ago(3, 0, 1, 2), *weeks_ago(2, 0, 2, 4), *weeks_ago(0, 0, 1))  # week 1 ago was missed
    w = store.week(today)
    assert (w["this_week"], w["streak"], w["repaired"]) == (2, 2, True), "one missed week is forgiven"

    practice(*weeks_ago(0, 2))
    assert store.week(today)["streak"] == 3, "the current week counts once it reaches the target"

    store2 = Store(tmp_path / "w2.db")
    store, store2 = store2, store
    practice(*weeks_ago(4, 0, 1, 2), *weeks_ago(0, 0))  # weeks 1-3 ago missed
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


def test_doctor_warns_when_the_container_clock_is_utc():
    from whetstone.__main__ import _clock_check

    ok, what, fix = _clock_check("", in_container=True)
    assert ok is None and "UTC" in what and "inside the container" in what and "TZ=" in fix
    ok, what, _ = _clock_check("Nowhere/Nope", in_container=True)
    assert ok is None and "Nowhere/Nope" in what
    assert _clock_check("", in_container=False)[0] is True, "outside Docker the system clock is already local"


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


def test_brief_reads_ai_handles_from_the_profile(tmp_path, monkeypatch, capsys):
    content, mine = tmp_path / "content", tmp_path / "my"
    content.mkdir()
    (content / "catalog.yaml").write_text(yaml.safe_dump(CATALOG))
    mine.mkdir()
    monkeypatch.setenv("WHETSTONE_CONTENT", str(content))
    monkeypatch.setenv("WHETSTONE_HOME", str(mine))

    def brief(*ai_handles):
        (mine / "profile.md").write_text(f"---\nname: Sam\nai_handles: {list(ai_handles)}\n---\n")
        assert main(["question", "brief", "rate-limiter"]) == 0
        return capsys.readouterr().out

    out = brief("tests", "frontend")
    assert "The learner's AI handles: tests, frontend." in out
    assert "Pull a tests or review question forward to position 2 or 3" in out, "tests fade fastest, so they come before position 4"
    assert "question new rate-limiter <slug> --type <type>" in out
    assert "Pull a tests or review" not in brief("frontend", "CI and Docker"), "no thesis skill handed off: the recipe stands"
    assert "Pull a tests or review" in brief("PR review")

    assert main(["question", "brief", "rate-limiter", "--type", "tests"]) == 0
    out = capsys.readouterr().out
    assert "tests: requested. Follow the tests section of AUTHORING.md." in out and "Suggested:" not in out
    assert "question new rate-limiter <slug> --type tests" in out


def test_question_new_scaffolds_every_type(tmp_path, monkeypatch, capsys):
    """Each type's scaffold has the shape AUTHORING.md asks for and passes `question add` as it is."""
    content, mine = tmp_path / "content", tmp_path / "my"
    content.mkdir()
    (content / "catalog.yaml").write_text(yaml.safe_dump(CATALOG))
    monkeypatch.setenv("WHETSTONE_CONTENT", str(content))
    monkeypatch.setenv("WHETSTONE_HOME", str(mine))

    for kind in ("predict", "fix", "review", "tests", "design"):
        assert main(["question", "new", "m", kind, "--type", kind]) == 0
        stage = mine / ".staging" / kind
        assert yaml.safe_load((stage / "challenge.yaml").read_text())["type"] == kind
        starter = (stage / "starter.py").read_text()
        if kind in ("predict", "review", "tests"):
            assert (stage / "subject.py").exists(), f"{kind}: the code to read goes in subject.py"
        if kind == "predict":
            assert "ANSWERS = {" in starter and "..." in starter
        if kind == "review":
            assert "FINDINGS" in starter
        if kind == "tests":
            assert starter.count("def test_") == 1 and not (stage / "tests").exists(), "tests: one weak test, no tests/ folder"
        if kind == "design":
            assert "Options: ..." in starter and "GUARANTEE" in starter
        assert main(["question", "add", str(stage), "--module", "m"]) == 0, capsys.readouterr().out
    out = capsys.readouterr().out
    assert "Added m/05-design." in out

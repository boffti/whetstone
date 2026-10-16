import json

import yaml

from whetstone.__main__ import add_reviews, main

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

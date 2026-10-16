import io
import json

import yaml

from whetstone.__main__ import main, whiteboard_template
from whetstone.config import Settings
from whetstone.runner import WHITEBOARD_SECTIONS, check_whiteboard
from whetstone.server import RunBody, create_app
from whetstone.store import Store

CATALOG = {
    "problems": [
        {
            "id": "url-shortener",
            "title": "URL shortener",
            "summary": "Short codes that redirect fast.",
            "reports": [
                {"company": "Stripe", "round": "system-design", "question": "Design a link shortener."},
                {"company": "Uber", "round": "practical-coding", "question": "Encode and decode a URL."},
            ],
        },
        {
            "id": "ledger",
            "title": "Ledger",
            "summary": "Money that adds up.",
            "reports": [{"company": "Ramp", "round": "practical-coding"}],
        },
    ]
}
WORDS = "a strong design names its numbers, its keys and what happens when a part of it fails at peak load"
RUBRIC = {
    "points": [
        {"id": "unique-codes", "section": "Deep dives", "must": True, "point": "Codes stay unique without one id server."},
        {"id": "cached-reads", "section": "High-level design", "must": True, "point": "Redirects are served from a cache."},
        {"id": "redirect-status", "section": "API", "must": True, "point": "A 302 keeps click counts right."},
        {"id": "expiry", "section": "Data model", "point": "Links can expire."},
        {"id": "hot-links", "section": "Failure modes", "point": "A hot link does not melt one shard."},
    ]
}


def make_board(stage):
    for rel, body in whiteboard_template().items():
        (stage / rel).parent.mkdir(parents=True, exist_ok=True)
        (stage / rel).write_text(body.format(title="Short links for a launch"))
    design = "# Short links\n\n" + "".join(f"## {name}\n\n{WORDS}.\n\n" for name in WHITEBOARD_SECTIONS)
    (stage / "solution.md").write_text(design + "```mermaid\nflowchart LR\n  client --> api\n```\n")
    (stage / "rubric.yaml").write_text(yaml.safe_dump(RUBRIC))
    return design


def grade(points, summary="Solid read path; ids need work."):
    return json.dumps({"summary": summary, "points": points})


def test_a_system_design_is_checked_by_section_and_solved_only_by_the_agents_grade(tmp_path, monkeypatch, capsys):
    content, mine = tmp_path / "content", tmp_path / "my"
    content.mkdir()
    (content / "catalog.yaml").write_text(yaml.safe_dump(CATALOG))
    monkeypatch.setenv("WHETSTONE_CONTENT", str(content))
    monkeypatch.setenv("WHETSTONE_HOME", str(mine))

    def run(*args, stdin=""):
        monkeypatch.setattr("sys.stdin", io.StringIO(stdin))
        code = main(list(args))
        out = capsys.readouterr()
        return code, out.out + out.err

    stage = tmp_path / "short-links"
    design = make_board(stage)
    code, out = run("question", "add", str(stage), "--module", "url-shortener")
    assert code == 0, out
    key = "url-shortener/01-short-links"
    stage = mine / "tracks" / key  # filing moves the folder

    # The section check names what is empty, and a full design passes it.
    starter = check_whiteboard((stage / "starter.md").read_text())
    assert starter.status == "failed" and "Add a '## Requirements' section" not in str(starter.tests)
    assert "has 0 words" in starter.tests[0].message
    assert check_whiteboard(design).tests[-1].outcome == "failed", "a design needs one diagram"

    settings = Settings(content, mine, "redis://localhost:1/0", None, "", 10)
    app = create_app(settings)
    endpoint = {r.path: r.endpoint for r in app.routes if hasattr(r, "endpoint")}
    track, cid = key.split("/")
    full = (stage / "solution.md").read_text()
    ran = endpoint["/api/challenges/{track}/{cid}/run"](track, cid, RunBody(code=full, mode="submit"))
    assert ran["status"] == "passed" and not ran["first_solve"], "filling every section never solves a design"

    # A grade must cover every rubric point, and a gap needs a question for the learner.
    code, out = run("grade", key, stdin=grade({"unique-codes": {"verdict": "covered"}}))
    assert code == 1 and "cached-reads has no verdict" in out
    gaps = {pid: {"verdict": "covered", "quote": "leases blocks of ids"} for pid in ("unique-codes", "cached-reads", "expiry", "hot-links")}
    code, out = run("grade", key, stdin=grade(gaps | {"redirect-status": {"verdict": "missing"}}))
    assert code == 1 and "needs a note" in out

    gaps["redirect-status"] = {"verdict": "missing", "note": "A browser caches a 301. What does that do to your counts?"}
    code, out = run("grade", key, stdin=grade(gaps))
    assert code == 0 and "1 must-have still open: redirect-status" in out
    assert key not in Store(settings.db_path).solved_keys()

    # Like a hidden test, a missed point shows only the agent's question until the learner solves it.
    review = endpoint["/api/challenges/{track}/{cid}/review"](track, cid)["review"]
    missed = next(p for p in review["points"] if p["id"] == "redirect-status")
    assert missed["point"] == "" and missed["note"].startswith("A browser caches")
    assert review["covered"] == 4 and not review["passed"]

    gaps["redirect-status"] = {"verdict": "covered", "quote": "302, so every click reaches us"}
    code, out = run("grade", key, stdin=grade(gaps))
    assert code == 0 and "Every must-have is covered: solved." in out
    after = endpoint["/api/challenges/{track}/{cid}/review"](track, cid)
    assert after["solved"] and all(p["point"] for p in after["review"]["points"])

    # The Design page lists system design prompts only, with the learner's design question.
    prompts = endpoint["/api/design"]()["prompts"]
    assert [p["id"] for p in prompts] == ["url-shortener"]
    assert prompts[0]["reports"] == 1 and prompts[0]["companies"] == ["Stripe"]
    assert prompts[0]["questions"][0] | {"status": "x"} == {
        "key": key,
        "title": "Short links for a launch",
        "status": "x",
        "covered": 5,
        "points": 5,
    }

    code, out = run("grade", "nope/01-x", stdin="{}")
    assert code == 1

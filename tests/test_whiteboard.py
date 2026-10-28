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


def test_a_whiteboard_drawing_reaches_the_agent_as_mermaid(tmp_path, monkeypatch, capsys):
    """The learner draws in Excalidraw; the check, `draft` and the preview read it as Mermaid."""
    from whetstone.runner import drawing_mermaid
    from whetstone.server import DrawingBody

    drawing = [
        {"id": "a", "type": "rectangle", "x": 0, "y": 0, "width": 100, "height": 50},
        {"id": "ta", "type": "text", "text": "Redirect service", "containerId": "a"},
        {"id": "b", "type": "ellipse", "x": 300, "y": 0, "width": 100, "height": 50, "frameId": "f"},
        {"id": "tb", "type": "text", "text": "Redis", "x": 320, "y": 10, "width": 40, "height": 20},
        {"id": "f", "type": "frame", "name": "Region A"},
        {"id": "user", "type": "text", "text": "Visitor", "x": -300, "y": 10, "width": 80, "height": 25},
        {"id": "in", "type": "arrow", "x": -210, "y": 20, "points": [[0, 0], [200, 0]]},
        {"id": "read", "type": "arrow", "strokeStyle": "dashed", "startBinding": {"elementId": "a"}, "endBinding": {"elementId": "b"}},
        {"id": "lr", "type": "text", "text": "GET code", "containerId": "read"},
        {"id": "half", "type": "arrow", "startBinding": {"elementId": "b"}},
        {"id": "aside", "type": "text", "text": "TTL 5 s", "x": 900, "y": 900, "width": 50, "height": 20},
        {"id": "gone", "type": "rectangle", "isDeleted": True},
    ]
    mermaid, notes = drawing_mermaid(drawing)
    assert mermaid.splitlines() == [
        "flowchart LR",
        '  subgraph f1["Region A"]',
        '    n3(["Redis"])',
        "  end",
        '  n1["Visitor"]',
        '  n2["Redirect service"]',
        "  n1 --> n2",
        '  n2 -.->|"GET code"| n3',
    ], "free text an arrow points at becomes a node; text drawn on a shape names it"
    assert notes == ["an arrow at 'Redis' whose other end is attached to nothing", "text on the board: 'TTL 5 s'"]
    assert drawing_mermaid([]) == ("", [])

    content, mine = tmp_path / "content", tmp_path / "my"
    content.mkdir()
    (content / "catalog.yaml").write_text(yaml.safe_dump(CATALOG))
    monkeypatch.setenv("WHETSTONE_CONTENT", str(content))
    monkeypatch.setenv("WHETSTONE_HOME", str(mine))
    make_board(tmp_path / "short-links")
    assert main(["question", "add", str(tmp_path / "short-links"), "--module", "url-shortener"]) == 0
    capsys.readouterr()

    settings = Settings(content, mine, "redis://localhost:1/0", None, "", 10)
    endpoint = {r.path: r.endpoint for r in create_app(settings).routes if hasattr(r, "endpoint")}
    path = "/api/challenges/{track}/{cid}/drawing"
    text = "".join(f"## {name}\n\n{WORDS}.\n\n" for name in WHITEBOARD_SECTIONS)  # no mermaid block
    run = endpoint["/api/challenges/{track}/{cid}/run"]
    assert run("url-shortener", "01-short-links", RunBody(code=text))["tests"][-1]["outcome"] == "failed"

    class Req:  # require_json only reads the content type
        headers = {"content-type": "application/json"}

    put = next(r.endpoint for r in create_app(settings).routes if getattr(r, "path", "") == path and "PUT" in r.methods)
    put("url-shortener", "01-short-links", DrawingBody(elements=drawing), Req())
    assert run("url-shortener", "01-short-links", RunBody(code=text))["tests"][-1]["outcome"] == "passed", "a drawn diagram counts"

    assert main(["draft", "url-shortener/01-short-links"]) == 0
    out = capsys.readouterr().out
    assert "## The learner's whiteboard drawing, as Mermaid" in out and '-.->|"GET code"|' in out
    assert "- Also on the board: text on the board: 'TTL 5 s'" in out


def test_sections_parse_in_linear_time_on_hostile_input():
    """A design is the learner's text. The old regexes took minutes on a long run of spaces in a
    heading or on many unclosed comments; the scan must stay fast and keep the same sections."""
    import time

    from whetstone.runner import whiteboard_sections

    assert whiteboard_sections("## A\n<!-- gone -->kept\n## B ##\r\nx <!-- open\n") == {"a": "\nkept\n", "b": "\nx <!-- open\n"}
    started = time.perf_counter()
    for text in ("<!--" * 50_000, "## " + " " * 50_000 + "x" + " " * 50_000, "## " + "#" * 20_000 + " " * 20_000 + "x"):
        whiteboard_sections(text)
    assert time.perf_counter() - started < 1, "section parsing must stay linear"

import yaml

from whetstone.config import Settings
from whetstone.content import LearningPath, save_path
from whetstone.server import LOCAL_HOSTS, create_app, is_local_request
from whetstone.store import Store


def test_api_paths_lists_modules_in_order_with_progress(tmp_path):
    content = tmp_path / "content"
    mine = tmp_path / "my"
    content.mkdir()
    for q in ("01-core", "02-burst"):
        (mine / "tracks/rate-limiter" / q).mkdir(parents=True)
        (mine / "tracks/rate-limiter" / q / "challenge.yaml").write_text(f"title: {q}\n")
    (content / "catalog.yaml").write_text(
        yaml.safe_dump(
            {
                "problems": [
                    {"id": "web-crawler", "title": "Web crawler", "summary": "Crawl one host.", "reports": [{"company": "Anthropic"}]},
                ]
            }
        )
    )
    save_path(
        content / "paths",
        LearningPath(
            "staff", "Staff", "Design reliable systems", ["web-crawler", "rate-limiter"], domain="Foundations", companies=["Stripe"]
        ),
    )
    settings = Settings(content, mine, "redis://localhost:1/0", None, "", 10)
    Store(settings.db_path).record_run("rate-limiter/01-core", "submit", "passed", 1, 1, 0.1, "code")

    app = create_app(settings)
    paths = next(r for r in app.routes if getattr(r, "path", "") == "/api/paths").endpoint()

    assert [(p["id"], p["goal"], p["domain"], p["companies"]) for p in paths] == [
        ("staff", "Design reliable systems", "Foundations", ["Stripe"])
    ]
    assert paths[0]["modules"] == [
        {
            "module": "web-crawler",
            "title": "Web crawler",
            "summary": "Crawl one host.",
            "reports": 1,
            "built": False,
            "questions": 0,
            "planned": 5,
            "solved": 0,
            "next": None,
        },
        {
            "module": "rate-limiter",
            "title": "Rate limiter",
            "summary": "",
            "reports": 0,
            "built": True,
            "questions": 2,
            "planned": 5,
            "solved": 1,
            "next": "02-burst",
        },
    ]


def test_only_local_requests_are_answered():
    ok = [
        ("localhost:8000", None),
        ("127.0.0.1:8000", "http://127.0.0.1:8000"),
        ("[::1]:8000", "http://[::1]:8000"),
        ("localhost", "http://localhost:8000"),
    ]
    blocked = [
        ("evil.example:8000", None),  # DNS rebinding: an outside name pointed at 127.0.0.1
        ("localhost:8000", "https://evil.example"),  # another site's page posting to the app
        ("localhost.evil.example", None),
        ("", None),
    ]
    assert all(is_local_request(h, o, LOCAL_HOSTS) for h, o in ok)
    assert not any(is_local_request(h, o, LOCAL_HOSTS) for h, o in blocked)
    assert is_local_request("devbox:8000", None, LOCAL_HOSTS | {"devbox"}), "WHETSTONE_ALLOWED_HOSTS adds names"


def test_hints_and_solution_open_in_order(tmp_path):
    """A hint unlocks after a test run since the last one; the solution after a solve or a give-up."""
    from fastapi.testclient import TestClient

    q = tmp_path / "my/tracks/m/01-q"
    q.mkdir(parents=True)
    (q / "challenge.yaml").write_text("title: Q\n")
    (q / "hints.md").write_text("one\n\n---\n\ntwo\n\n---\n\nthree\n\n---\n\nfour\n")
    (q / "solution.py").write_text("ANSWER = 1\n")
    (tmp_path / "content").mkdir()
    settings = Settings(tmp_path / "content", tmp_path / "my", "redis://localhost:1/0", None, "", 10)
    client = TestClient(create_app(settings), base_url="http://localhost")

    assert client.get("/api/challenges/m/01-q/hints/1").status_code == 404, "hints open in order"
    assert client.get("/api/challenges/m/01-q/hints/0").status_code == 200
    assert client.get("/api/challenges/m/01-q/hints/1").status_code == 409, "the next hint needs a test run first"
    assert client.get("/api/challenges/m/01-q/hints/0").status_code == 200, "re-reading an opened hint is free"
    Store(settings.db_path).record_run("m/01-q", "run", "failed", 0, 1, 0.1, "code")
    assert client.get("/api/challenges/m/01-q/hints/1").status_code == 200

    assert client.post("/api/challenges/m/01-q/solution", json={}).status_code == 409
    assert client.post("/api/challenges/m/01-q/solution", json={"give_up": True}).json() == {"code": "ANSWER = 1\n"}
    assert Store(settings.db_path).reveals("m/01-q") == ["hint-0", "hint-1", "solution"]


def test_predictions_are_scored_and_explanations_kept(tmp_path):
    """A guess before a run is scored against the result; an explanation after a solve is kept."""
    import shutil

    from fastapi.testclient import TestClient

    from whetstone.config import EXAMPLE

    shutil.copytree(EXAMPLE, tmp_path / "my/tracks/m/01-memo")
    (tmp_path / "content").mkdir()
    settings = Settings(tmp_path / "content", tmp_path / "my", "redis://localhost:1/0", None, "", 60)
    client = TestClient(create_app(settings), base_url="http://localhost")
    q = client.get("/api/challenges/m/01-memo").json()
    names = [t["name"] for t in q["visible_tests"]]
    assert names == ["test_returns_correct_values", "test_computes_each_input_once", "test_stats_count_hits_and_misses"]

    starter = (EXAMPLE / "starter.py").read_text()
    guess = {"tests": {"test_returns_correct_values": True, "test_computes_each_input_once": True}}
    r = client.post("/api/challenges/m/01-memo/run", json={"code": starter, "mode": "run", "prediction": guess}).json()
    assert (r["prediction"]["correct"], r["prediction"]["total"]) == (1, 2), "the starter computes twice, so one guess was wrong"

    solution = (EXAMPLE / "solution.py").read_text()
    r = client.post(
        "/api/challenges/m/01-memo/run", json={"code": solution, "mode": "submit", "prediction": {"all_pass": True, "confidence": 4}}
    ).json()
    assert r["first_solve"] and (r["prediction"]["correct"], r["prediction"]["confidence"]) == (1, 4)

    assert client.post(
        "/api/challenges/m/01-memo/explanation", json={"test": "test_errors_are_not_cached", "text": "I save only after compute returns."}
    ).json() == {"saved": True}
    assert Store(settings.db_path).explanation("m/01-memo")["text"] == "I save only after compute returns."
    numbers = client.get("/api/dashboard").json()["numbers"]
    assert (numbers["predict_now"], numbers["predicted"]) == (67, 3), "2 of 3 guesses right"


def test_agent_inbox_round_trip(tmp_path, monkeypatch, capsys):
    """The app queues a build; the learner's agent claims it and reports back; the app sees it."""
    import json

    import yaml
    from fastapi.testclient import TestClient

    from whetstone.__main__ import main

    content, mine = tmp_path / "content", tmp_path / "my"
    content.mkdir()
    mine.mkdir()
    (content / "catalog.yaml").write_text(
        yaml.safe_dump({"problems": [{"id": "rate-limiter", "title": "Rate limiter", "summary": "s", "reports": []}]})
    )
    monkeypatch.setenv("WHETSTONE_CONTENT", str(content))
    monkeypatch.setenv("WHETSTONE_HOME", str(mine))
    settings = Settings(content, mine, "redis://localhost:1/0", None, "", 10)
    client = TestClient(create_app(settings), base_url="http://localhost")

    assert client.post("/api/requests", json={"kind": "build", "target": "nope"}).status_code == 400
    first = client.post("/api/requests", json={"kind": "build", "target": "Rate Limiter"}).json()
    again = client.post("/api/requests", json={"kind": "build", "target": "rate-limiter"}).json()
    assert first["target"] == "rate-limiter" and again["id"] == first["id"], "an open request is reused, not duplicated"
    assert client.get("/api/requests").json()["agent"]["connected"] is False

    assert main(["watch", "--for", "1"]) == 0
    events = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert events[1]["event"] == "requested" and events[1]["ask"] == "Build the next Whetstone question for the rate-limiter module."
    assert client.get("/api/requests").json()["agent"]["connected"] is True, "watching counts as connected"

    assert main(["request", "claim", str(first["id"])]) == 0
    assert main(["request", "claim", str(first["id"])]) == 1, "a claimed request cannot be claimed twice"
    assert main(["request", "done", str(first["id"]), "--result", "rate-limiter/01-token-bucket"]) == 0
    done = client.get("/api/requests").json()["requests"][0]
    assert (done["status"], done["result"]) == ("done", "rate-limiter/01-token-bucket")


def test_learner_edits_interests_and_keeps_their_profile_text(tmp_path):
    import yaml
    from fastapi.testclient import TestClient

    from whetstone.content import load_profile

    content, mine = tmp_path / "content", tmp_path / "my"
    (content / "paths").mkdir(parents=True)
    mine.mkdir()
    (content / "catalog.yaml").write_text(
        yaml.safe_dump({"problems": [{"id": "rate-limiter", "title": "Rate limiter", "summary": "s", "reports": []}]})
    )
    (content / "paths" / "staff.yaml").write_text(yaml.safe_dump({"title": "Staff", "modules": ["rate-limiter"]}))
    (mine / "profile.md").write_text("---\nname: Sam\nfocus: []\n---\n\n# Learner profile\n\nWrites Go at work.\n")
    settings = Settings(content, mine, "redis://localhost:1/0", None, "", 10)
    client = TestClient(create_app(settings), base_url="http://localhost")

    assert client.put("/api/profile", json={"focus": ["nope"]}).status_code == 400
    saved = client.put("/api/profile", json={"focus": ["Rate Limiter"], "targets": ["Stripe", "Stripe"], "paths": ["staff"]}).json()
    assert (saved["name"], saved["focus"], saved["targets"], saved["paths"]) == ("Sam", ["rate-limiter"], ["Stripe"], ["staff"])
    assert "Writes Go at work." in (mine / "profile.md").read_text(), "the free text below the header is kept"
    assert load_profile(mine / "profile.md")["focus"] == ["rate-limiter"]

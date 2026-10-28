import yaml

from whetstone.config import Settings
from whetstone.content import LearningPath, save_path
from whetstone.server import LOCAL_HOSTS, create_app, is_local_request, request_ask
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
        ("localhost", "http://localhost"),
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


def test_origin_port_must_match_host_port():
    """Another local server (a dev server at :9000, say) is a different origin, not this app."""
    assert not is_local_request("localhost:8000", "http://localhost:9000", LOCAL_HOSTS)
    assert not is_local_request("localhost:8000", "http://localhost", LOCAL_HOSTS), "no port means the default, 80"
    assert not is_local_request("localhost:abc", None, LOCAL_HOSTS), "a bad port is not a local request"
    assert is_local_request("localhost:8000", "http://LOCALHOST:8000", LOCAL_HOSTS), "host names are case-insensitive"


def test_requests_say_whether_they_finished_recently(tmp_path):
    """The app shows a just-finished build; the server decides what "just" means, so the browser
    does not compare its clock with the container's (which runs on UTC)."""
    import sqlite3
    from datetime import datetime, timedelta

    from fastapi.testclient import TestClient

    content, mine = tmp_path / "content", tmp_path / "my"
    content.mkdir()
    mine.mkdir()
    (content / "catalog.yaml").write_text(
        yaml.safe_dump({"problems": [{"id": "rate-limiter", "title": "Rate limiter", "summary": "s", "reports": []}]})
    )
    settings = Settings(content, mine, "redis://localhost:1/0", None, "", 10)
    client = TestClient(create_app(settings), base_url="http://localhost")
    r = client.post("/api/requests", json={"kind": "build", "target": "rate-limiter"}).json()

    def flags():
        row = client.get("/api/requests").json()["requests"][0]
        return row["recent"], row["stale"]

    def age(minutes):
        with sqlite3.connect(settings.db_path) as conn:
            then = (datetime.now() - timedelta(minutes=minutes)).isoformat(timespec="seconds")
            conn.execute("UPDATE requests SET updated_at = ? WHERE id = ?", (then, r["id"]))

    assert flags() == (True, False)
    age(11)
    assert flags() == (False, False)
    age(16)
    assert flags() == (False, True), "a claim untouched for 15 minutes is an agent that stopped"


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
    assert main(["request", "claim", str(first["id"])]) == 0, "an agent that died mid-build replays its claim"
    assert "orphaned" in capsys.readouterr().out
    assert main(["request", "done", str(first["id"]), "--result", "rate-limiter/01-nope"]) == 1, "a bad key would be a dead Start link"
    (mine / "tracks/rate-limiter/01-token-bucket").mkdir(parents=True)
    (mine / "tracks/rate-limiter/01-token-bucket/challenge.yaml").write_text("title: Token bucket\n")
    assert main(["request", "done", str(first["id"]), "--result", "rate-limiter/01-token-bucket"]) == 0
    done = client.get("/api/requests").json()["requests"][0]
    assert (done["status"], done["result"]) == ("done", "rate-limiter/01-token-bucket")


def test_claim_checks_the_status_inside_the_update(tmp_path):
    """The guard is in the UPDATE itself: a cancel that commits while the claim waits for the
    write lock wins, so a claim can never land on a request that just stopped being queued."""
    import sqlite3
    import threading
    import time

    store = Store(tmp_path / "w.db")
    r = store.add_request("build", "rate-limiter")
    hold = sqlite3.connect(store.path, timeout=10)
    hold.execute("UPDATE requests SET status = 'cancelled' WHERE id = ?", (r["id"],))  # takes the write lock
    got = {}
    t = threading.Thread(target=lambda: got.update(row=store.update_request(r["id"], "claimed", only_from=("queued",))))
    t.start()
    time.sleep(0.5)  # the claim has read 'queued' and waits for the lock
    hold.commit()
    t.join()
    hold.close()
    assert got["row"] is None
    assert store.requests()[0]["status"] == "cancelled"


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


def test_a_predict_lesson_keeps_its_misconceptions_until_the_first_submit(tmp_path):
    """The misconceptions name what the hidden predictions test, so they open with the first Submit (or a reveal)."""
    from fastapi.testclient import TestClient

    from whetstone.__main__ import scaffold

    q = tmp_path / "my/tracks/m/01-q"
    for name, text in scaffold("predict").items():
        (q / name).parent.mkdir(parents=True, exist_ok=True)
        (q / name).write_text(text)
    (q / "lesson.md").write_text(
        "## The idea\n\nRead first.\n\n## Misconceptions\n\n- a missing key has tokens\n\n## Interview angle\n\nNext.\n"
    )
    (tmp_path / "content").mkdir()
    settings = Settings(tmp_path / "content", tmp_path / "my", "redis://localhost:1/0", None, "", 60)
    client = TestClient(create_app(settings), base_url="http://localhost")

    html = client.get("/api/challenges/m/01-q").json()["lesson_html"]
    assert "a missing key has tokens" not in html and "Opens after your first Submit" in html and "Next." in html
    starter = (q / "starter.py").read_text()
    assert "lesson_html" not in client.post("/api/challenges/m/01-q/run", json={"code": starter, "mode": "run"}).json()
    r = client.post("/api/challenges/m/01-q/run", json={"code": starter, "mode": "submit"}).json()
    assert r["status"] == "failed" and "a missing key has tokens" in r["lesson_html"], "the first Submit opens them, right or wrong"
    assert "a missing key has tokens" in client.get("/api/challenges/m/01-q").json()["lesson_html"]


def test_learner_rates_a_question_after_submit(tmp_path):
    """One tap after Submit: too easy, right, too hard or artificial. The last rating wins, and the
    agent sees it in progress and in the next brief."""
    import shutil

    from fastapi.testclient import TestClient

    from whetstone.config import EXAMPLE
    from whetstone.content import load_tracks
    from whetstone.store import progress_rows

    shutil.copytree(EXAMPLE, tmp_path / "my/tracks/m/01-memo")
    (tmp_path / "content").mkdir()
    settings = Settings(tmp_path / "content", tmp_path / "my", "redis://localhost:1/0", None, "", 60)
    client = TestClient(create_app(settings), base_url="http://localhost")
    assert client.get("/api/challenges/m/01-memo").json()["rating"] is None
    assert client.post("/api/challenges/m/01-memo/rating", json={"rating": "too-hard"}).json() == {"saved": True}
    assert client.post("/api/challenges/m/01-memo/rating", json={"rating": "meh"}).status_code == 422
    assert client.get("/api/challenges/m/01-memo").json()["rating"] == "too-hard"
    store = Store(settings.db_path)
    assert store.rating("m/01-memo") == "too-hard"
    assert progress_rows(store, load_tracks(settings.tracks_dir))[0]["rating"] == "too-hard"
    client.post("/api/challenges/m/01-memo/rating", json={"rating": "right"})
    assert store.rating("m/01-memo") == "right"


def test_a_request_carries_what_it_is_framed_for(tmp_path):
    """Prepare asks: your work, a company you are preparing for, or a domain. The choice travels
    with the request and reaches the agent in its ask. The same module framed two ways is two jobs."""
    from fastapi.testclient import TestClient

    content, mine = tmp_path / "content", tmp_path / "my"
    content.mkdir()
    mine.mkdir()
    (content / "catalog.yaml").write_text(
        yaml.safe_dump({"problems": [{"id": "job-scheduler", "title": "Job scheduler", "summary": "s", "reports": []}]})
    )
    client = TestClient(create_app(Settings(content, mine, "redis://localhost:1/0", None, "", 10)), base_url="http://localhost")
    uber = client.post("/api/requests", json={"kind": "design", "target": "job-scheduler", "framing": "company:Uber"}).json()
    assert uber["framing"] == "company:Uber"
    mine_ = client.post("/api/requests", json={"kind": "design", "target": "job-scheduler", "framing": "work"}).json()
    assert mine_["id"] != uber["id"], "a different framing is a different job"
    again = client.post("/api/requests", json={"kind": "design", "target": "job-scheduler", "framing": "company:Uber"}).json()
    assert again["id"] == uber["id"], "the same framing reuses the open request"
    assert client.post("/api/requests", json={"kind": "build", "target": "job-scheduler", "framing": "vendor:x"}).status_code == 422
    assert request_ask(uber).endswith("Frame it for Uber: I'm preparing for their interviews.")
    assert request_ask({**uber, "framing": None}).endswith("module."), "an older request reads as before"
    again_for = {"kind": "variant", "target": "job-scheduler/01-end-of-day-jobs", "framing": "company:Uber"}
    assert request_ask(again_for) == (
        "Build a Whetstone variant of job-scheduler/01-end-of-day-jobs: the same idea on a new surface. "
        "Frame it for Uber: I'm preparing for their interviews."
    ), "Prepare again for... is a variant with the new framing"

import yaml

from whetstone.config import Settings
from whetstone.content import LearningPath, save_path
from whetstone.server import create_app
from whetstone.store import Store


def test_api_paths_lists_modules_in_order_with_progress(tmp_path):
    content = tmp_path / "content"
    mine = tmp_path / "my"
    content.mkdir()
    for q in ("01-core", "02-burst"):
        (mine / "tracks/rate-limiter" / q).mkdir(parents=True)
        (mine / "tracks/rate-limiter" / q / "challenge.yaml").write_text(f"title: {q}\n")
    (content / "catalog.yaml").write_text(yaml.safe_dump({"problems": [
        {"id": "web-crawler", "title": "Web crawler", "summary": "Crawl one host.", "reports": [{"company": "Anthropic"}]},
    ]}))
    save_path(content / "paths", LearningPath("staff", "Staff", "Design reliable systems", ["web-crawler", "rate-limiter"],
                                              domain="Foundations", companies=["Stripe"]))
    settings = Settings(content, mine, "redis://localhost:1/0", None, "", 10)
    Store(settings.db_path).record_run("rate-limiter/01-core", "submit", "passed", 1, 1, 0.1, "code")

    app = create_app(settings)
    paths = next(r for r in app.routes if getattr(r, "path", "") == "/api/paths").endpoint()

    assert [(p["id"], p["goal"], p["domain"], p["companies"]) for p in paths] == [("staff", "Design reliable systems", "Foundations", ["Stripe"])]
    assert paths[0]["modules"] == [
        {"module": "web-crawler", "title": "Web crawler", "summary": "Crawl one host.", "reports": 1,
         "built": False, "questions": 0, "solved": 0, "next": None},
        {"module": "rate-limiter", "title": "Rate limiter", "summary": "", "reports": 0,
         "built": True, "questions": 2, "solved": 1, "next": "02-burst"},
    ]

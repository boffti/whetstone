import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from check_content import all_problems, check_catalog, check_paths  # noqa: E402


def test_shared_content_is_valid():
    assert all_problems() == []


def test_checker_catches_common_mistakes(tmp_path):
    catalog = {
        "problems": [
            {
                "id": "Bad_ID",
                "title": "",
                "summary": "",
                "track": "concurrency-caching",
                "report_count": 1,
                "reports": [{"company": "X", "question": "Q", "round": "chat", "confidence": "sure", "sources": ["ftp://x"]}],
            }
        ]
    }
    found = "\n".join(check_catalog(catalog))
    for message in (
        "kebab-case",
        "needs a title",
        "needs a summary",
        "must not link a learner's track",
        "round must be",
        "confidence must be",
        "http(s) source",
    ):
        assert message in found, message

    (tmp_path / "p.yaml").write_text(yaml.safe_dump({"title": "T", "goal": "G", "domain": "D", "modules": ["nope", "nope"]}))
    found = "\n".join(check_paths(tmp_path, set()))
    assert "unknown module 'nope'" in found and "listed twice" in found

from whetstone.config import EXAMPLE, Settings
from whetstone.content import load_challenge
from whetstone.runner import run_tests, validate_challenge


def test_shipped_example_question_is_valid(tmp_path):
    """examples/memoize is the quality bar agents copy: it must pass its own check."""
    settings = Settings(tmp_path / "content", tmp_path / "my", "redis://localhost:1/0", None, "", 60)
    result = validate_challenge(load_challenge(EXAMPLE, "examples"), settings, strict=True)
    assert result.ok, result.problems
    assert not [n for n in result.notes if "hints.md" in n], "the example follows the current format"


def test_failure_details_are_plain_text(tmp_path, monkeypatch):
    """A FORCE_COLOR in the app's environment must not put escape codes into the results panel."""
    monkeypatch.setenv("FORCE_COLOR", "1")
    settings = Settings(tmp_path / "content", tmp_path / "my", "redis://localhost:1/0", None, "", 60)
    question = load_challenge(EXAMPLE, "examples")
    report = run_tests(question, question.read("starter.py"), "run", settings)
    assert report.failed and "#x1B" not in str(report.to_dict()) and "\x1b" not in report.output

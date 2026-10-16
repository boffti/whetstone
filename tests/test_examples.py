from whetstone.config import EXAMPLE, Settings
from whetstone.content import load_challenge
from whetstone.runner import validate_challenge


def test_shipped_example_question_is_valid(tmp_path):
    """examples/memoize is the quality bar agents copy: it must pass its own check."""
    settings = Settings(tmp_path / "content", tmp_path / "my", "redis://localhost:1/0", None, "", 60)
    result = validate_challenge(load_challenge(EXAMPLE, "examples"), settings)
    assert result.ok, result.problems

from solution import FINDINGS

# The seeded defects: line in subject.py -> category. A finding counts within 2 lines.
SEEDED = {50: "not-idempotent", 52: "missing-timeout", 69: "wrong-boundary"}
TOLERANCE = 2


def _matches(finding: tuple[int, str], line: int, category: str) -> bool:
    found_line, found_category = finding
    return abs(found_line - line) <= TOLERANCE and found_category == category


def test_every_seeded_defect_is_found():
    # Count the misses, never name them: the categories are the answer, and hints are where help is given.
    missed = [cat for line, cat in SEEDED.items() if not any(_matches(f, line, cat) for f in FINDINGS)]
    defects = "One defect" if len(missed) == 1 else f"{len(missed)} defects"
    assert not missed, (
        f"{defects} would still block this pull request. Take each promise in the docstrings and find the line that breaks it."
    )


def test_at_most_one_false_positive():
    extra = [f for f in FINDINGS if not any(_matches(f, line, cat) for line, cat in SEEDED.items())]
    assert len(extra) <= 1, f"{len(extra)} findings point at code that keeps its promise. Which of them would you defend in a real review?"

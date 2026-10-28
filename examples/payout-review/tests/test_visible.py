from pathlib import Path

from solution import FINDINGS

CATEGORIES = {"race", "not-idempotent", "missing-timeout", "wrong-boundary", "resource-leak", "unvalidated-input"}
SUBJECT_LINES = len((Path(__file__).resolve().parents[1] / "subject.py").read_text(encoding="utf-8").splitlines())


def _pairs() -> list[tuple]:
    return [f for f in FINDINGS if isinstance(f, tuple) and len(f) == 2]


def test_findings_are_line_and_category_pairs():
    assert FINDINGS, "List at least one finding: (line in subject.py, category)."
    assert len(_pairs()) == len(FINDINGS), "Each finding is a pair: (line, category)."
    assert all(isinstance(line, int) and isinstance(cat, str) for line, cat in _pairs()), "Each finding is (line number, category)."


def test_categories_come_from_the_list():
    unknown = sorted({cat for _, cat in _pairs()} - CATEGORIES)
    assert not unknown, f"Unknown categories: {', '.join(map(str, unknown))}. Use a name from the Categories list in the problem."


def test_lines_point_inside_subject():
    outside = [line for line, _ in _pairs() if not (isinstance(line, int) and 1 <= line <= SUBJECT_LINES)]
    assert not outside, f"Lines {outside} are not in subject.py, which has {SUBJECT_LINES} lines."

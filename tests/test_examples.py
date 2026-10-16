from whetstone.config import EXAMPLE, Settings
from whetstone.content import load_challenge
from whetstone.runner import run_tests, validate_challenge


def test_shipped_example_question_is_valid(tmp_path):
    """examples/memoize is the quality bar agents copy: it must pass its own check."""
    settings = Settings(tmp_path / "content", tmp_path / "my", "redis://localhost:1/0", None, "", 60)
    result = validate_challenge(load_challenge(EXAMPLE, "examples"), settings, strict=True)
    assert "mutants: the tests catch 3 of 3" in result.notes
    assert result.ok, result.problems
    assert not [n for n in result.notes if "hints.md" in n], "the example follows the current format"


def test_failure_details_are_plain_text(tmp_path, monkeypatch):
    """A FORCE_COLOR in the app's environment must not put escape codes into the results panel."""
    monkeypatch.setenv("FORCE_COLOR", "1")
    settings = Settings(tmp_path / "content", tmp_path / "my", "redis://localhost:1/0", None, "", 60)
    question = load_challenge(EXAMPLE, "examples")
    report = run_tests(question, question.read("starter.py"), "run", settings)
    assert report.failed and "#x1B" not in str(report.to_dict()) and "\x1b" not in report.output


def test_tests_questions_grade_the_learners_tests_by_the_bugs_they_catch(tmp_path):
    """examples/retry-tests: the learner writes tests; Submit runs them against hidden mutants."""
    settings = Settings(tmp_path / "content", tmp_path / "my", "redis://localhost:1/0", None, "", 60)
    question = load_challenge(EXAMPLE.parent / "retry-tests", "examples")
    assert validate_challenge(question, settings, strict=True).ok

    weak = run_tests(question, question.read("starter.py"), "submit", settings)
    survived = [t.label for t in weak.tests if t.outcome == "failed"]
    assert weak.status == "failed" and len(survived) == 4, "one happy-path test catches none of the 4 bugs"
    assert "catches the bug: backoff means waiting the same time between tries" in survived

    wrong = "from retry import retry\n\ndef test_wrong():\n    assert retry(lambda: 1, sleep=lambda s: None) == 2\n"
    report = run_tests(question, wrong, "run", settings)
    assert report.status == "failed" and "checks the wrong thing" in report.tests[0].message


def test_mutation_gate_rejects_tests_that_miss_a_bug(tmp_path):
    import shutil

    settings = Settings(tmp_path / "content", tmp_path / "my", "redis://localhost:1/0", None, "", 60)
    copy = tmp_path / "memoize"
    shutil.copytree(EXAMPLE, copy)
    # A mutant the tests cannot see: it only renames a local variable.
    blind = (
        (copy / "solution.py")
        .read_text()
        .replace("value = self._compute(n)", "result = self._compute(n)")
        .replace("self._cache[n] = value\n        return value", "self._cache[n] = result\n        return result")
    )
    (copy / "mutants/04-renamed.py").write_text('"""Misconception: none, this one behaves the same."""\n\n' + blind)
    result = validate_challenge(load_challenge(copy, "examples"), settings, strict=True)
    assert not result.ok and any("04-renamed.py survives" in p for p in result.problems)
    assert validate_challenge(load_challenge(copy, "examples"), settings).ok, "older questions only get a note"


def test_design_questions_check_the_design_note():
    from whetstone.runner import _design_note

    filled = '''"""
Options: a unique index, or a lock plus a cache.
Trade-off: the index survives restarts; the lock is faster.
Choice: the unique index.
Failure mode: a slow insert under heavy contention.
"""'''
    assert _design_note(filled).outcome == "passed"
    note = _design_note('"""\nOptions: ...\nChoice: lock\n"""')
    assert note.outcome == "failed" and "options, trade-off, failure mode" in note.message

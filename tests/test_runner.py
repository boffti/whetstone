"""The test run is a subprocess: it must not see the app's secrets, and a timeout must take
everything it started down with it."""

import os
import time

from whetstone.config import Settings
from whetstone.runner import _pytest


def settings(tmp_path):
    return Settings(tmp_path / "content", tmp_path / "my", "redis://localhost:1/0", None, "", 10)


def test_child_gets_an_allowlisted_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-secret")
    monkeypatch.setenv("FORCE_COLOR", "1")
    files = {
        "tests/test_env.py": (
            "import os\n"
            "def test_env():\n"
            "    assert 'ANTHROPIC_API_KEY' not in os.environ\n"
            "    assert 'FORCE_COLOR' not in os.environ\n"
            "    assert os.environ['PATH'] and os.environ['NO_COLOR']\n"
        )
    }
    tests, output, _ = _pytest(files, "tests", 30, settings(tmp_path))
    assert tests is not None and [t.outcome for t in tests] == ["passed"], output


def test_timeout_kills_what_the_run_started(tmp_path):
    pid_file = tmp_path / "grandchild.pid"
    files = {
        "tests/test_slow.py": (
            "import subprocess, sys, time\n"
            "def test_slow():\n"
            f"    child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
            f"    open({str(pid_file)!r}, 'w').write(str(child.pid))\n"
            "    time.sleep(60)\n"
        )
    }
    started = time.monotonic()
    tests, _, _ = _pytest(files, "tests", 2, settings(tmp_path))
    assert tests is None, "a run that overruns reports a timeout"
    assert time.monotonic() - started < 10, "the timeout is enforced, not the grandchild's sleep"
    pid = int(pid_file.read_text())
    for _ in range(20):  # init reaps the orphan after the kill; give it a moment
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            break
        time.sleep(0.1)
    else:
        os.kill(pid, 9)
        raise AssertionError("the grandchild outlived the run")


# ---------- What a failed run may show, and what `question check` says ----------
import json  # noqa: E402

import yaml  # noqa: E402

from whetstone.__main__ import scaffold  # noqa: E402
from whetstone.content import load_challenge  # noqa: E402
from whetstone.runner import run_tests, validate_challenge  # noqa: E402

HINTS = "one\n\n---\n\ntwo\n\n---\n\nthree\n\n---\n\nfour\n"
VISIBLE = "from solution import ANSWER\n\n\ndef test_answer():\n    assert ANSWER == 1\n"


def question(root, files, **meta):
    """A small question on disk: a build with ANSWER = 1, unless `files` says otherwise."""
    base = {
        "challenge.yaml": yaml.safe_dump({"title": "Q", "type": "build", **meta}),
        "lesson.md": "## The idea\n",
        "problem.md": "## Task\n",
        "hints.md": HINTS,
        "starter.py": "ANSWER = 0\n",
        "solution.py": "ANSWER = 1\n",
        "tests/test_visible.py": VISIBLE,
    }
    for name, text in (base | files).items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text)
    return load_challenge(root, "m")


def test_a_hidden_failure_shows_the_authors_message_and_no_values(tmp_path):
    """PEDAGOGY rule 7: a hidden failure reports its category, never the test body. pytest's
    rewritten `assert 99.8 == 100.2` is the answer key of a predict question."""
    q = question(
        tmp_path / "q",
        {
            "tests/test_hidden.py": 'def test_total_is_rounded():\n    assert 99.8 == 100.2, "The total drifts. Which step rounds too early?"\n'
        },
    )
    report = run_tests(q, "ANSWER = 1\n", "submit", settings(tmp_path))
    hidden = next(t for t in report.tests if t.hidden)
    assert (hidden.outcome, hidden.message, hidden.details) == ("failed", "The total drifts. Which step rounds too early?", "")
    assert "99.8" not in json.dumps(report.to_dict()) and "100.2" not in json.dumps(report.to_dict())


def test_a_visible_failure_keeps_its_trace(tmp_path):
    q = question(tmp_path / "q", {})
    report = run_tests(q, "ANSWER = 2\n", "run", settings(tmp_path))
    assert report.tests[0].outcome == "failed" and "assert 2 == 1" in report.tests[0].details


def test_predict_mutants_are_wrong_subjects_the_reference_answers_must_notice(tmp_path):
    files = scaffold("predict")
    blind = '"""Misconception: none, it behaves the same."""\n\n' + files["subject.py"].replace("left", "balance")
    answers = '"""Misconception: a wrong answer key is not a mutant."""\n\n' + files["solution.py"].replace("False", "True")
    q = question(tmp_path / "q", files | {"mutants/03-blind.py": blind, "mutants/04-answers.py": answers})
    result = validate_challenge(q, settings(tmp_path), strict=True)
    assert not result.ok and any("03-blind.py survives" in p for p in result.problems), result
    assert any("04-answers.py does not run in place of subject.py" in p for p in result.problems), result
    assert "mutants: the tests catch 2 of 4" in result.notes
    assert validate_challenge(q, settings(tmp_path)).ok, "older questions only get a note"


def test_the_predict_harness_blocks_the_shortcut_on_run_and_on_submit(tmp_path):
    q = question(tmp_path / "q", scaffold("predict"))
    assert "does_not_import" not in q.read("tests/test_hidden.py"), "the substring check is gone; conftest.py blocks the import itself"
    cheat = (
        "from subject import take\n\nb = {'k': 1}\ntake(b, 'k')\n"
        "ANSWERS = {'second_take_from_one_token': take(b, 'k'), 'take_from_a_missing_key': take({}, 'k')}\n"
    )
    for mode in ("run", "submit"):
        report = run_tests(q, cheat, mode, settings(tmp_path))
        assert report.status != "passed" and "runs the code it should predict" in json.dumps(report.to_dict()), (mode, report)
    sneaky = "class Same:\n    def __eq__(self, other):\n        return True\n\n\nANSWERS = {'second_take_from_one_token': Same(), 'take_from_a_missing_key': Same()}\n"
    assert run_tests(q, sneaky, "submit", settings(tmp_path)).status == "failed"
    assert run_tests(q, q.read("solution.py"), "submit", settings(tmp_path)).status == "passed"


def test_lint_warns_about_a_long_lesson_and_a_technique_tag(tmp_path):
    q = question(tmp_path / "q", {"lesson.md": "## The idea\n\n" + "word " * 501}, tags=["payments", "token-bucket"])
    result = validate_challenge(q, settings(tmp_path))
    assert result.ok, result.problems
    assert any("504 words" in n for n in result.notes), result.notes
    assert any("token-bucket" in n and "technique" in n for n in result.notes), result.notes


def test_a_file_that_cannot_load_is_an_error_that_names_the_file(tmp_path):
    """pytest 9 reports a collection error as a bare module name; the app must still say the tests could not start."""
    q = question(tmp_path / "q", {"tests/test_hidden.py": "from solution import NOPE\n"})
    report = run_tests(q, "ANSWER = 1\n", "submit", settings(tmp_path))
    assert report.status == "error" and "could not start" in report.summary, report
    assert report.tests[0].label == "test_hidden could not load" and report.tests[0].hidden and report.tests[0].details == ""

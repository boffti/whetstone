"""Run a learner's code against a challenge's pytest suite in a throwaway folder."""

from __future__ import annotations

import ast
import difflib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .config import Settings
from .content import DIFFICULTIES, LESSON_MODES, QUESTION_TYPES, REQUIRED_FILES, Challenge


@dataclass
class TestResult:
    name: str
    label: str
    outcome: str  # passed | failed | error | skipped
    duration: float
    message: str = ""
    details: str = ""
    hidden: bool = False


@dataclass
class RunReport:
    status: str  # passed | failed | error | timeout | blocked
    summary: str
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    total: int = 0
    duration: float = 0.0
    tests: list[TestResult] = field(default_factory=list)
    output: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def _label(name: str) -> str:
    if name.startswith("tests.") or name.endswith(".py"):
        return f"{name.split('.')[-1] if name.startswith('tests.') else name} could not load"
    base = name.split("[")[0]
    if base.startswith("test_"):
        base = base[5:]
    return base.replace("_", " ")


def _tail(text: str, limit: int = 6000) -> str:
    return text if len(text) <= limit else "...\n" + text[-limit:]


def run_tests(challenge: Challenge, code: str, mode: str, settings: Settings) -> RunReport:
    """mode = 'run' (visible tests only) or 'submit' (all tests)."""
    if challenge.kind == "tests":
        return _grade_learner_tests(challenge, code, mode, settings)
    include_hidden = mode == "submit"
    timeout = int(challenge.timeout or settings.run_timeout)
    files: dict[str, str | Path] = {"solution.py": code}
    files |= {name: challenge.path / name for name in challenge.support}
    files |= {f"tests/{f.name}": f for f in challenge.test_files(include_hidden)}
    tests, output, duration = _pytest(files, "tests", timeout, settings)
    if tests is None:
        return _timeout(timeout, duration, output)
    if challenge.kind == "design":
        tests.insert(0, _design_note(code))
    return _report(tests, output, duration, include_hidden, challenge, settings)


def _pytest(files: dict[str, str | Path], target: str, timeout: int, settings: Settings) -> tuple[list[TestResult] | None, str, float]:
    """Run pytest on `target` in a throwaway folder holding `files` (name -> text, or a file to
    copy). Returns (tests, output, seconds); tests is None when the run timed out."""
    with tempfile.TemporaryDirectory(prefix="whetstone-") as tmp_name:
        tmp = Path(tmp_name)
        for name, source in files.items():
            dest = tmp / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(source, Path):
                shutil.copy(source, dest)
            else:
                dest.write_text(source, encoding="utf-8")
        junit = tmp / "report.xml"
        cmd = [
            sys.executable,
            "-m",
            "pytest",
            target,
            "-q",
            "--tb=short",
            "--color=no",  # the app shows output as text; a FORCE_COLOR in the environment would leak escape codes
            "-p",
            "no:cacheprovider",
            "-o",
            "addopts=",
            "--rootdir",
            str(tmp),
            f"--junitxml={junit}",
        ]
        env = {k: v for k, v in os.environ.items() if k not in ("FORCE_COLOR", "PY_COLORS")}
        env |= {"PYTHONPATH": str(tmp), "PYTHONDONTWRITEBYTECODE": "1", "REDIS_URL": settings.redis_url, "NO_COLOR": "1"}
        started = time.monotonic()
        try:
            proc = subprocess.run(cmd, cwd=tmp, env=env, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            out = (exc.stdout or b"").decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
            return None, _tail(out), time.monotonic() - started
        output = _tail(proc.stdout + ("\n" + proc.stderr if proc.stderr.strip() else ""))
        return (_parse_junit(junit) if junit.exists() else []), output, time.monotonic() - started


def _timeout(timeout: int, duration: float, output: str) -> RunReport:
    return RunReport(
        status="timeout",
        summary=f"Stopped after {timeout} s. A thread may be waiting forever (deadlock) or a loop never ends.",
        duration=duration,
        output=output,
    )


def _report(
    tests: list[TestResult], output: str, duration: float, include_hidden: bool, challenge: Challenge, settings: Settings
) -> RunReport:
    report = RunReport(status="failed", summary="", duration=duration, tests=tests, output=output)
    report.total = len(tests)
    report.passed = sum(t.outcome == "passed" for t in tests)
    report.skipped = sum(t.outcome == "skipped" for t in tests)
    report.failed = sum(t.outcome in ("failed", "error") for t in tests)
    collection_error = any(t.outcome == "error" and (t.name.startswith(("tests.", "test_yours")) or t.name.endswith(".py")) for t in tests)

    if report.total == 0 or collection_error:
        report.status = "error"
        report.summary = "The tests could not start. Check for a syntax error or a missing name in your code."
    elif report.skipped and "redis" in challenge.requires:
        report.status = "blocked"
        report.summary = f"Redis is not reachable at {settings.redis_url}. Start Redis, then run again."
    elif report.failed == 0 and report.skipped == 0:
        report.status = "passed"
        report.summary = (
            f"All {report.total} tests passed."
            if include_hidden
            else f"All {report.total} visible tests passed. Submit to run the hidden tests."
        )
    else:
        report.status = "failed"
        report.summary = f"{report.passed} of {report.total} tests passed."
    return report


# ---------- "tests" questions: the learner writes the tests ----------
MUTANT_TIMEOUT = 20


def misconception(mutant: Path) -> str:
    """The first line of a mutant's docstring: the wrong belief it encodes."""
    try:
        doc = ast.get_docstring(ast.parse(mutant.read_text(encoding="utf-8"))) or ""
    except SyntaxError:
        doc = ""
    line = doc.strip().splitlines()[0] if doc.strip() else mutant.stem.replace("-", " ")
    return re.sub(r"^misconception:\s*", "", line, flags=re.I).rstrip(".")


def _grade_learner_tests(challenge: Challenge, code: str, mode: str, settings: Settings) -> RunReport:
    """Run the learner's tests on the real code (they must pass), then, on Submit, on each hidden
    mutant (each must make at least one of their tests fail)."""
    include_hidden = mode == "submit"
    timeout = int(challenge.timeout or settings.run_timeout)
    subject = challenge.support[0] if challenge.support else "subject.py"
    files: dict[str, str | Path] = {name: challenge.path / name for name in challenge.support} | {"test_yours.py": code}
    tests, output, duration = _pytest(files, "test_yours.py", timeout, settings)
    if tests is None:
        return _timeout(timeout, duration, output)
    results = [
        TestResult(
            name=t.name,
            label=f"your test passes on the real code: {t.label}",
            outcome=t.outcome,
            duration=t.duration,
            message=f"This test fails on the correct {subject}, so it checks the wrong thing. {t.message}".strip()
            if t.outcome == "failed"
            else t.message,
            details=t.details,
        )
        for t in tests
    ]
    if not tests:
        return RunReport(
            status="error", summary="Write at least one test: a function whose name starts with test_.", duration=duration, output=output
        )
    if include_hidden:
        for mutant in challenge.mutants():
            found, _, seconds = _pytest(files | {subject: mutant}, "test_yours.py", min(timeout, MUTANT_TIMEOUT), settings)
            duration += seconds
            caught = found is None or any(t.outcome in ("failed", "error") for t in found)
            results.append(
                TestResult(
                    name=f"test_catches_{mutant.stem.replace('-', '_')}",
                    label=f"catches the bug: {misconception(mutant)}",
                    outcome="passed" if caught else "failed",
                    duration=seconds,
                    message="" if caught else "Every one of your tests passes on this buggy version. Which input would expose it?",
                    hidden=True,
                )
            )
    return _report(results, output, duration, include_hidden, challenge, settings)


# ---------- "design" questions: a note on the choice, then code ----------
DESIGN_SECTIONS = ("options", "trade-off", "choice", "failure mode")


def _design_note(code: str) -> TestResult:
    """Design questions open solution.py with a short note; this checks it is filled in."""
    try:
        doc = ast.get_docstring(ast.parse(code)) or ""
    except SyntaxError:
        doc = ""
    missing = [s for s in DESIGN_SECTIONS if not re.search(rf"^\s*{s}\s*:\s*(?!\.\.\.)\S", doc, flags=re.I | re.M)]
    return TestResult(
        name="test_design_note",
        label="design note names the options, the trade-off, your choice and the failure mode you accept",
        outcome="failed" if missing else "passed",
        duration=0.0,
        message=f"Fill in the design note at the top of solution.py: {', '.join(missing)}." if missing else "",
    )


def _parse_junit(path: Path) -> list[TestResult]:
    results: list[TestResult] = []
    root = ET.parse(path).getroot()
    for case in root.iter("testcase"):
        name = case.get("name", "")
        classname = case.get("classname", "")
        outcome, message, details = "passed", "", ""
        for tag in ("failure", "error", "skipped"):
            node = case.find(tag)
            if node is not None:
                outcome = {"failure": "failed", "error": "error", "skipped": "skipped"}[tag]
                message = (node.get("message") or "").strip()
                details = (node.text or "").strip()
                break
        results.append(
            TestResult(
                name=name,
                label=_label(name),
                outcome=outcome,
                duration=float(case.get("time", 0) or 0),
                message=message[:500],
                details=_tail(details, 4000),
                hidden="hidden" in classname,
            )
        )
    return results


@dataclass
class Validation:
    key: str
    ok: bool
    problems: list[str]
    notes: list[str]


def validate_challenge(challenge: Challenge, settings: Settings, strict: bool = False) -> Validation:
    """A challenge is valid when its files exist, the reference solution passes every
    test, and the starter fails at least one test. `strict` (used when a question is added)
    also enforces the current format; older questions only get notes."""
    problems: list[str] = []
    notes: list[str] = []
    for problem in _format_problems(challenge):
        (problems if strict else notes).append(problem)
    if challenge.kind not in QUESTION_TYPES:
        problems.append(f"type must be one of {', '.join(QUESTION_TYPES)}")
    if challenge.lesson not in LESSON_MODES:
        problems.append(f"lesson must be one of {', '.join(LESSON_MODES)}")
    if challenge.variant_of and not re.fullmatch(r"[a-z0-9-]+/\d{2}-[a-z0-9-]+", challenge.variant_of):
        problems.append("variant_of must be a question key, like rate-limiter/01-token-bucket")
    if challenge.kind in ("predict", "review") and not challenge.support:
        problems.append(f"a {challenge.kind} question needs the code to read as a support file (support: [subject.py])")
    for name in REQUIRED_FILES:
        if not (challenge.path / name).exists():
            problems.append(f"missing {name}")
    if challenge.kind == "tests":
        if not challenge.support:
            problems.append("a tests question needs the code under test as a support file (support: [subject.py])")
        if len(challenge.mutants()) < 2:
            problems.append("a tests question needs 2 or more buggy versions in mutants/, which the learner's tests must catch")
    elif not challenge.visible_test_files():
        problems.append("missing tests/test_visible.py (at least one visible test file)")
    if challenge.difficulty not in DIFFICULTIES:
        problems.append(f"difficulty must be one of {', '.join(DIFFICULTIES)}")
    for name in challenge.support:
        if not (challenge.path / name).exists():
            problems.append(f"support file {name} is listed but missing")
    if (challenge.path / "hints.md").exists() and len(challenge.hints()) < 2:
        problems.append("hints.md needs at least 2 hints separated by --- lines")
    if problems:
        return Validation(challenge.key, False, problems, notes)

    ref = run_tests(challenge, challenge.read("solution.py"), "submit", settings)
    if ref.status == "blocked":
        notes.append("Redis is not reachable, so the Redis tests were skipped. Start Redis and validate again.")
        return Validation(challenge.key, False, [ref.summary], notes)
    if ref.status != "passed":
        failing = [f"{t.name}: {t.message}" for t in ref.tests if t.outcome in ("failed", "error")]
        problems.append(f"reference solution does not pass: {ref.summary}")
        problems.extend(failing[:8] or [ref.output[-1500:]])
    notes.append(f"reference solution: {ref.passed}/{ref.total} passed in {ref.duration:.1f} s")

    if challenge.kind == "fix":
        notes.append(_fix_size(challenge))

    starter = run_tests(challenge, challenge.read("starter.py"), "submit", settings)
    if starter.status == "passed":
        problems.append("starter passes every test, so the challenge teaches nothing; make the starter incomplete")
    else:
        notes.append(f"starter: {starter.passed}/{starter.total} passed (expected: some fail)")

    if challenge.kind in MUTATION_GATED:
        gate, gate_notes = _mutation_gate(challenge, settings, strict)
        problems += gate
        notes += gate_notes
    return Validation(challenge.key, not problems, problems, notes)


# Questions whose tests grade the learner's code. Their tests must catch every mutant: a wrong
# version of the reference, one per misconception. (For "tests" questions the mutants are what
# the learner's tests must catch, so the reference solution check already covers them.)
MUTATION_GATED = ("build", "fix", "design")


def _mutation_gate(challenge: Challenge, settings: Settings, strict: bool) -> tuple[list[str], list[str]]:
    mutants = challenge.mutants()
    if len(mutants) < 2:
        gap = "add 2 or more mutants/*.py: wrong versions of the solution, one per misconception, that the tests must catch"
        return ([gap], []) if strict else ([], [gap])
    survivors = [m for m in mutants if run_tests(challenge, m.read_text(encoding="utf-8"), "submit", settings).status == "passed"]
    found = [
        f"mutants/{m.name} survives: no test catches '{misconception(m)}'. Add a hidden test for it, or fix the mutant." for m in survivors
    ]
    note = f"mutants: the tests catch {len(mutants) - len(survivors)} of {len(mutants)}"
    return (found, [note]) if strict else ([], [note, *found])


def _format_problems(challenge: Challenge) -> list[str]:
    """Rules of the current question format that older questions may not follow yet."""
    problems = []
    if (challenge.path / "hints.md").exists() and len(challenge.hints()) != 4:
        problems.append("hints.md needs exactly 4 hints: a question, the concept, a next step tied to a test, a skeleton")
    return problems


def _fix_size(challenge: Challenge) -> str:
    """A fix question's bug should be small: report how much of the starter the fix changes."""
    before, after = challenge.read("starter.py").splitlines(), challenge.read("solution.py").splitlines()
    changed = sum(1 for op in difflib.ndiff(before, after) if op[:1] in "+-")
    return f"fix: the reference changes {changed} lines of a {len(before)}-line starter (keep the bug small and realistic)"

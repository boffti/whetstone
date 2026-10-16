"""Run a learner's code against a challenge's pytest suite in a throwaway folder."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .config import Settings
from .content import DIFFICULTIES, REQUIRED_FILES, Challenge


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
    include_hidden = mode == "submit"
    timeout = int(challenge.timeout or settings.run_timeout)
    with tempfile.TemporaryDirectory(prefix="whetstone-") as tmp_name:
        tmp = Path(tmp_name)
        (tmp / "solution.py").write_text(code, encoding="utf-8")
        for name in challenge.support:
            shutil.copy(challenge.path / name, tmp / name)
        tests_dir = tmp / "tests"
        tests_dir.mkdir()
        for test_file in challenge.test_files(include_hidden):
            shutil.copy(test_file, tests_dir / test_file.name)
        junit = tmp / "report.xml"
        cmd = [
            sys.executable,
            "-m",
            "pytest",
            "tests",
            "-q",
            "--tb=short",
            "-p",
            "no:cacheprovider",
            "-o",
            "addopts=",
            "--rootdir",
            str(tmp),
            f"--junitxml={junit}",
        ]
        env = {**os.environ, "PYTHONPATH": str(tmp), "PYTHONDONTWRITEBYTECODE": "1", "REDIS_URL": settings.redis_url}
        started = time.monotonic()
        try:
            proc = subprocess.run(cmd, cwd=tmp, env=env, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            out = (exc.stdout or b"").decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
            return RunReport(
                status="timeout",
                summary=f"Stopped after {timeout} s. A thread may be waiting forever (deadlock) or a loop never ends.",
                duration=time.monotonic() - started,
                output=_tail(out),
            )
        duration = time.monotonic() - started
        output = _tail(proc.stdout + ("\n" + proc.stderr if proc.stderr.strip() else ""))
        tests = _parse_junit(junit) if junit.exists() else []

    report = RunReport(status="failed", summary="", duration=duration, tests=tests, output=output)
    report.total = len(tests)
    report.passed = sum(t.outcome == "passed" for t in tests)
    report.skipped = sum(t.outcome == "skipped" for t in tests)
    report.failed = sum(t.outcome in ("failed", "error") for t in tests)
    collection_error = any(t.outcome == "error" and (t.name.startswith("tests.") or t.name.endswith(".py")) for t in tests)

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


def validate_challenge(challenge: Challenge, settings: Settings) -> Validation:
    """A challenge is valid when its files exist, the reference solution passes every
    test, and the starter fails at least one test."""
    problems: list[str] = []
    notes: list[str] = []
    for name in REQUIRED_FILES:
        if not (challenge.path / name).exists():
            problems.append(f"missing {name}")
    if not challenge.visible_test_files():
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

    starter = run_tests(challenge, challenge.read("starter.py"), "submit", settings)
    if starter.status == "passed":
        problems.append("starter passes every test, so the challenge teaches nothing; make the starter incomplete")
    else:
        notes.append(f"starter: {starter.passed}/{starter.total} passed (expected: some fail)")
    return Validation(challenge.key, not problems, problems, notes)

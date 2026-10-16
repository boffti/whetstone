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
    if challenge.is_whiteboard:
        return check_whiteboard(code)
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


# ---------- "whiteboard" questions: a system design in Markdown ----------
# The sections of a design interview, in order, with what each one should hold. The starter
# template and the check's messages both come from here.
WHITEBOARD_SECTIONS = {
    "Requirements": "What it must do, what it need not do, and the numbers it must meet.",
    "Estimates": "Rough load: requests per second, data size, growth. Show the arithmetic.",
    "API": "The calls clients make, with their inputs, outputs and errors.",
    "Data model": "What you store, the keys you look it up by, and where it lives.",
    "High-level design": "The main components and how a request flows through them. Draw them on the Whiteboard tab, then explain the flow here.",
    "Deep dives": "The two or three hardest parts, worked through in detail.",
    "Trade-offs": "What you chose, what you gave up, and why.",
    "Failure modes": "What breaks: a node, a region, a dependency, a retry storm. What happens then.",
}
SECTION_MIN_WORDS = 12


def whiteboard_sections(text: str) -> dict[str, str]:
    """The design's level-2 sections ("## Name"), by lowercased name, without HTML comments."""
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    parts = re.split(r"^##[ \t]+(.+?)[ \t]*#*[ \t]*$", text, flags=re.M)
    return {parts[i].strip().lower(): parts[i + 1] for i in range(1, len(parts) - 1, 2)}


# ---------- The whiteboard drawing, as Mermaid for the agent ----------
SHAPE_SYNTAX = {"rectangle": '["{}"]', "ellipse": '(["{}"])', "diamond": '{{"{}"}}'}


def _words(text: object) -> str:
    return " ".join(str(text or "").split()).replace('"', "'")


def drawing_mermaid(elements: list[dict]) -> tuple[str, list[str]]:
    """An Excalidraw drawing as a Mermaid flowchart, plus what does not fit one: loose text and
    arrows that connect to nothing. Labelled shapes are nodes; so is free text an arrow points
    at. An arrow is an edge when each end is bound to, or lands on, a node. Frames are subgraphs.
    ("", []) for an empty drawing."""
    live = [e for e in elements if isinstance(e, dict) and not e.get("isDeleted")]
    by_id = {e.get("id"): e for e in live}
    labels: dict[str, str] = {}
    loose: list[dict] = []
    for e in live:
        if e.get("type") == "text" and _words(e.get("text")):
            if e.get("containerId") in by_id:
                labels[e["containerId"]] = _words(e.get("text"))
            else:
                loose.append(e)
    shapes = [e for e in live if e.get("type") in SHAPE_SYNTAX]

    def holds(box: dict, x: float, y: float, pad: float = 0) -> bool:
        bx, by = box.get("x", 0), box.get("y", 0)
        return bx - pad <= x <= bx + box.get("width", 0) + pad and by - pad <= y <= by + box.get("height", 0) + pad

    for t in list(loose):  # free text drawn on top of an unlabelled shape names it
        home = next((s for s in shapes if s["id"] not in labels and holds(s, t.get("x", 0), t.get("y", 0))), None)
        if home:
            labels[home["id"]] = _words(t.get("text"))
            loose.remove(t)

    def end_of(arrow: dict, last: bool) -> str | None:
        bound = (arrow.get("endBinding" if last else "startBinding") or {}).get("elementId")
        if bound in {s["id"] for s in shapes}:
            return bound
        points = arrow.get("points") or []
        if not points:
            return None
        x, y = arrow.get("x", 0) + points[-1 if last else 0][0], arrow.get("y", 0) + points[-1 if last else 0][1]
        hit = next((s for s in shapes if holds(s, x, y, 16)), None) or next((t for t in loose if holds(t, x, y, 24)), None)
        return hit["id"] if hit else None

    arrows = [(a, end_of(a, False), end_of(a, True)) for a in live if a.get("type") in ("arrow", "line")]
    pointed = {end for _, *ends in arrows for end in ends if end}
    nodes = shapes + [t for t in loose if t["id"] in pointed]  # free text an arrow points at is a node
    loose = [t for t in loose if t["id"] not in pointed]
    nodes.sort(key=lambda e: (round(e.get("y", 0) / 40), e.get("x", 0)))
    names = {n["id"]: f"n{i}" for i, n in enumerate(nodes, 1)}

    def node(n: dict) -> str:
        if n.get("type") == "text":
            return f'{names[n["id"]]}["{_words(n.get("text"))}"]'
        return names[n["id"]] + SHAPE_SYNTAX[n["type"]].format(labels.get(n["id"], "unlabelled " + n["type"]))

    frames = {e["id"]: _words(e.get("name")) or "group" for e in live if e.get("type") in ("frame", "magicframe")}
    lines = ["flowchart LR"]
    for fid, title in frames.items():
        members = [node(n) for n in nodes if n.get("frameId") == fid]
        if members:
            lines += [f'  subgraph f{len(lines)}["{title}"]', *(f"    {m}" for m in members), "  end"]
    lines += [f"  {node(n)}" for n in nodes if n.get("frameId") not in frames]
    notes, stray = [], 0
    for a, start, finish in arrows:
        text = labels.get(a["id"], "")
        if start and finish:
            arrow = ("-.->" if a.get("strokeStyle") in ("dashed", "dotted") else "-->") if a.get("type") == "arrow" else "---"
            label = f'|"{text.replace("|", "/")}"|' if text else ""
            lines.append(f"  {names[start]} {arrow}{label} {names[finish]}")
        elif start or finish:
            known = start or finish
            name = labels.get(known) or _words(by_id[known].get("text")) or "a shape"
            notes.append(f"an arrow{f' labelled {text!r}' if text else ''} at {name!r} whose other end is attached to nothing")
        elif text:
            notes.append(f"an unconnected arrow labelled {text!r}")
        else:
            stray += 1
    if stray:
        notes.append(f"{stray} arrow{'s' if stray > 1 else ''} not attached to anything")
    notes += [f"text on the board: {_words(t.get('text'))!r}" for t in loose]
    counts = {n: notes.count(n) for n in notes}  # say "twice", not the same line twice
    notes = [n if c == 1 else f"{n} ({c} times)" for n, c in counts.items()]
    if not nodes and not notes:
        return "", []
    return "\n".join(lines), notes


def drawing_ready(elements: list[dict]) -> bool:
    """A diagram worth the name: two labelled shapes joined by an arrow."""
    mermaid, _ = drawing_mermaid(elements)
    edges = re.findall(r"^  n\d+ (?:-->|-\.->|---)", mermaid, flags=re.M)
    labelled = re.findall(r'^ +n\d+[\[({]+"(?!unlabelled )', mermaid, flags=re.M)
    return bool(edges) and len(labelled) >= 2


def check_whiteboard(text: str, drawing: list[dict] | None = None) -> RunReport:
    """Every section has some substance, and there is at least one diagram: on the whiteboard, or
    a mermaid block in the text. The design itself is graded by the learner's agent against the
    rubric; this only says what is still empty."""
    sections = whiteboard_sections(text)
    tests = []
    for name, what in WHITEBOARD_SECTIONS.items():
        body = sections.get(name.lower())
        words = len(re.findall(r"[A-Za-z0-9]+", body or ""))
        if body is None:
            message = f"Add a '## {name}' section. {what}"
        elif words < SECTION_MIN_WORDS:
            message = f"{name} has {plural_words(words)}. {what}"
        else:
            message = ""
        tests.append(TestResult(f"section_{slug_name(name)}", f"{name} is filled in", "failed" if message else "passed", 0.0, message))
    drawn = drawing_ready(drawing or []) or re.search(r"^```mermaid[ \t]*$", text, flags=re.M)
    tests.append(
        TestResult(
            "diagram",
            "a diagram shows the main components",
            "passed" if drawn else "failed",
            0.0,
            "" if drawn else "On the Whiteboard tab, draw the main components as labelled boxes and join them with arrows.",
        )
    )
    passed = sum(t.outcome == "passed" for t in tests)
    status = "passed" if passed == len(tests) else "failed"
    summary = "Every section is filled in. Ask for a review." if status == "passed" else f"{passed} of {len(tests)} parts are ready."
    return RunReport(status, summary, passed=passed, failed=len(tests) - passed, total=len(tests), tests=tests)


def plural_words(n: int) -> str:
    return f"{n} word" if n == 1 else f"{n} words"


def slug_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


RUBRIC_VERDICTS = ("covered", "partial", "missing")


def rubric_problems(challenge: Challenge) -> list[str]:
    """What is wrong with a whiteboard question's rubric.yaml."""
    try:
        points = challenge.rubric()
    except Exception as exc:  # a YAML error names the line
        return [f"rubric.yaml does not parse: {exc}"]
    problems = []
    if not 5 <= len(points) <= 10:
        problems.append(f"rubric.yaml needs 5 to 10 points under 'points:' (it has {len(points)})")
    ids = [str(p.get("id", "")) for p in points]
    if any(not re.fullmatch(r"[a-z0-9-]+", i) for i in ids) or len(set(ids)) != len(ids):
        problems.append("every rubric point needs a unique id in lowercase-with-dashes")
    sections = {n.lower() for n in WHITEBOARD_SECTIONS}
    for p in points:
        if not str(p.get("point", "")).strip():
            problems.append(f"rubric point {p.get('id')} needs a 'point': what a strong design does")
        if str(p.get("section", "")).lower() not in sections:
            problems.append(f"rubric point {p.get('id')}: section must be one of {', '.join(WHITEBOARD_SECTIONS)}")
    if sum(bool(p.get("must")) for p in points) < 3:
        problems.append("mark 3 or more rubric points with 'must: true': the ones a design cannot pass without")
    return problems


def grade_design(challenge: Challenge, payload: object) -> tuple[dict, list[str]]:
    """Check an agent's grade of a whiteboard design against the question's rubric. The design
    passes when every must-have point is covered. Returns (grade, problems)."""
    rubric = {str(p.get("id")): p for p in challenge.rubric()}
    given = payload.get("points") if isinstance(payload, dict) else None
    if not isinstance(given, dict):
        return {}, ['The grade needs "points": {"<rubric id>": {"verdict": "covered", "quote": "...", "note": "..."}, ...}']
    problems = [f"{pid} is not in rubric.yaml" for pid in given if pid not in rubric]
    problems += [f"{pid} has no verdict: grade every rubric point" for pid in rubric if pid not in given]
    points = []
    for pid, point in rubric.items():
        g = given.get(pid) if isinstance(given.get(pid), dict) else {}
        verdict = str(g.get("verdict", "")).lower()
        quote, note = str(g.get("quote", "")).strip(), str(g.get("note", "")).strip()
        if pid in given and verdict not in RUBRIC_VERDICTS:
            problems.append(f"{pid}: verdict must be one of {', '.join(RUBRIC_VERDICTS)}")
        if verdict in ("partial", "missing") and not note:
            problems.append(f"{pid}: a {verdict} point needs a note, one question that leads the learner to it")
        if len(note) > 400 or len(quote) > 300:
            problems.append(f"{pid}: keep the note under 400 characters and the quote under 300")
        points.append(
            {
                "id": pid,
                "section": str(point.get("section", "")),
                "point": str(point.get("point", "")).strip(),
                "must": bool(point.get("must")),
                "verdict": verdict,
                "quote": quote,
                "note": note,
            }
        )
    summary = str(payload.get("summary", "")).strip()
    if not summary or len(summary) > 600:
        problems.append('Add a "summary": one to three sentences on the design as a whole, under 600 characters.')
    covered = sum(p["verdict"] == "covered" for p in points)
    status = "passed" if all(p["verdict"] == "covered" for p in points if p["must"]) else "failed"
    return {"points": points, "summary": summary, "covered": covered, "total": len(points), "status": status}, problems


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
    if challenge.is_whiteboard:
        return _validate_whiteboard(challenge, problems, notes)
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

    ref = run_tests(challenge, challenge.read(challenge.solution_file), "submit", settings)
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

    starter = run_tests(challenge, challenge.read(challenge.starter_file), "submit", settings)
    if starter.status == "passed":
        problems.append("starter passes every test, so the challenge teaches nothing; make the starter incomplete")
    else:
        notes.append(f"starter: {starter.passed}/{starter.total} passed (expected: some fail)")

    if challenge.kind in MUTATION_GATED:
        gate, gate_notes = _mutation_gate(challenge, settings, strict)
        problems += gate
        notes += gate_notes
    return Validation(challenge.key, not problems, problems, notes)


def _validate_whiteboard(challenge: Challenge, problems: list[str], notes: list[str]) -> Validation:
    """The files exist, the rubric is sound, the reference design fills every section, and the
    starter does not. There are no tests or mutants: the learner's agent grades the design."""
    for name in challenge.required_files:
        if not (challenge.path / name).exists():
            problems.append(f"missing {name}")
    if challenge.difficulty not in DIFFICULTIES:
        problems.append(f"difficulty must be one of {', '.join(DIFFICULTIES)}")
    if problems:
        return Validation(challenge.key, False, problems, notes)
    problems += rubric_problems(challenge)
    ref = check_whiteboard(challenge.read("solution.md"))
    if ref.status != "passed":
        problems.append(f"the reference design (solution.md) is not complete: {ref.summary}")
        problems += [f"{t.label}: {t.message}" for t in ref.tests if t.outcome != "passed"]
    else:
        notes.append(f"reference design: all {ref.total} parts filled in")
    starter = check_whiteboard(challenge.read("starter.md"))
    if starter.status == "passed":
        problems.append("starter.md fills every section already; leave the sections for the learner")
    rubric = challenge.rubric() if not any("rubric.yaml does not parse" in p for p in problems) else []
    notes.append(f"rubric: {len(rubric)} points, {sum(bool(p.get('must')) for p in rubric)} of them must-haves")
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

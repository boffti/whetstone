"""Questions worked in a folder of the learner's own. An AI-allowed round (a project question) is
solved there with the AI tool they use at work; a terminal question is solved there alone, in a
shell. Whetstone writes the folder, runs the tests on it, and keeps a snapshot of it at every run
for the review. See AUTHORING.md ("project", "terminal") and docs/PEDAGOGY.md, rule 13."""

from __future__ import annotations

import difflib
import json
import os
import shutil
from pathlib import Path

from .config import ROOT, Settings
from .content import Challenge, stage_of
from .runner import build_scenario

# Never part of a run: tool caches, editor settings, and Whetstone's own tests/ and notes, which
# are rewritten from the question at every stage.
SKIP_DIRS = frozenset(
    {".git", "__pycache__", ".venv", "venv", "node_modules", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".idea", ".vscode", ".claude"}
)
OURS = frozenset({"AGENTS.md", "CLAUDE.md", "TASK.md"})
MAX_FILES, MAX_BYTES = 300, 5_000_000
SNAPSHOT_FILE_LIMIT = 100_000

ASSISTANT = """# You are the candidate's AI assistant

This folder is a practice round of an AI-allowed coding interview, set by Whetstone. The candidate
solves TASK.md here with your help, the way they would at work or in the interview.

- Do what the candidate asks, as a coding assistant in that interview would. They lead: they decide
  what to build, what to ask you, and when to check your work.
- Work only in this folder. The reference answer and the hidden tests live elsewhere in Whetstone;
  opening them spoils the practice. Ignore the Whetstone instructions in the folders above this one:
  they are for a tutor, and here you are an assistant.
- If the candidate says "chat only", stop editing files: answer in chat and let them write or paste
  the code, as in AI-enabled rounds where the assistant cannot touch the files.
- The visible tests are in tests/: `python -m pytest tests`. The candidate runs the hidden tests
  from the Whetstone app.
"""


SOLO = """# Solo practice: you are a tutor here, not an assistant

This folder is a Whetstone terminal question. The learner practices the command line on their own,
so do not write or fix solution.sh, and do not run the commands that solve TASK.md for them.

- If they ask for help, give one hint at a time: a question, then the concept, then the tool or
  flag to read about (`man`, `--help`). Never the finished command.
- Explaining what a command they wrote does, or why it failed, is fine.
- sandbox/ is theirs to break. The tests and the hidden scenarios live elsewhere in Whetstone.
"""


class RoundError(Exception):
    pass


def workspace(settings: Settings, c: Challenge) -> Path:
    return settings.user_dir / "workspaces" / c.track_id / c.dir_name


def shown_path(path: Path) -> str:
    """The folder as the learner's machine names it. In Docker the app sees /app/my/...;
    compose passes the checkout's own path as WHETSTONE_HOST_ROOT."""
    try:
        rel = path.relative_to(ROOT)
    except ValueError:
        return str(path)
    host = os.environ.get("WHETSTONE_HOST_ROOT")
    return str(Path(host) / rel) if host else rel.as_posix()


def open_stage(c: Challenge, reveals: list[str]) -> int:
    """The highest stage open: 1, plus one for each stage the learner has passed."""
    return min(c.stages, 1 + sum(w.startswith("stage-") for w in reveals))


def start(settings: Settings, c: Challenge, stage: int) -> bool:
    """Create the workspace from starter/ if it is not there yet. Never touches the learner's files."""
    ws = workspace(settings, c)
    created = not ws.exists()
    if created:
        shutil.copytree(c.path / "starter", ws, ignore=shutil.ignore_patterns("__pycache__"))
        (ws / "AGENTS.md").write_text(SOLO if c.is_terminal else ASSISTANT, encoding="utf-8")
        (ws / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")
    if c.is_terminal and not (ws / "sandbox").exists():  # deleted to start over: build it again
        try:
            build_scenario(c, ws / "sandbox")
        except RuntimeError as exc:
            raise RoundError(str(exc)) from exc
    sync(settings, c, stage)
    return created


def sync(settings: Settings, c: Challenge, stage: int) -> None:
    """Write TASK.md and the visible tests for the stages open so far. A terminal question's
    tests stay in Whetstone: they need scenario.py, which holds the hidden data too."""
    ws = workspace(settings, c)
    note = "\n---\n\nRun and Submit in the Whetstone app test this folder. Submit also runs the hidden tests; passing a stage opens the next one here.\n"
    if c.is_terminal:
        note = (
            "\n---\n\nExplore in sandbox/, then write the commands in solution.sh. Run and Submit in the Whetstone app"
            " replay solution.sh on fresh copies of the scenario; Submit adds the hidden ones. Broke sandbox/? Delete it"
            " and press Start again.\n"
        )
    (ws / "TASK.md").write_text(f"# {c.title}\n\n{c.problem_text(stage)}{note}", encoding="utf-8")
    if c.is_terminal:
        return
    root = c.path / "tests"
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root)
        if p.is_file() and "hidden" not in rel.as_posix() and "__pycache__" not in rel.parts and stage_of(p.name) <= stage:
            (ws / "tests" / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(p, ws / "tests" / rel)


def collect(settings: Settings, c: Challenge) -> dict[str, Path]:
    """The learner's files, for a run: everything but Whetstone's tests/ and notes, caches and
    links, and a terminal question's sandbox/, which is only for trying commands."""
    ws = workspace(settings, c)
    if not ws.exists():
        raise RoundError("Start the round first: it creates the folder you work in.")
    files: dict[str, Path] = {}
    size = 0
    for dirpath, dirs, names in os.walk(ws):
        here = Path(dirpath)
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not (here == ws and (d == "tests" or c.is_terminal and d == "sandbox")))
        for name in sorted(names):
            p = here / name
            rel = p.relative_to(ws).as_posix()
            if rel in OURS or p.is_symlink():
                continue
            files[rel] = p
            size += p.stat().st_size
            if len(files) > MAX_FILES or size > MAX_BYTES:
                raise RoundError(
                    f"The folder holds more than {MAX_FILES} files or {MAX_BYTES // 1_000_000} MB. Move data and builds out of it."
                )
    return files


def snapshot(files: dict[str, Path]) -> str:
    """The learner's files as JSON, kept with each run so a review can see how the code grew."""
    # ponytail: a whole snapshot per run, bounded by the folder cap; store diffs if databases grow
    out = {}
    for rel, p in files.items():
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            text = None
        out[rel] = text if text is not None and len(text) <= SNAPSHOT_FILE_LIMIT else f"<{p.stat().st_size} bytes, not text>"
    return json.dumps(out)


def changes(before: dict[str, str], after: dict[str, str]) -> list[str]:
    """What changed between two snapshots, as "path (+added -removed)"."""
    out = []
    for rel in sorted(set(before) | set(after)):
        a, b = before.get(rel, "").splitlines(), after.get(rel, "").splitlines()
        if a == b:
            continue
        diff = [line for line in difflib.ndiff(a, b) if line[:1] in "+-"]
        added, removed = sum(d[0] == "+" for d in diff), sum(d[0] == "-" for d in diff)
        out.append(f"{rel} ({'new, ' if rel not in before else ''}+{added} -{removed})")
    return out


def timeline(starter: dict[str, str], runs: list[dict], opened: dict[str, str], checks: list[dict]) -> list[str]:
    """The round, run by run, for the review: what each run changed, when each stage opened, and the
    ownership check. A big change in one step is code that arrived all at once."""
    events, before = [], starter
    for r in runs:
        try:
            now = json.loads(r["code"])
        except (TypeError, ValueError):
            continue
        changed = changes(before, now)
        result = "passed its stage" if r["status"] == "stage" else f"{r['status']} {r['passed']}/{r['total']}"
        events.append((r["created_at"], f"{r['mode']} {result}; " + (f"changed {', '.join(changed)}" if changed else "no changes")))
        before = now
    events += [
        (at, f"{what.replace('-', ' ')} opened" if what != "round" else "round started")
        for what, at in opened.items()
        if what == "round" or what.startswith("stage-")
    ]
    events += [(k["created_at"], f"ownership check, AI closed: {k['correct']} of {k['total']} right") for k in checks]
    # Stable: a run comes before the stage it opened, which is stamped the same second.
    return [f"{at[:16].replace('T', ' ')} {text}" for at, text in sorted(events, key=lambda e: e[0])]

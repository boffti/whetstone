"""Command line. Any AI coding agent (or a person) drives Whetstone with these commands;
the agent does the thinking on the learner's own subscription. See AGENTS.md.

Content model: a learning path is an ordered list of modules toward a goal; a module
is a topic made of ordered questions; a question is one exercise (lesson, code, tests).
In the files, a module is a folder under my/tracks/ and a question is a folder in it.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .catalog import CLI, _rel
from .config import load_settings
from .content import (
    QUESTION_TYPES,
    ContentError,
    LearningPath,
    find_challenge,
    load_all_paths,
    load_profile,
    load_tracks,
    save_path,
    slugify,
)


def _challenge_yaml(kind: str, lesson: str, support: str = "[]", minutes: int = 20) -> str:
    return (
        "title: {title}  # name the scenario, not the technique\n"
        f"type: {kind}  # build | predict | fix | review | tests | design\n"
        f"lesson: {lesson}  # after-run = problem first; first = lesson first (use for predict)\n"
        f"difficulty: medium\nminutes: {minutes}\ntags: []\nrequires: []\n"
        f"support: {support}  # read-only files the learner sees; predict, review and tests: the code to read\n"
        "# variant_of: module/NN-slug  # set when this re-tests an earlier question on a new surface\n"
        "summary: One sentence about what the learner does.\n"
    )


# A toy question of each type that passes `question add`; the author replaces every file. See AUTHORING.md.
TEMPLATE = {
    "challenge.yaml": _challenge_yaml("build", "after-run"),
    "lesson.md": "## The idea\n\n## Subgoals\n\n## In Python\n\n## Misconceptions\n\n## Interview angle\n\n## Tie-in to your work\n",
    "problem.md": "## Task\n\n## API\n\n## Rules\n\n## Example\n",
    "hints.md": (
        "Rung 1, a question about the failing behavior.\n\n---\n\n"
        "Rung 2, the concept or subgoal behind it, by its lesson name.\n\n---\n\n"
        "Rung 3, a concrete next step tied to a named test.\n\n---\n\n"
        "Rung 4, a skeleton: the structure with the key lines left as `...`.\n"
    ),
    "starter.py": '"""Starter code."""\n\n\ndef solve():\n    raise NotImplementedError\n',
    "solution.py": '"""Reference solution."""\n\n\ndef solve():\n    return 42\n',
    "tests/test_visible.py": "from solution import solve\n\n\ndef test_returns_answer():\n    assert solve() == 42\n",
    "tests/test_hidden.py": "from solution import solve\n\n\ndef test_returns_int():\n    assert isinstance(solve(), int)\n",
    "mutants/01-off-by-one.py": '"""Misconception: one less is close enough."""\n\n\ndef solve():\n    return 41\n',
    "mutants/02-wrong-type.py": '"""Misconception: the text "42" is the same as the number 42."""\n\n\ndef solve():\n    return "42"\n',
}

_COMMON = {name: TEMPLATE[name] for name in ("lesson.md", "hints.md")}

_PREDICT = {
    **_COMMON,
    "challenge.yaml": _challenge_yaml("predict", "first", "[subject.py]", 15),
    "problem.md": "## Task\n\n## API\n\n## Predict\n\n## Example\n",
    "subject.py": (
        '"""The code the learner predicts. Keep it correct, realistic and under 60 lines."""\n\n\n'
        "def take(bucket: dict, key: str, n: int = 1) -> bool:\n"
        '    """Spend n tokens from bucket[key] if there are enough. A missing key has 0 tokens."""\n'
        "    left = bucket.get(key, 0)\n"
        "    if left < n:\n"
        "        return False\n"
        "    bucket[key] = left - n\n"
        "    return True\n"
    ),
    "starter.py": (
        '"""Your predictions. Replace each ... with the value the code produces. Predict by reading; do not run it."""\n\n'
        "ANSWERS = {\n"
        '    "second_take_from_one_token": ...,  # bool\n'
        '    "take_from_a_missing_key": ...,  # bool\n'
        "}\n"
    ),
    "solution.py": '"""The right predictions."""\n\nANSWERS = {\n    "second_take_from_one_token": False,\n    "take_from_a_missing_key": False,\n}\n',
    "tests/test_visible.py": (
        "from solution import ANSWERS\n\n"
        'KEYS = ("second_take_from_one_token", "take_from_a_missing_key")\n\n\n'
        "def test_every_prediction_is_filled_in():\n"
        "    missing = [k for k in KEYS if k not in ANSWERS or ANSWERS[k] is ...]\n"
        '    assert not missing, "Fill in every prediction: " + ", ".join(missing) + "."\n'
    ),
    "tests/test_hidden.py": (
        "from pathlib import Path\n\n"
        "import solution\n"
        "from solution import ANSWERS\n"
        "from subject import take\n\n\n"
        "def test_solution_does_not_import_subject():\n"
        '    assert "subject" not in Path(solution.__file__).read_text(), "Predict it by reading the code, not by running it."\n\n\n'
        "def test_second_take_from_one_token():\n"
        '    bucket = {"k": 1}\n'
        '    take(bucket, "k")\n'
        '    assert ANSWERS["second_take_from_one_token"] == take(bucket, "k"), "What is left after the first take spends the only token?"\n\n\n'
        "def test_take_from_a_missing_key():\n"
        '    assert ANSWERS["take_from_a_missing_key"] == take({}, "k"), "What does .get(key, 0) give for a key that was never added?"\n'
    ),
}

_FIX_API = "def in_window(events: list[float], now: float, size: float) -> int:\n"
_FIX_DOC = '    """How many events happened in the last `size` seconds. One exactly `size` seconds old still counts."""\n'
_FIX = {
    **_COMMON,
    "challenge.yaml": _challenge_yaml("fix", "after-run"),
    "problem.md": "## Task\n\n<!-- A bug report: the symptom, the steps to reproduce, expected and actual. Never the cause. -->\n\n## API\n\n## Rules\n\n## Example\n",
    "starter.py": '"""Count the events inside a sliding window. Complete, and wrong in one place."""\n\n\n'
    + _FIX_API
    + _FIX_DOC
    + "    return sum(1 for t in events if t > now - size)\n",
    "solution.py": '"""Count the events inside a sliding window."""\n\n\n'
    + _FIX_API
    + _FIX_DOC
    + "    return sum(1 for t in events if t >= now - size)\n",
    "tests/test_visible.py": (
        "from solution import in_window\n\n\n"
        "def test_an_event_exactly_one_window_old_still_counts():\n"
        "    assert in_window([0.0, 5.0, 10.0], now=10.0, size=10.0) == 3, (\n"
        '        "The report says the oldest event in the window is dropped. Which comparison decides the edge?"\n'
        "    )\n"
    ),
    "tests/test_hidden.py": (
        "from solution import in_window\n\n\n"
        "def test_older_events_are_dropped():\n"
        '    assert in_window([2.0, 9.0], now=10.0, size=5.0) == 1, "An event from before the window must not count."\n\n\n'
        "def test_the_edge_holds_for_any_window():\n"
        '    assert in_window([3.0, 7.0], now=7.0, size=4.0) == 2, "Fixing only the reported numbers is not a fix. Does the edge hold elsewhere?"\n'
    ),
    "mutants/01-counts-every-event.py": '"""Misconception: the window is for show; every event counts."""\n\n\n'
    + _FIX_API
    + _FIX_DOC
    + "    return len(events)\n",
    "mutants/02-drops-the-newest.py": '"""Misconception: an event at `now` has not happened yet."""\n\n\n'
    + _FIX_API
    + _FIX_DOC
    + "    return sum(1 for t in events if t >= now - size and t < now)\n",
}

_REVIEW = {
    **_COMMON,
    "challenge.yaml": _challenge_yaml("review", "after-run", "[subject.py]"),
    "problem.md": "## Task\n\n## API\n\n## Categories\n\n## Example\n",
    # Line numbers matter here: the seeded defects are on lines 10 and 12.
    "subject.py": (
        '"""Move money between two accounts held in one shared dict. Written by an AI assistant."""\n'
        "\n"
        "import threading\n"
        "\n"
        "LOCK = threading.Lock()\n"
        "\n"
        "\n"
        "def transfer(accounts: dict[str, int], src: str, dst: str, amount: int) -> None:\n"
        '    """Take `amount` from src and give it to dst. Refuse an overdraft."""\n'
        "    if accounts[src] - amount <= 0:\n"
        '        raise ValueError("insufficient funds")\n'
        "    accounts[src] -= amount\n"
        "    accounts[dst] += amount\n"
    ),
    "starter.py": (
        '"""Your review of subject.py: one (line, category) pair per defect you find."""\n\n'
        'FINDINGS: list[tuple[int, str]] = []  # e.g. [(17, "race")]; the categories are listed in the problem\n'
    ),
    "solution.py": '"""The seeded defects."""\n\nFINDINGS = [(10, "wrong-boundary"), (12, "race")]\n',
    "tests/test_visible.py": (
        "from solution import FINDINGS\n\n\n"
        "def test_findings_are_line_and_category_pairs():\n"
        '    assert FINDINGS, "List at least one finding: (line in subject.py, category)."\n'
        '    assert all(isinstance(line, int) and isinstance(cat, str) for line, cat in FINDINGS), "Each finding is (line number, category)."\n'
    ),
    "tests/test_hidden.py": (
        "from solution import FINDINGS\n\n"
        'SEEDED = {10: "wrong-boundary", 12: "race"}\n\n\n'
        "def _found(line: int, category: str) -> bool:\n"
        "    return any(abs(found_line - line) <= 2 and found_cat == category for found_line, found_cat in FINDINGS)\n\n\n"
        "def test_every_seeded_defect_is_found():\n"
        "    missed = [cat for line, cat in SEEDED.items() if not _found(line, cat)]\n"
        '    assert not missed, "A reviewer would still flag: " + ", ".join(missed) + ". Read the function once more, line by line."\n\n\n'
        "def test_at_most_one_false_positive():\n"
        "    extra = [f for f in FINDINGS if not any(abs(f[0] - line) <= 2 and f[1] == cat for line, cat in SEEDED.items())]\n"
        '    assert len(extra) <= 1, f"{len(extra)} findings point at code that is fine. Which ones would you defend in a real review?"\n'
    ),
}

_TESTS_SUBJECT = (
    "def clamp(n: float, low: float, high: float) -> float:\n"
    '    """Return n limited to the closed range [low, high]. Raise ValueError when low > high."""\n'
)
_TESTS = {
    **_COMMON,
    "challenge.yaml": _challenge_yaml("tests", "after-run", "[subject.py]", 25),
    "problem.md": TEMPLATE["problem.md"],
    "subject.py": '"""The code under test: correct, with its contract in the docstring. The learner reads it."""\n\n\n'
    + _TESTS_SUBJECT
    + "    if low > high:\n"
    '        raise ValueError("low must not exceed high")\n'
    "    return max(low, min(n, high))\n",
    "starter.py": (
        '"""Your tests for subject.py. Each function whose name starts with test_ is one test.\n\n'
        "They must pass on the real subject.py. On Submit, they also run against hidden buggy\n"
        "versions of it, and each buggy version must make at least one of your tests fail.\n"
        '"""\n\n'
        "from subject import clamp\n\n\n"
        "def test_returns_the_number_when_it_is_in_range():\n"
        "    assert clamp(5, 0, 10) == 5\n"
    ),
    "solution.py": (
        '"""Reference tests: they pass on subject.py and catch every mutant."""\n\n'
        "import pytest\n"
        "from subject import clamp\n\n\n"
        "def test_returns_the_number_when_it_is_in_range():\n"
        "    assert clamp(5, 0, 10) == 5\n\n\n"
        "def test_a_number_above_the_range_becomes_the_top():\n"
        "    assert clamp(15, 0, 10) == 10\n\n\n"
        "def test_a_number_below_the_range_becomes_the_bottom():\n"
        "    assert clamp(-3, 0, 10) == 0\n\n\n"
        "def test_an_inverted_range_is_refused():\n"
        "    with pytest.raises(ValueError):\n"
        "        clamp(5, 10, 0)\n"
    ),
    "mutants/01-only-a-floor.py": '"""Misconception: clamping only needs a floor; nobody passes a number above high."""\n\n\n'
    + _TESTS_SUBJECT
    + "    if low > high:\n"
    '        raise ValueError("low must not exceed high")\n'
    "    return max(low, n)\n",
    "mutants/02-accepts-an-inverted-range.py": '"""Misconception: an inverted range is the caller\'s problem."""\n\n\n'
    + _TESTS_SUBJECT
    + "    return max(low, min(n, high))\n",
}

_DESIGN_CLASS = (
    "class Deliveries:\n"
    '    """Hand each message to `send` under the guarantee you chose."""\n\n'
    "    def __init__(self) -> None:\n"
    "        self.seen: set[str] = set()\n\n"
    "    def deliver(self, message_id: str, send) -> None:\n"
)
_DESIGN_NOTE = (
    '"""Design note:\n\n'
    "Options: at-most-once (remember a message before sending it) or at-least-once (remember it after).\n"
    "Trade-off: a crash between remembering and sending loses a message; one between sending and remembering repeats it.\n"
    "Choice: at-most-once. A repeated message costs more here than a lost one.\n"
    "Failure mode: a message whose send fails is never retried.\n"
    '"""\n\n'
    'GUARANTEE = "at-most-once"\n\n\n'
)
_DESIGN = {
    **_COMMON,
    "challenge.yaml": _challenge_yaml("design", "after-run", "[]", 30),
    "problem.md": "## Task\n\n<!-- Name two or three options and the guarantee each gives. -->\n\n## API\n\n## Rules\n\n## Example\n",
    "starter.py": (
        '"""Design note (fill in every line before you code):\n\n'
        "Options: ...\n"
        "Trade-off: ...\n"
        "Choice: ...\n"
        "Failure mode: ...\n"
        '"""\n\n'
        'GUARANTEE = ""  # "at-most-once" or "at-least-once": the hidden tests check the one you declare\n\n\n'
        + _DESIGN_CLASS
        + "        send(message_id)\n"
    ),
    "solution.py": _DESIGN_NOTE + _DESIGN_CLASS + "        if message_id in self.seen:\n"
    "            return\n"
    "        self.seen.add(message_id)  # remember first: a failed send must not be repeated\n"
    "        send(message_id)\n",
    "tests/test_visible.py": (
        "from solution import GUARANTEE, Deliveries\n\n\n"
        "def test_a_guarantee_is_declared():\n"
        '    assert GUARANTEE in ("at-most-once", "at-least-once"), "Set GUARANTEE to the option your design note chose."\n\n\n'
        "def test_a_new_message_is_sent():\n"
        "    sent = []\n"
        '    Deliveries().deliver("m1", sent.append)\n'
        '    assert sent == ["m1"]\n'
    ),
    "tests/test_hidden.py": (
        "from solution import GUARANTEE, Deliveries\n\n\n"
        "def test_a_repeated_message_follows_the_guarantee():\n"
        "    sent = []\n"
        "    d = Deliveries()\n"
        '    d.deliver("m1", sent.append)\n'
        '    d.deliver("m1", sent.append)\n'
        '    if GUARANTEE == "at-most-once":\n'
        '        assert sent == ["m1"], "You declared at-most-once. What does a duplicate delivery look like under it?"\n'
        "    else:\n"
        '        assert "m1" in sent\n\n\n'
        "def test_a_failed_send_follows_the_guarantee():\n"
        "    calls = []\n\n"
        "    def flaky(message_id):\n"
        "        calls.append(message_id)\n"
        "        if len(calls) == 1:\n"
        '            raise ConnectionError("first send fails")\n\n'
        "    d = Deliveries()\n"
        "    try:\n"
        '        d.deliver("m1", flaky)\n'
        "    except ConnectionError:\n"
        "        pass\n"
        '    d.deliver("m1", flaky)\n'
        '    expected = 1 if GUARANTEE == "at-most-once" else 2\n'
        '    assert len(calls) == expected, f"You declared {GUARANTEE}. Do you remember the message before or after the send?"\n'
    ),
    "mutants/01-remembers-after-sending.py": _DESIGN_NOTE.replace(
        '"""Design note:', '"""Misconception: a message is delivered once it is sent, so remember it afterwards.\n\nDesign note:'
    )
    + _DESIGN_CLASS
    + "        if message_id in self.seen:\n"
    "            return\n"
    "        send(message_id)\n"
    "        self.seen.add(message_id)\n",
    "mutants/02-forgets-between-calls.py": _DESIGN_NOTE.replace(
        '"""Design note:', '"""Misconception: the caller never sends the same message twice.\n\nDesign note:'
    )
    + _DESIGN_CLASS
    + "        send(message_id)\n",
}

SCAFFOLDS = {"build": TEMPLATE, "predict": _PREDICT, "fix": _FIX, "review": _REVIEW, "tests": _TESTS, "design": _DESIGN}


def scaffold(kind: str) -> dict[str, str]:
    """The files of a toy question of this type. It passes `question add` as is; the author replaces every file."""
    return whiteboard_template() if kind == "whiteboard" else SCAFFOLDS[kind]


def whiteboard_template() -> dict[str, str]:
    """Files for a system design (whiteboard) question. See AUTHORING.md, "whiteboard"."""
    from .runner import WHITEBOARD_SECTIONS

    starter = "# {title}\n\n" + "".join(f"## {name}\n\n<!-- {what} -->\n\n" for name, what in WHITEBOARD_SECTIONS.items())
    return {
        "challenge.yaml": (
            "title: {title}  # name the scenario, not the technique\n"
            "type: whiteboard\n"
            "lesson: after-run  # the lesson opens after the learner's first section check\n"
            "difficulty: medium\nminutes: 45\ntags: []\n"
            "# variant_of: module/NN-slug  # set when this re-tests an earlier question on a new surface\n"
            "summary: One sentence about the system the learner designs.\n"
        ),
        "lesson.md": "## The idea\n\n## Subgoals\n\n## Numbers to know\n\n## Misconceptions\n\n## Interview angle\n\n## Tie-in to your work\n",
        "problem.md": "## Task\n\n## Scale\n\n## Out of scope\n\n## What the interviewer looks for\n",
        "hints.md": TEMPLATE["hints.md"].replace("tied to a named test", "tied to a named section"),
        "starter.md": starter,
        "solution.md": starter.replace("<!-- ", "").replace(" -->", ""),
        "rubric.yaml": (
            "# 5 to 10 points a strong design covers. Mark 3 or more must: true.\n"
            "points:\n"
            "  - id: example-point\n"
            "    section: API  # one of the design sections\n"
            "    must: true\n"
            "    point: What a strong design does here, in one sentence.\n"
            "    look_for: What to look for in the learner's text when you grade it.\n"
        ),
    }


def plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def fail(message: str, code: int = 1) -> int:
    print(message, file=sys.stderr)
    return code


def _state(settings):
    """The learner's progress store, and modules by id."""
    from .store import Store

    return Store(settings.db_path), {t.id: t for t in load_tracks(settings.tracks_dir)}


def _module_status(track, solved: set[str]) -> dict:
    keys = [c.key for c in track.challenges] if track else []
    return {"questions": len(keys), "solved": sum(k in solved for k in keys)}


# ---------- App ----------


def cmd_serve(args) -> int:
    import uvicorn

    from .server import create_app

    if args.host not in ("127.0.0.1", "localhost"):
        print("Warning: Whetstone runs the code you submit. Do not expose it to the internet.", file=sys.stderr)
    uvicorn.run(create_app(), host=args.host, port=args.port, log_level="info")
    return 0


def cmd_generate(args) -> int:
    from .generator import GenerationError, generate_challenge

    settings = load_settings()
    try:
        key = generate_challenge(settings, args.topic, args.module, None, args.difficulty, args.notes or "")
    except GenerationError as exc:
        return fail(f"Error: {exc}")
    print(f"Done: {key}")
    return 0


# ---------- Learning paths ----------


def _find_path(settings, path_id: str) -> LearningPath | None:
    return next((p for p in load_all_paths(settings.shared_paths_dir, settings.paths_dir) if p.id == path_id), None)


def cmd_path_create(args) -> int:
    settings = load_settings()
    path_id = slugify(args.id)
    if _find_path(settings, path_id):
        return fail(f"Path {path_id} already exists. Show it with: {CLI} path show {path_id}")
    lp = LearningPath(
        path_id, args.title or path_id.replace("-", " ").capitalize(), args.goal, domain=args.domain or "", companies=args.company or []
    )
    dest = save_path(settings.paths_dir, lp)
    print(f"Created path {path_id} in {_rel(dest)} (your own; never committed).")
    print(f"Add modules in order: {CLI} path add {path_id} <module> [<module> ...]")
    return 0


def cmd_path_add(args) -> int:
    from .catalog import find_problem

    settings = load_settings()
    lp = _find_path(settings, args.path)
    if lp is None:
        return fail(f'No path {args.path}. Create it with: {CLI} path create {args.path} --goal "..."')
    tracks = {t.id for t in load_tracks(settings.tracks_dir)}
    for raw in args.modules:
        module = slugify(raw)
        if module not in tracks and find_problem(settings, raw) is None:
            return fail(f"{raw} is neither a module nor a catalog problem. Create it with: {CLI} module create {module}")
        if module in lp.modules:
            print(f"{module} is already in the path.")
            continue
        lp.modules.append(module)
        print(f"Added {module}{'' if module in tracks else ' (not built yet)'}.")
    dest = save_path(settings.paths_dir, lp)
    if not lp.mine:
        print(f"Saved your copy in {_rel(dest)}. The shared path is unchanged.")
    return 0


def cmd_path_show(args) -> int:
    from .catalog import path_rows

    settings = load_settings()
    lp = _find_path(settings, args.path)
    if lp is None:
        return fail(f"No path {args.path}. List paths with: {CLI} path list")
    store, tracks = _state(settings)
    rows = path_rows(settings, lp, tracks, store.solved_keys())
    if args.json:
        print(
            json.dumps(
                {"id": lp.id, "title": lp.title, "goal": lp.goal, "domain": lp.domain, "companies": lp.companies, "modules": rows}, indent=2
            )
        )
        return 0
    print(f"{lp.title} ({lp.id})")
    if lp.domain or lp.companies:
        print(" · ".join(filter(None, [lp.domain, ", ".join(lp.companies)])))
    if lp.goal:
        print(f"Goal: {lp.goal}")
    print()
    width = max((len(r["title"]) for r in rows), default=0)
    for i, r in enumerate(rows, 1):
        status = f"{r['solved']} of {r['questions']} solved" if r["built"] else f"not built yet: {CLI} question brief {r['module']}"
        print(f"{i:2}. {r['module']:<26} {r['title']:<{width}}  {status}")
    if not rows:
        print(f"No modules yet. Add some: {CLI} path add {lp.id} <module> ...")
    return 0


def cmd_path_list(args) -> int:
    settings = load_settings()
    paths = load_all_paths(settings.shared_paths_dir, settings.paths_dir)
    if args.domain:
        paths = [p for p in paths if args.domain.lower() in p.domain.lower()]
    if args.json:
        print(
            json.dumps(
                [
                    {"id": p.id, "title": p.title, "goal": p.goal, "domain": p.domain, "companies": p.companies, "modules": p.modules}
                    for p in paths
                ],
                indent=2,
            )
        )
        return 0
    for domain in sorted({p.domain for p in paths}):
        print(f"\n{domain or 'Other'}")
        for p in (x for x in paths if x.domain == domain):
            who = f"; {', '.join(p.companies[:4])}" if p.companies else ""
            mine = " [yours]" if p.mine else ""
            print(f"  {p.id:<28} {p.title}{mine}  ({len(p.modules)} modules{who})")
    if not paths:
        print(f'No learning paths yet. Create one: {CLI} path create <id> --goal "..."')
    return 0


# ---------- Modules ----------


def cmd_module_create(args) -> int:
    from .catalog import find_problem
    from .generator import ensure_track

    settings = load_settings()
    module = slugify(args.id)
    title, description = args.title, args.description
    if args.from_catalog:
        problem = find_problem(settings, args.from_catalog)
        if problem is None:
            return fail(f"No catalog problem {args.from_catalog}. List them with: {CLI} catalog")
        title, description = title or problem["title"], description or problem.get("summary")
    if (settings.tracks_dir / module).exists():
        return fail(f"Module {module} already exists. Add a question: {CLI} question brief {module}")
    ensure_track(settings, module, title, description)
    print(f"Created module {module}. Next: {CLI} question brief {module}")
    return 0


def cmd_module_list(args) -> int:
    settings = load_settings()
    store, tracks = _state(settings)
    solved = store.solved_keys()
    rows = [{"module": t.id, "title": t.title, "description": t.description, **_module_status(t, solved)} for t in tracks.values()]
    if args.json:
        print(json.dumps(rows, indent=2))
        return 0
    width = max((len(r["title"]) for r in rows), default=0)
    for r in rows:
        print(f"{r['module']:<26} {r['title']:<{width}}  {r['solved']} of {r['questions']} solved")
    return 0


# ---------- Questions ----------


def cmd_question_brief(args) -> int:
    from .catalog import find_problem, make_brief

    settings = load_settings()
    module = slugify(args.module)
    problem = find_problem(settings, args.module)
    track = next((t for t in load_tracks(settings.tracks_dir) if t.id == module), None)
    if problem and not args.topic:
        text = make_brief(settings, problem, difficulty=args.difficulty, notes=args.notes or "", kind=args.type)
    else:
        topic = args.topic or (f"{track.title}: {track.description}" if track else None)
        if not topic:
            return fail(f'{module} is not a module or a catalog problem yet. Pass --topic "..." to say what it teaches.', 2)
        text = make_brief(settings, topic=topic, track=module, difficulty=args.difficulty, notes=args.notes or "", kind=args.type)
    print(text)
    return 0


def cmd_question_new(args) -> int:
    settings = load_settings()
    slug = slugify(args.slug)
    stage = settings.staging_dir / slug
    if stage.exists():
        return fail(f"{stage} already exists. Fill it in, or pick another slug.")
    title = args.title or slug.replace("-", " ").capitalize()
    for rel, body in scaffold(args.type or "build").items():
        dest = stage / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(body.replace("{title}", title), encoding="utf-8")  # not .format: the code templates hold braces
    rel_stage = _rel(stage)
    print(f"Created {rel_stage}/ with the files to fill in (see AUTHORING.md).")
    print(f"Then file it: {CLI} question add {rel_stage} --module {slugify(args.module)}")
    return 0


def cmd_question_add(args) -> int:
    from .catalog import find_problem
    from .generator import install_challenge

    settings = load_settings()
    stage = Path(args.dir)
    if not stage.is_dir():
        return fail(f"{args.dir} is not a folder.")
    module = slugify(args.module)
    problem = find_problem(settings, args.module)
    title, description = (problem["title"], problem.get("summary")) if problem else (None, None)
    print("Checking: the reference solution must pass, the starter must fail...")
    key, problems, notes = install_challenge(settings, stage, module, title, description)
    for note in notes:
        print(f"  {note}")
    if not key:
        print("NOT ADDED. Fix these problems, then run the same command again:")
        for p in problems:
            print(f"  ! {p}")
        return 1
    print(f"Added {key}.")
    print(f"Run `{CLI} question check {key}` twice more to catch flaky timing.")
    print(f"The learner can open it at http://localhost:8000/#/{key}")
    return 0


def cmd_question_check(args) -> int:
    from .runner import validate_challenge

    settings = load_settings()
    targets = [
        ch
        for track in load_tracks(settings.tracks_dir)
        for ch in track.challenges
        if not args.targets or any(ch.key == t or ch.track_id == t for t in args.targets)
    ]
    if not targets:
        return fail("No questions matched.")
    failed = 0
    for ch in targets:
        result = validate_challenge(ch, settings)
        print(f"[{'PASS' if result.ok else 'FAIL'}] {ch.key}")
        for note in result.notes:
            print(f"       {note}")
        for problem in result.problems:
            print(f"       ! {problem}")
        failed += not result.ok
    print(f"\n{len(targets) - failed}/{len(targets)} questions valid.")
    return 1 if failed else 0


# ---------- Catalog and the learner ----------


def cmd_catalog(args) -> int:
    from .catalog import catalog_links, find_problem, load_catalog

    settings = load_settings()
    store, tracks = _state(settings)
    solved = store.solved_keys()

    if args.problem:
        p = find_problem(settings, args.problem)
        if p is None:
            return fail(f"No catalog problem {args.problem!r}. List them with: {CLI} catalog")
        p = {**p, "links": catalog_links(p, tracks, solved)}
        if args.json:
            print(json.dumps(p, indent=2))
            return 0
        print(f"{p['title']} ({p['id']})\n{p.get('summary', '')}\n")
        for link in p["links"]:
            print(f"Practice: {link['track']}/{link['challenge']} ({link['solved']} of {link['total']} solved)")
        if not p["links"] and p.get("format") != "design":
            print(f"No questions yet. Build one: {CLI} question brief {p['id']}")
        print(f"\n{len(p['reports'])} reports:")
        for r in p["reports"]:
            meta = ", ".join(str(x) for x in (r["round"], r.get("level"), r.get("year"), f"{r['confidence']} confidence") if x)
            print(f"\n- {r['company']} ({meta})\n  {r['question']}")
            for f in r.get("follow_ups", []):
                print(f"    -> {f}")
            for s in r.get("sources", []):
                print(f"    {s}")
        return 0

    q = (args.search or "").lower()
    rows = []
    for p in load_catalog(settings):
        hits = [
            r
            for r in p["reports"]
            if (not args.company or r["company"].lower() == args.company.lower()) and (not args.round or r["round"] == args.round)
        ]
        text = " ".join([p["title"], p.get("summary", ""), *p.get("tags", []), *(r["question"] for r in p["reports"])]).lower()
        if hits and (not q or q in text):
            rows.append((p, hits, catalog_links(p, tracks, solved)))
    rows.sort(key=lambda row: (-len(row[1]), row[0]["id"]))
    if args.json:
        print(
            json.dumps(
                [
                    {
                        "id": p["id"],
                        "title": p["title"],
                        "summary": p.get("summary", ""),
                        "format": p.get("format"),
                        "reports": len(hits),
                        "companies": sorted({r["company"] for r in hits}),
                        "links": links,
                    }
                    for p, hits, links in rows
                ],
                indent=2,
            )
        )
        return 0
    for p, hits, links in rows:
        if p.get("format") == "design":
            status = "discussion"
        elif links:
            status = f"{sum(lk['solved'] for lk in links)}/{sum(lk['total'] for lk in links)} solved"
        else:
            status = "not built"
        companies = list(dict.fromkeys(r["company"] for r in hits))
        more = f" +{len(companies) - 4}" if len(companies) > 4 else ""
        print(f"{len(hits):3}  {p['id']:<26} {status:<11} {p['title']}  [{', '.join(companies[:4])}{more}]")
    print(f"\n{len(rows)} problem{'' if len(rows) == 1 else 's'}. Details: {CLI} catalog <id>")
    return 0


def cmd_progress(args) -> int:
    from .store import progress_rows

    settings = load_settings()
    store, tracks = _state(settings)
    rows = progress_rows(store, tracks.values())
    week = store.week()
    types = {kind: sum(r["type"] == kind for r in rows) for kind in QUESTION_TYPES}  # zeros show which types nobody built
    if args.json:
        print(json.dumps({"week": week, "active_days": store.active_days(), "types": types, "questions": rows}, indent=2))
        return 0
    done = sum(r["status"] == "solved" for r in rows)
    print(
        f"This week: {week['this_week']} of {week['target']} practice days. Weekly streak: {week['streak']}. Solved {done} of {len(rows)} questions."
    )
    print("By type: " + ", ".join(f"{kind} {n}" for kind, n in types.items()) + ".\n")
    for r in rows:
        last = r["last_run"]
        notes = [f"runs={r['runs']}", f"hints={r['hints_opened']}/{r['hint_count']}"]
        if r["solution_viewed"]:
            notes.append("viewed solution")
        if r["solve"]:
            notes.append("mastered" if r["mastered"] else f"{r['solve']} solve")
        if r["review_due"]:
            notes.append(f"review due {r['review_due']}")
        if last:
            notes.append(f"last {last['mode']}: {last['status']} {last['passed']}/{last['total']}")
        print(f"{r['status']:<9} {r['key']:<46} {' '.join(notes)}")
    return 0


def _question_or_none(settings, key: str):
    track_id, _, cid = key.partition("/")
    try:
        return find_challenge(settings.tracks_dir, track_id, cid)
    except ContentError as exc:
        print(f"{exc}. List questions with: {CLI} progress", file=sys.stderr)
        return None


def cmd_draft(args) -> int:
    settings = load_settings()
    store, _ = _state(settings)
    c = _question_or_none(settings, args.key)
    if c is None:
        return 1
    code, last, opened = store.get_draft(c.key), store.last_run(c.key), store.reveals(c.key)
    starter = c.read(c.starter_file)
    if code == starter:
        code = None
    print(f"# {c.key}: {c.title}")
    print(f"Last run: {last['mode']} {last['status']} {last['passed']}/{last['total']} at {last['created_at']}" if last else "No runs yet.")
    print(
        f"Hints opened: {sum(w.startswith('hint') for w in opened)} of {len(c.hints())}. Solution viewed: {'yes' if 'solution' in opened else 'no'}."
    )
    if c.is_whiteboard:
        review = store.latest_review(c.key)
        print(f"Rubric: {_rel(c.path / 'rubric.yaml')}. Last review: {review['created_at'] if review else 'none yet'}.")
        print(f"Grade it with: {CLI} grade {c.key} < grade.json   (see the whetstone-review skill)")
    print(f"\n## The learner's {c.editor_file}{' (untouched starter)' if code is None else ''}\n")
    print(code if code is not None else starter)
    if c.is_whiteboard:
        from .runner import drawing_mermaid

        mermaid, notes = drawing_mermaid(store.get_drawing(c.key))
        print("\n## The learner's whiteboard drawing, as Mermaid\n")
        print(f"```mermaid\n{mermaid}\n```" if mermaid else "(nothing drawn yet)")
        for n in notes:
            print(f"- Also on the board: {n}")
    return 0


def cmd_grade(args) -> int:
    """Record your grade of the learner's system design, point by point against its rubric."""
    from .runner import grade_design

    settings = load_settings()
    store, _ = _state(settings)
    c = _question_or_none(settings, args.key)
    if c is None:
        return 1
    if not c.is_whiteboard:
        return fail(f"{c.key} is a {c.kind} question. grade is for system designs (type: whiteboard); use note for code.")
    raw = Path(args.file).read_text(encoding="utf-8") if args.file else sys.stdin.read()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        return fail(f"The grade is not valid JSON: {exc}")
    grade, problems = grade_design(c, payload)
    if problems:
        print("NOT RECORDED. Fix these, then run the same command again:")
        for p in problems:
            print(f"  ! {p}")
        return 1
    design = store.get_draft(c.key) or c.read(c.starter_file)
    store.add_review(c.key, grade["points"], grade["summary"])
    first = store.record_run(c.key, "submit", grade["status"], grade["covered"], grade["total"], 0.0, design)
    musts = [p for p in grade["points"] if p["must"] and p["verdict"] != "covered"]
    store.record_event(
        c.key, "reviewed", {"covered": grade["covered"], "total": grade["total"], "passed": grade["status"] == "passed", "solved": first}
    )
    print(f"Recorded: {grade['covered']} of {plural(grade['total'], 'point')} covered.", end=" ")
    if grade["status"] == "passed":
        print("Every must-have is covered" + (": solved." if first else "."))
    else:
        print(f"{plural(len(musts), 'must-have')} still open: {', '.join(p['id'] for p in musts)}.")
    return 0


def cmd_test(args) -> int:
    from .runner import run_tests

    settings = load_settings()
    store, _ = _state(settings)
    c = _question_or_none(settings, args.key)
    if c is None:
        return 1
    code = store.get_draft(c.key)
    code = code if code is not None else c.read(c.starter_file)
    # ponytail: not recorded as a run, so the learner's progress only reflects their own runs
    if c.is_whiteboard:
        from .runner import check_whiteboard

        report = check_whiteboard(code, store.get_drawing(c.key))
    else:
        report = run_tests(c, code, "submit" if args.all else "run", settings)
    print(f"{report.status.upper()}: {report.summary}")
    for t in report.tests:
        if t.outcome != "passed":
            print(f"- {t.label}{' (hidden)' if t.hidden else ''}: {t.outcome}. {t.message}")
    if report.status in ("error", "timeout"):
        print(report.output[-3000:])
    return 0 if report.status == "passed" else 1


def _clock_check(tz: str, in_container: bool) -> tuple[bool | None, str, str]:
    """A Docker container's clock runs on UTC unless TZ is set, so practice done in the evening
    would be dated tomorrow. Returns a doctor finding: (ok, what, fix)."""
    from datetime import datetime
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    fix = "Set TZ=<your zone, e.g. America/Chicago> in .env, then run: docker compose up -d"
    where = " (bin/whetstone doctor ran inside the container, whose clock this is, not your computer's)"
    if not tz:
        if in_container:
            return None, "Clock: UTC, because TZ is not set" + where, fix
        return True, f"Clock: {datetime.now().astimezone().tzname()} (the system's)", ""
    try:
        expected = datetime.now(ZoneInfo(tz)).utcoffset()
    except ZoneInfoNotFoundError:
        return None, f"Clock: TZ={tz} is not a zone this system knows", fix
    actual = datetime.now().astimezone()
    if expected != actual.utcoffset():
        return None, f"Clock: TZ={tz} is set, but the clock runs on {actual.tzname()}" + (where if in_container else ""), fix
    return True, f"Clock: {tz}", ""


def cmd_doctor(args) -> int:
    """Check the setup, and say how to fix each problem. Exits with 1 when something is broken."""
    import os
    import platform
    import subprocess
    import urllib.request

    from .catalog import load_catalog
    from .config import ROOT
    from .server import _redis_ok
    from .store import Store

    settings = load_settings()
    results: list[tuple[bool | None, str, str]] = []  # (True ok, None warning, False broken), what, fix

    def check(ok: bool | None, what: str, fix: str = "") -> None:
        results.append((ok, what, fix))

    check(sys.version_info >= (3, 11), f"Python {platform.python_version()}", "Install Python 3.11 or newer, or run Whetstone with Docker.")

    user = settings.user_dir
    user.mkdir(parents=True, exist_ok=True)
    check(os.access(user, os.W_OK), f"Your data folder: {_rel(user)}", "Make it writable, or point WHETSTONE_HOME at a folder you own.")
    try:
        store = Store(settings.db_path)
        saved = f", the old one was saved as {_rel(store.backup)}" if store.backup else ""
        check(True, f"Progress database: schema {store.schema_version()}{saved}")
    except Exception as exc:  # noqa: BLE001 - report any database problem as a finding
        check(False, f"Progress database: {exc}", "Update Whetstone (git pull), or restore a whetstone.db.v*.bak backup.")

    has_profile = (user / "profile.md").exists()
    check(
        has_profile or None,
        "Your profile: " + ("my/profile.md" if has_profile else "not set up yet"),
        'Ask your agent: "Set up my Whetstone profile."',
    )
    if has_profile:
        header = load_profile(user / "profile.md")
        filled = [k for k, v in header.items() if v]
        check(
            bool(filled) or None,
            f"Profile header for the dashboard: {', '.join(filled) if filled else 'missing or empty'}",
            'Ask your agent: "Update my Whetstone profile header." (the whetstone-profile skill)',
        )

    problems, paths = load_catalog(settings), load_all_paths(settings.shared_paths_dir, settings.paths_dir)
    check(
        bool(problems), f"Shared content: {len(problems)} modules, {len(paths)} learning paths", "Run git pull, or check WHETSTONE_CONTENT."
    )

    try:
        tracks = load_tracks(settings.tracks_dir)
    except ContentError as exc:
        tracks = []
        check(False, f"Your questions: {exc}", "Fix or remove the broken question folder.")
    questions = [c for t in tracks for c in t.challenges]
    check(
        bool(questions) or None,
        f"Your questions: {len(questions)} in {plural(len(tracks), 'module')}",
        'Ask your agent: "Build the first Whetstone question for <module>."',
    )
    old = [c.key for c in questions if (c.path / "hints.md").exists() and len(c.hints()) != 4]
    if old:
        check(
            None,
            f"{plural(len(old), 'question')} use the older format (not 4 hints). They still work.",
            "To upgrade one, ask your agent to rewrite its hints as the 4-rung ladder in AUTHORING.md.",
        )

    needs = [c.key for c in questions if "redis" in c.requires]
    redis_up = _redis_ok(settings.redis_url)
    check(
        redis_up or (None if not needs else False),
        f"Redis at {settings.redis_url}: {'reachable' if redis_up else 'not reachable'}"
        + (f", needed by {plural(len(needs), 'question')}" if needs else ""),
        "Start it with docker compose up -d, or on a Mac: brew install redis && brew services start redis.",
    )

    try:
        with urllib.request.urlopen("http://127.0.0.1:8000/api/config", timeout=1) as resp:  # noqa: S310 - fixed local URL
            app_up = resp.status == 200
    except OSError:
        app_up = False
    check(
        app_up or None,
        f"Web app at http://localhost:8000: {'running' if app_up else 'not running'}",
        "Start it with docker compose up -d, or bin/whetstone serve.",
    )

    check(*_clock_check(os.environ.get("TZ", ""), in_container=Path("/.dockerenv").exists()))

    if (ROOT / ".git").exists() and user.resolve().is_relative_to(ROOT):
        rel = user.resolve().relative_to(ROOT).as_posix()
        ignored = subprocess.run(["git", "-C", str(ROOT), "check-ignore", "-q", rel], check=False).returncode == 0
        tracked = subprocess.run(["git", "-C", str(ROOT), "ls-files", rel], capture_output=True, text=True, check=False).stdout.split()
        check(
            ignored and not tracked,
            f"Git ignores {rel}/, so your work can't be pushed by accident"
            if ignored and not tracked
            else f"Git does not fully ignore {rel}/",
            f"Keep {rel}/ in .gitignore, and run: git rm -r --cached {rel}",
        )

    skills = sorted((ROOT / ".claude" / "skills").glob("*/SKILL.md"))
    check(
        bool(skills) or None,
        f"Agent skills: {', '.join(s.parent.name for s in skills) or 'none found'}",
        "Run git pull to get .claude/skills/.",
    )

    marks = {True: "ok ", None: " ! ", False: "ERR"}
    for ok, what, fix in results:
        print(f"[{marks[ok]}] {what}")
        if ok is not True and fix:
            print(f"        {fix}")
    broken, warnings = sum(r[0] is False for r in results), sum(r[0] is None for r in results)
    print(f"\n{'All good.' if not broken and not warnings else f'{broken} to fix, {warnings} to look at.'}")
    return 1 if broken else 0


# ---------- Live pair ----------


def cmd_watch(args) -> int:
    """Stream what the learner does in the app, one JSON object per line, for an agent to react
    to (see the whetstone-pair skill). Typing is merged into one "paused" event after a pause,
    so the agent wakes on moments, not keystrokes."""
    import time
    from datetime import datetime

    from .store import Store

    settings = load_settings()
    store = Store(settings.db_path)
    last = store.last_event_id()
    editing: dict[str, dict] = {}  # question -> {"since", "last", "lines"}
    current, quiet_since, idle_sent = None, time.monotonic(), False
    stop_at = time.monotonic() + args.seconds if args.seconds else None

    def emit(event: str, question: str | None, **data) -> None:
        line = {"at": datetime.now().isoformat(timespec="seconds"), "event": event, "question": question}
        line |= {"pair": store.setting("pair_mode", "quiet"), **data}
        print(json.dumps(line), flush=True)

    def flush(question: str) -> None:
        e = editing.pop(question, None)
        if e:
            extra = {"shapes": e["shapes"]} if "shapes" in e else {}  # a whiteboard drawing changed
            emit("paused", question, editing_seconds=round(e["last"] - e["since"]), lines=e["lines"], **extra)

    emit("watching", args.key, note=f'Read the code with: {CLI} draft <question>. Reply with: {CLI} note <question> "..." --line N')
    from .server import request_ask

    # Work the learner queued before the watch started comes first.
    for r in reversed(store.requests(open_only=True)):
        emit("requested", None, id=r["id"], kind=r["kind"], target=r["target"], status=r["status"], ask=request_ask(r))
    store.mark_agent_seen()
    last_seen = time.monotonic()
    try:
        while not stop_at or time.monotonic() < stop_at:
            now = time.monotonic()
            if now - last_seen >= HEARTBEAT_SECONDS:
                store.mark_agent_seen()  # the app shows "Agent connected" while this stays fresh
                last_seen = now
            for e in store.events_after(last):
                last = e["id"]
                if args.key and e["challenge"] not in (None, args.key):
                    continue
                quiet_since, idle_sent = now, False
                if e["kind"] == "edited":
                    entry = editing.setdefault(e["challenge"], {"since": now, "lines": 0})
                    entry |= {"last": now} | {k: e["data"][k] for k in ("lines", "shapes") if k in e["data"]}
                    continue
                if e["challenge"]:
                    flush(e["challenge"])
                    current = e["challenge"]
                emit(e["kind"], e["challenge"], **e["data"])
            for question in [q for q, e in editing.items() if now - e["last"] >= args.pause]:
                flush(question)
            if current and not idle_sent and not editing and now - quiet_since >= args.idle:
                emit("idle", current, minutes=round(args.idle / 60))
                idle_sent = True
            time.sleep(1)
        for question in list(editing):
            flush(question)
    except KeyboardInterrupt:
        pass
    return 0


def cmd_note(args) -> int:
    """Show a short remark to the learner in the app, next to their code."""
    from .store import Store

    settings = load_settings()
    track_id, _, cid = args.key.partition("/")
    try:
        find_challenge(settings.tracks_dir, track_id, cid)
    except ContentError as exc:
        return fail(str(exc))
    text = args.text.strip()
    if not text or len(text) > 600:
        return fail("A note needs 1 to 600 characters. Keep it to one idea.")
    Store(settings.db_path).add_note(args.key, text, args.line)
    print(f"Noted on {args.key}" + (f", line {args.line}." if args.line else "."))
    return 0


HEARTBEAT_SECONDS = 5


def cmd_requests(args) -> int:
    """Work the learner queued for you in the app."""
    from .server import request_ask
    from .store import Store

    rows = Store(load_settings().db_path).requests(open_only=not args.all)
    if args.json:
        print(json.dumps([r | {"ask": request_ask(r)} for r in rows], indent=2))
        return 0
    if not rows:
        print("Nothing queued.")
    for r in rows:
        print(f"#{r['id']:<4} {r['status']:<9} {request_ask(r)}" + (f"  -> {r['result']}" if r.get("result") else ""))
    return 0


def cmd_request(args) -> int:
    """Claim a queued request, then mark it done or failed, so the app shows its progress."""
    from .store import Store

    store = Store(load_settings().db_path)
    moves = {"claim": ("claimed", ("queued",)), "done": ("done", ("queued", "claimed")), "fail": ("failed", ("queued", "claimed"))}
    status, allowed = moves[args.action]
    r = store.update_request(args.id, status, args.result, only_from=allowed)
    if not r:
        return fail(f"Request #{args.id} is not open (already done, failed, cancelled or claimed).")
    store.record_event(None, f"request-{status}", {"id": r["id"], "kind": r["kind"], "target": r["target"], "result": r.get("result")})
    print(f"Request #{r['id']} {status}." + (f" {r['result']}" if r.get("result") else ""))
    return 0


# ---------- Parser ----------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="whetstone", description="Self-hosted practice dojo. AI agents: read AGENTS.md.")
    sub = parser.add_subparsers(dest="cmd")

    def cmd(group, name, func, help_text):
        p = group.add_parser(name, help=help_text, description=help_text)
        p.set_defaults(func=func)
        return p

    cmd(sub, "doctor", cmd_doctor, "check the setup and say how to fix each problem")
    p = cmd(sub, "serve", cmd_serve, "start the web app")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)

    # Learning paths
    paths = sub.add_parser("path", help="learning paths: ordered modules toward a goal").add_subparsers(dest="action", required=True)
    p = cmd(paths, "create", cmd_path_create, "create a learning path")
    p.add_argument("id")
    p.add_argument("--goal", default="", help="what the learner wants to be able to do")
    p.add_argument("--title")
    p.add_argument("--domain", help='e.g. "Payments & fintech"')
    p.add_argument("--company", action="append", help="a company whose system this path models; repeat for more")
    p = cmd(paths, "add", cmd_path_add, "append modules (or catalog problems to build later) to a path")
    p.add_argument("path")
    p.add_argument("modules", nargs="+")
    p = cmd(paths, "show", cmd_path_show, "a path's modules, in order, with progress")
    p.add_argument("path")
    p.add_argument("--json", action="store_true")
    p = cmd(paths, "list", cmd_path_list, "all learning paths, grouped by domain")
    p.add_argument("--domain", help="only paths whose domain contains this text")
    p.add_argument("--json", action="store_true")

    # Modules
    modules = sub.add_parser("module", help="modules: a topic made of ordered questions").add_subparsers(dest="action", required=True)
    p = cmd(modules, "create", cmd_module_create, "create an empty module")
    p.add_argument("id")
    p.add_argument("--title")
    p.add_argument("--description")
    p.add_argument("--from-catalog", metavar="PROBLEM", help="take the title and summary from a catalog problem")
    p = cmd(modules, "list", cmd_module_list, "all modules with progress")
    p.add_argument("--json", action="store_true")

    # Questions
    questions = sub.add_parser("question", help="questions: one exercise each (lesson, code, tests)").add_subparsers(
        dest="action", required=True
    )
    p = cmd(questions, "brief", cmd_question_brief, "instructions for writing the next question in a module")
    p.add_argument("module", help="module id, or a catalog problem id")
    p.add_argument(
        "--type", choices=QUESTION_TYPES, help="ask for this type instead of the recipe's suggestion; whiteboard: a system design"
    )
    p.add_argument("--topic", help="what the question teaches, for a module that is not in the catalog")
    p.add_argument("--difficulty", default="medium", choices=["easy", "medium", "hard"])
    p.add_argument("--notes", help="what the learner asked for")
    p = cmd(questions, "new", cmd_question_new, "scaffold a question's files in my/.staging/<slug>/")
    p.add_argument("module")
    p.add_argument("slug")
    p.add_argument("--title")
    p.add_argument(
        "--type", choices=QUESTION_TYPES, help="the question type to scaffold (default build); whiteboard: Markdown and a rubric"
    )
    p = cmd(questions, "add", cmd_question_add, "check a written question and file it as the module's next question")
    p.add_argument("dir")
    p.add_argument("--module", required=True)
    p = cmd(questions, "check", cmd_question_check, "check questions: the reference passes and the starter fails")
    p.add_argument("targets", nargs="*", help="module or module/question; empty = all")

    p = cmd(sub, "validate", cmd_question_check, "same as: question check")
    p.add_argument("targets", nargs="*")

    # Catalog and the learner
    p = cmd(sub, "catalog", cmd_catalog, "problems reported at real companies, or one in full")
    p.add_argument("problem", nargs="?")
    p.add_argument("--company")
    p.add_argument("--round", help="practical-coding, system-design, low-level-design, concurrency, debugging, ...")
    p.add_argument("--search")
    p.add_argument("--json", action="store_true")
    p = cmd(sub, "progress", cmd_progress, "what the learner solved, attempted and struggled with")
    p.add_argument("--json", action="store_true")
    p = cmd(sub, "draft", cmd_draft, "the learner's current code for a question")
    p.add_argument("key", help="module/question, e.g. rate-limiter/01-token-bucket")
    p = cmd(sub, "test", cmd_test, "run the tests on the learner's current code (not recorded)")
    p.add_argument("key")
    p.add_argument("--all", action="store_true", help="include hidden tests")

    p = cmd(sub, "watch", cmd_watch, "stream the learner's activity in the app as JSON lines, for a pairing agent")
    p.add_argument("--key", help="only this question (module/question)")
    p.add_argument("--pause", type=int, default=20, help="seconds without typing before a 'paused' event (default 20)")
    p.add_argument("--idle", type=int, default=600, help="seconds of no activity before an 'idle' event (default 600)")
    p.add_argument("--for", dest="seconds", type=int, default=0, help="stop after this many seconds (default: run until stopped)")
    p = cmd(sub, "requests", cmd_requests, "work the learner queued for you in the app (build a module, a variant, a path)")
    p.add_argument("--all", action="store_true", help="include finished requests")
    p.add_argument("--json", action="store_true")
    p = cmd(sub, "request", cmd_request, "claim a queued request, then mark it done or failed")
    p.add_argument("action", choices=["claim", "done", "fail"])
    p.add_argument("id", type=int)
    p.add_argument("--result", help="done: the question key you built; fail: the reason, in one line")
    p = cmd(sub, "grade", cmd_grade, "record your grade of a system design against its rubric (JSON on stdin or --file)")
    p.add_argument("key", help="module/question")
    p.add_argument("--file", help="read the grade from this file instead of stdin")
    p = cmd(sub, "note", cmd_note, "show a short remark to the learner in the app, next to their code")
    p.add_argument("key", help="module/question")
    p.add_argument("text")
    p.add_argument("--line", type=int, help="pin the note to a line of the learner's file (solution.py or design.md)")

    p = cmd(sub, "generate", cmd_generate, "write a question with the Anthropic API (needs ANTHROPIC_API_KEY)")
    p.add_argument("topic")
    p.add_argument("--module", default="generated")
    p.add_argument("--difficulty", default="medium", choices=["easy", "medium", "hard"])
    p.add_argument("--notes")

    args = parser.parse_args(argv)
    if not args.cmd:
        args = parser.parse_args(["serve"])
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

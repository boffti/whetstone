"""The catalog of reported interview problems in content/catalog.yaml."""

from __future__ import annotations

from pathlib import Path

import yaml

from .config import EXAMPLE, ROOT, Settings
from .content import LearningPath, Track, load_profile, load_tracks, slugify

CLI = "bin/whetstone"


_catalog_cache: dict[Path, tuple[int, list[dict]]] = {}


def load_catalog(settings: Settings) -> list[dict]:
    """Parsed once per file change: the catalog is large and path views read it per module.
    Callers must not mutate the returned problems."""
    path = settings.content_dir / "catalog.yaml"
    if not path.exists():
        return []
    mtime = path.stat().st_mtime_ns
    cached = _catalog_cache.get(path)
    if cached and cached[0] == mtime:
        return cached[1]
    loader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)  # the C parser is ~10x faster when available
    problems = (yaml.load(path.read_text(encoding="utf-8"), Loader=loader) or {}).get("problems", [])
    _catalog_cache[path] = (mtime, problems)
    return problems


def find_problem(settings: Settings, pid: str) -> dict | None:
    return next((p for p in load_catalog(settings) if p["id"] == pid), None)


def catalog_links(problem: dict, tracks: dict[str, Track], solved: set[str]) -> list[dict]:
    """Where a problem can be practiced: its curated `track` link, then its own built track."""
    links = []
    for target in dict.fromkeys(filter(None, [problem.get("track"), slugify(problem["id"])])):
        track_id, _, cid = target.partition("/")
        track = tracks.get(track_id)
        chs = [c for c in track.challenges if not cid or c.dir_name == cid] if track else []
        if not chs:
            continue
        nxt = next((c for c in chs if c.key not in solved), chs[0])
        links.append(
            {
                "track": track.id,
                "challenge": nxt.dir_name,
                "title": chs[0].title if cid else track.title,
                "total": len(chs),
                "solved": sum(c.key in solved for c in chs),
                "own": track.id == slugify(problem["id"]),
            }
        )
    return links


def path_rows(settings: Settings, lp: LearningPath, tracks: dict[str, Track], solved: set[str]) -> list[dict]:
    """A path's modules in order, built or not, with progress and the question to open next."""
    problems = {p["id"]: p for p in load_catalog(settings)}
    rows = []
    for module in lp.modules:
        track = tracks.get(module)
        problem = problems.get(module, {})
        chs = track.challenges if track else []
        nxt = next((c for c in chs if c.key not in solved), chs[0] if chs else None)
        rows.append(
            {
                "module": module,
                "title": track.title if track else problem.get("title", module),
                "summary": problem.get("summary") or (track.description if track else ""),
                "reports": len(problem.get("reports", [])),
                "built": bool(chs),
                "questions": len(chs),
                "planned": len(RECIPE),  # a module grows one question at a time, through the recipe
                "solved": sum(c.key in solved for c in chs),
                "next": nxt.dir_name if nxt else None,
            }
        )
    return rows


RANK = {"high": 0, "medium": 1, "low": 2}
# One finished question per type, for "copy the quality of".
EXAMPLES_BY_TYPE = {
    "build": "examples/memoize/",
    "tests": "examples/retry-tests/",
    "predict": "examples/limiter-predict/",
    "fix": "examples/payments-fix/",
    "review": "examples/payout-review/",
    "whiteboard": "examples/short-links-whiteboard/",
}


def report_line(r: dict) -> str:
    """One report for the brief. A low-confidence report is a title seen once on an aggregator,
    paraphrased, so it is labelled; the first source link is what grounded_in should cite."""
    meta = [r["round"], r.get("year"), "title only" if r.get("confidence") == "low" else None]
    follow = f" Follow-ups: {'; '.join(r['follow_ups'][:3])}" if r.get("follow_ups") else ""
    source = f" Source: {r['sources'][0]}" if r.get("sources") else ""
    return f"- {r['company']} ({', '.join(str(m) for m in meta if m)}): {r['question']}{follow}{source}"


def pick_reports(reports: list[dict], limit: int = 8) -> list[dict]:
    """The reports a brief shows: high and medium confidence first, newest first, then title-only
    ones fill the rest so new companies still appear."""
    ordered = sorted(reports, key=lambda r: (RANK.get(r.get("confidence"), 2), -(r.get("year") or 0)))
    solid = [r for r in ordered if r.get("confidence") != "low"][: limit - 2] if len(ordered) > limit else ordered
    rest = [r for r in ordered if r not in solid]
    return (solid + rest)[:limit]


def _rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def make_brief(
    settings: Settings,
    problem: dict | None = None,
    topic: str | None = None,
    track: str | None = None,
    difficulty: str = "medium",
    notes: str = "",
    kind: str | None = None,
    ratings: dict[str, str] | None = None,
) -> str:
    """Instructions for an AI agent to write a module's next question, for a catalog problem or a free topic.
    kind asks for one question type instead of the recipe's suggestion; "whiteboard" is a system design question.
    ratings maps the module's question keys to how the learner rated them."""
    whiteboard = kind == "whiteboard"
    if problem:
        track_id, track_title = slugify(problem["id"]), problem["title"]
        topic = f"{problem['title']}: {problem.get('summary', '')}"
        reports = problem.get("reports", [])
        if whiteboard:
            reports = [r for r in reports if r.get("round") == "system-design"] or reports
        reports = pick_reports(reports)
    elif topic and track:
        track_id, track_title, reports = slugify(track), track, []
    else:
        raise ValueError("Give a catalog problem, or both a topic and a module.")

    tracks = load_tracks(settings.tracks_dir)
    existing_track = next((t for t in tracks if t.id == track_id), None)
    challenges = existing_track.challenges if existing_track else []
    rated = {k: v.replace("-", " ") for k, v in (ratings or {}).items()}
    existing = [
        f"- {c.dir_name}: {c.title} ({c.kind}, {c.difficulty}"
        f"{f', variant of {c.variant_of}' if c.variant_of else ''}{f', rated {rated[c.key]}' if c.key in rated else ''})"
        for c in challenges
    ]
    position = sum(not c.variant_of for c in challenges) + 1  # a variant re-tests an earlier slot; it does not advance the recipe
    ai_handles = load_profile(settings.profile_path).get("ai_handles", [])

    lines = [
        f'# Whetstone brief: {"a system design question" if whiteboard else "the next question"} in the "{track_title}" module',
        "",
        "You are writing one system design question for Whetstone: an interview prompt the learner answers in "
        "Markdown, with Mermaid diagrams, on a scratchpad you can watch. Whetstone checks every section is filled "
        "in; later you grade the design against the rubric you write now (bin/whetstone grade)."
        if whiteboard
        else "You are writing one hands-on question for Whetstone. The learner reads a lesson, writes code in "
        "solution.py, and is graded by pytest. You do the writing; Whetstone checks your work.",
        "",
        "## Read first",
        "- AUTHORING.md: the file format, the question types, the test-writing rules and mutants/. Follow it exactly.",
        "- docs/PEDAGOGY.md: why the format works this way. Skim it once.",
        f"- {_rel(settings.profile_path)}: who the learner is, their goals, and how to write for them.",
        f"- {EXAMPLES_BY_TYPE[kind]}: a finished {kind} question to match for quality."
        if kind in EXAMPLES_BY_TYPE
        else f"- {_rel(EXAMPLE)}/ and examples/retry-tests/, plus the example for the type you choose "
        f"({', '.join(f'{k}: {v}' for k, v in EXAMPLES_BY_TYPE.items() if k not in ('build', 'tests', 'whiteboard'))}): "
        "finished questions to match for quality.",
    ]
    if settings.profile_path.name == "profile.example.md":
        lines.append("- The learner has no profile yet. First create my/profile.md from that template (see AGENTS.md, 'First run').")
    lines += ["", "## What to build", f"Topic: {topic}", f"Module: {track_id}", f"Difficulty: {difficulty}"]
    if notes:
        lines.append(f"Learner's notes: {notes}")
    if existing:
        lines += [
            "Already in this module (for context; design the system around these ideas):"
            if whiteboard
            else "Already in this module (write the next step up, do not repeat these):",
            *existing,
        ]
        if rated:
            lines.append(
                "The ratings are the learner's own, one tap after Submit: after 'too hard' stay on the concept with "
                "more scaffolding; after 'too easy' skip a step; after 'artificial' put the next one in their real work."
            )
    else:
        lines.append("This module is empty: write its first question.")
    lines += ["", "## Question type"]
    if whiteboard:
        lines.append("whiteboard: follow the whiteboard section of AUTHORING.md. Copy the quality of examples/short-links-whiteboard/.")
    elif kind:
        lines.append(f"{kind}: requested. Follow the {kind} section of AUTHORING.md.")
    else:
        lines.append(_recipe_line(position))
    lines.append(f"The learner's AI handles: {', '.join(ai_handles) or 'nothing listed in the profile'}.")
    if not kind and names_thesis_skill(ai_handles) and position <= 3 and not any(c.kind in THESIS_TYPES for c in challenges):
        lines.append(
            "That names tests, code review or reading code: the skills that fade fastest. Pull a tests or review question "
            "forward to position 2 or 3; do not wait for position 4. This outranks the suggestion above."
        )
    if reports:
        lines += ["", "## Real interview reports to ground it in", *[report_line(r) for r in reports]]
        lines.append("Use the reports for realism. Paraphrase them; do not name the source sites in the lesson.")
        if any(r.get("confidence") == "low" for r in reports):
            lines.append(
                "A report marked 'title only' is one aggregator's title, paraphrased, with no candidate account behind it: "
                "use it for breadth; anchor the scenario in the reports above it."
            )
        lines.append("Put the Source links of the reports you used in grounded_in in challenge.yaml.")
    lines += [
        "",
        "## Steps",
        f"1. Pick a short slug and run: {CLI} question new {track_id} <slug> --type {kind or '<type>'}",
        f"   It creates the files to fill in, in {_rel(settings.staging_dir)}/<slug>/.",
        f"2. Write every file. Then run: {CLI} question add {_rel(settings.staging_dir)}/<slug> --module {track_id}",
        "   It checks that the reference solution passes every test and the starter fails at least one, then files",
        "   the question as the module's next one. If it prints problems, fix them and run the same command again.",
        f"3. Run {CLI} question check <key> twice more to catch flaky timing.",
    ]
    return "\n".join(lines)


def build_notes(problem: dict, limit: int = 6) -> str:
    lines = [
        "Ground the challenge in these real interview reports. Start with the core version. "
        "If the track already has challenges, write the next step up by taking on the next follow-up.",
    ]
    lines += [report_line(r) for r in problem.get("reports", [])[:limit]]
    return "\n".join(lines)


# The types that practice what the learner's AI now does for them (docs/PEDAGOGY.md).
THESIS_TYPES = ("fix", "review", "tests")


def names_thesis_skill(ai_handles: list[str]) -> bool:
    """True when the profile says the learner's AI writes their tests, reviews code or reads code for them."""
    text = " ".join(ai_handles).lower()
    # ponytail: substring match; "test" also covers testing, "review" covers PR review
    return any(w in text for w in ("test", "review", "reading code", "read code", "code reading"))


# The module recipe from docs/PEDAGOGY.md: read before write, then build, mix, break and fix.
RECIPE = [
    "predict: the learner reads working code and predicts what it does on a scripted input.",
    "build: the core version, from a starter. Problem first (lesson: after-run).",
    "build: the next step up (concurrency, scale or failure). Mix in an idea from an earlier module without naming it.",
    "fix, review or tests: a realistic seeded bug to fix, AI-written code with 2 or 3 defects to review, or working code to write the tests for. Prefer tests when the profile says the learner's AI writes their tests.",
    "build or design: an adversary arrives (retry storm, clock skew, a crash between write and ack). In a design question the learner picks the guarantee first. Hidden tests attack it.",
]


def _recipe_line(position: int) -> str:
    if position <= len(RECIPE):
        return f"This is question {position} of the module. Suggested: {RECIPE[position - 1]} Pick another type only for a reason from the learner's progress."
    return (
        f"This is question {position}: the core recipe is done. Write a variant of an earlier question on a new surface "
        "(set variant_of), or apply the idea in another domain or in the learner's own stack."
    )

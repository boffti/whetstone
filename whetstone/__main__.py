"""Command line. Any AI coding agent (or a person) drives Whetstone with these commands;
the agent does the thinking on the learner's own subscription. See AGENTS.md.

Content model: a learning path is an ordered list of modules toward a goal; a module
is a topic made of ordered questions; a question is one exercise (lesson, code, tests).
In the files, a module is a folder under content/tracks/ and a question is a folder in it.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .catalog import CLI, _rel
from .config import load_settings
from .content import ContentError, LearningPath, find_challenge, load_all_paths, load_tracks, save_path, slugify

TEMPLATE = {
    "challenge.yaml": (
        "title: {title}  # name the scenario, not the technique\n"
        "type: build  # build | predict | fix | review\n"
        "lesson: after-run  # after-run = problem first; first = lesson first (use for predict)\n"
        "difficulty: medium\nminutes: 20\ntags: []\nrequires: []\n"
        "support: []  # predict and review: the code to read, e.g. [subject.py]\n"
        "# variant_of: module/NN-slug  # set when this re-tests an earlier question on a new surface\n"
        "summary: One sentence about what the learner does.\n"
    ),
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
}


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
        text = make_brief(settings, problem, difficulty=args.difficulty, notes=args.notes or "")
    else:
        topic = args.topic or (f"{track.title}: {track.description}" if track else None)
        if not topic:
            return fail(f'{module} is not a module or a catalog problem yet. Pass --topic "..." to say what it teaches.', 2)
        text = make_brief(settings, topic=topic, track=module, difficulty=args.difficulty, notes=args.notes or "")
    print(text)
    return 0


def cmd_question_new(args) -> int:
    settings = load_settings()
    slug = slugify(args.slug)
    stage = settings.staging_dir / slug
    if stage.exists():
        return fail(f"{stage} already exists. Fill it in, or pick another slug.")
    title = args.title or slug.replace("-", " ").capitalize()
    for rel, body in TEMPLATE.items():
        dest = stage / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(body.format(title=title), encoding="utf-8")
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
            print(f"Practise: {link['track']}/{link['challenge']} ({link['solved']} of {link['total']} solved)")
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
    if args.json:
        print(json.dumps({"week": week, "active_days": store.active_days(), "questions": rows}, indent=2))
        return 0
    done = sum(r["status"] == "solved" for r in rows)
    print(
        f"This week: {week['this_week']} of {week['target']} practice days. Weekly streak: {week['streak']}. Solved {done} of {len(rows)} questions.\n"
    )
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
    starter = c.read("starter.py")
    if code == starter:
        code = None
    print(f"# {c.key}: {c.title}")
    print(f"Last run: {last['mode']} {last['status']} {last['passed']}/{last['total']} at {last['created_at']}" if last else "No runs yet.")
    print(
        f"Hints opened: {sum(w.startswith('hint') for w in opened)} of {len(c.hints())}. Solution viewed: {'yes' if 'solution' in opened else 'no'}."
    )
    print(f"\n## The learner's solution.py{' (untouched starter)' if code is None else ''}\n")
    print(code if code is not None else starter)
    return 0


def cmd_test(args) -> int:
    from .runner import run_tests

    settings = load_settings()
    store, _ = _state(settings)
    c = _question_or_none(settings, args.key)
    if c is None:
        return 1
    code = store.get_draft(c.key)
    # ponytail: not recorded as a run, so the learner's progress only reflects their own runs
    report = run_tests(c, code if code is not None else c.read("starter.py"), "submit" if args.all else "run", settings)
    print(f"{report.status.upper()}: {report.summary}")
    for t in report.tests:
        if t.outcome != "passed":
            print(f"- {t.label}{' (hidden)' if t.hidden else ''}: {t.outcome}. {t.message}")
    if report.status in ("error", "timeout"):
        print(report.output[-3000:])
    return 0 if report.status == "passed" else 1


# ---------- Parser ----------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="whetstone", description="Self-hosted practice dojo. AI agents: read AGENTS.md.")
    sub = parser.add_subparsers(dest="cmd")

    def cmd(group, name, func, help_text):
        p = group.add_parser(name, help=help_text, description=help_text)
        p.set_defaults(func=func)
        return p

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
    p.add_argument("--topic", help="what the question teaches, for a module that is not in the catalog")
    p.add_argument("--difficulty", default="medium", choices=["easy", "medium", "hard"])
    p.add_argument("--notes", help="what the learner asked for")
    p = cmd(questions, "new", cmd_question_new, "scaffold a question's files in my/.staging/<slug>/")
    p.add_argument("module")
    p.add_argument("slug")
    p.add_argument("--title")
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

"""HTTP API and static UI."""

from __future__ import annotations

import os
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import dashboard as dash
from .catalog import FRAMING, build_notes, catalog_links, find_problem, framing_ask, load_catalog, path_rows
from .config import Settings, load_settings
from .content import ContentError, find_challenge, load_all_paths, load_profile, load_tracks, render_md, save_profile_header, slugify
from .generator import GenerationError, ensure_track, generate_challenge
from .runner import check_whiteboard, drawing_mermaid, run_tests
from .store import PAIR_MODES, REQUEST_KINDS, Store, progress_rows

STATIC = Path(__file__).parent / "static"
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
RECENT = timedelta(minutes=10)  # a request that finished this recently is still shown as news
STALE = timedelta(minutes=15)  # a claim untouched for this long is an agent that stopped


def allowed_hosts() -> set[str]:
    """Local names, plus any you add on purpose with WHETSTONE_ALLOWED_HOSTS (comma-separated)."""
    extra = {h.strip().lower() for h in os.environ.get("WHETSTONE_ALLOWED_HOSTS", "").split(",") if h.strip()}
    return LOCAL_HOSTS | extra


def _host_port(url: str) -> tuple[str, int] | None:
    """(hostname, port) of a URL or a bare authority, with the scheme's default port filled in."""
    try:
        parts = urlsplit(url)
        return (parts.hostname or ""), (parts.port or (443 if parts.scheme == "https" else 80))
    except ValueError:  # a port that is not a number
        return None


def is_local_request(host_header: str, origin: str | None, allowed: set[str]) -> bool:
    """Whetstone runs the code it is sent, so it only answers this machine. A wrong Host header
    means DNS rebinding (an outside site resolving its name to 127.0.0.1); an Origin that is not
    exactly this host and port means another page is sending the request, even one on another
    local port."""
    host = _host_port(f"//{host_header}")
    if host is None or host[0] not in allowed:
        return False
    return origin is None or _host_port(origin) == host


class CodeBody(BaseModel):
    code: str = Field(max_length=200_000)


class RunBody(CodeBody):
    mode: str = Field(default="run", pattern="^(run|submit)$")
    # A guess made before the run. run: {"tests": {"test_name": true}}, true = will pass.
    # submit: {"all_pass": true, "confidence": 1..5}.
    prediction: dict | None = None


class DrawingBody(BaseModel):
    elements: list[dict] = Field(max_length=5000)


class RenderBody(BaseModel):
    text: str = Field(max_length=200_000)


class ExplainBody(BaseModel):
    test: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=2000)


class RatingBody(BaseModel):
    rating: str = Field(pattern="^(too-easy|right|too-hard|artificial)$")


class InterestsBody(BaseModel):
    focus: list[str] | None = Field(default=None, max_length=20)
    targets: list[str] | None = Field(default=None, max_length=20)
    paths: list[str] | None = Field(default=None, max_length=20)


class RequestBody(BaseModel):
    kind: str = Field(pattern="^(" + "|".join(REQUEST_KINDS) + ")$")
    target: str = Field(default="", max_length=200)
    framing: str | None = Field(default=None, pattern=FRAMING.pattern)  # work, company:<name> or domain:<name>


class PairBody(BaseModel):
    mode: str = Field(pattern="^(" + "|".join(PAIR_MODES) + ")$")


class NoteDismiss(BaseModel):
    dismissed: bool = True


class SolutionBody(BaseModel):
    give_up: bool = False


NO_GENERATOR = "Ask your AI agent in this folder to build it (see AGENTS.md), or set ANTHROPIC_API_KEY in .env and restart to build here."


def require_json(request: Request) -> None:
    """Block cross-site form posts: a JSON content type forces a CORS preflight, which
    this app never approves. Endpoints that start work on the machine must call this."""
    if not request.headers.get("content-type", "").startswith("application/json"):
        raise HTTPException(415, "Send Content-Type: application/json")


def _redis_ok(url: str) -> bool:
    try:
        import redis

        return bool(redis.Redis.from_url(url, socket_connect_timeout=0.5).ping())
    except Exception:
        return False


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    store = Store(settings.db_path)
    app = FastAPI(title="Whetstone")
    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    hosts = allowed_hosts()

    @app.middleware("http")
    async def local_only(request: Request, call_next):
        if not is_local_request(request.headers.get("host", ""), request.headers.get("origin"), hosts):
            return JSONResponse({"detail": "Whetstone only answers requests from this machine."}, status_code=403)
        return await call_next(request)

    @app.middleware("http")
    async def revalidate_ui(request: Request, call_next):
        # The UI changes with every upgrade: make browsers check (cheaply, by ETag) instead of
        # serving a stale cached copy of the page, CSS or JS.
        response = await call_next(request)
        if request.url.path == "/" or request.url.path.startswith("/static/"):
            response.headers["Cache-Control"] = "no-cache"
        return response

    def get_challenge(track: str, cid: str):
        try:
            return find_challenge(settings.tracks_dir, track, cid)
        except ContentError as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.get("/")
    def index():
        return FileResponse(STATIC / "index.html")

    @app.get("/api/config")
    def config():
        return {
            "generator_enabled": settings.generator_enabled,
            "model": settings.model,
            "redis_ok": _redis_ok(settings.redis_url),
            "redis_url": settings.redis_url,
        }

    @app.get("/api/tracks")
    def tracks():
        all_tracks = load_tracks(settings.tracks_dir)
        rows = {r["key"]: r for r in progress_rows(store, all_tracks)}
        out = []
        for t in all_tracks:
            out.append(
                {
                    "id": t.id,
                    "title": t.title,
                    "description": t.description,
                    "challenges": [
                        {
                            "id": c.dir_name,
                            "number": c.number,
                            "title": c.title,
                            "type": c.kind,
                            "difficulty": c.difficulty,
                            "minutes": c.minutes,
                            "tags": c.tags,
                            "requires": c.requires,
                            "status": _status(rows[c.key]),
                        }
                        for c in t.challenges
                    ],
                }
            )
        return out

    @app.get("/api/dashboard")
    def dashboard():
        """The Practice home: who the learner is, how sharp each skill is, the numbers,
        the game layer, and each question's progress for the next steps."""
        today = date.today()
        all_tracks = load_tracks(settings.tracks_dir)
        rows = progress_rows(store, all_tracks)
        facts = store.facts()
        week = store.week()
        days = store.active_days(last=182)
        profile = load_profile(settings.user_dir / "profile.md")
        catalog = load_catalog(settings)
        titles = {t.id: t.title for t in all_tracks}
        recent = [
            {**r, "title": next((q["title"] for q in rows if q["key"] == r["challenge"]), r["challenge"])} for r in store.recent_runs()
        ]
        return {
            "has_profile": (settings.user_dir / "profile.md").exists(),
            "profile": profile,
            "questions": rows,
            "week": week,
            "active_days": days,
            "edges": dash.edges(rows, facts, titles, profile, catalog, today),
            "numbers": dash.numbers(rows, facts, today) | dash.predictions(store, today),
            "milestones": dash.milestones(rows, facts, week),
            "records": dash.records(rows, facts, store.active_days(last=3650), week["target"]),
            "targets": dash.targets(profile, catalog, {t.id for t in all_tracks if t.challenges}),
            "recent": recent,
        }

    @app.get("/api/stats")
    def stats():
        all_keys = [c.key for t in load_tracks(settings.tracks_dir) for c in t.challenges]
        solved = store.solved_keys()
        return {
            "week": store.week(),
            "solved": len([k for k in all_keys if k in solved]),
            "total": len(all_keys),
            "active_days": store.active_days(),
        }

    @app.get("/api/challenges/{track}/{cid}")
    def challenge(track: str, cid: str):
        c = get_challenge(track, cid)
        draft = store.get_draft(c.key)
        store.record_event(c.key, "opened", {"title": c.title, "type": c.kind})
        solved = c.key in store.solved_keys()
        reveal = solved or "solution" in store.reveals(c.key)
        return {
            "track": track,
            "id": cid,
            "title": c.title,
            "difficulty": c.difficulty,
            "type": c.kind,
            "lesson_mode": c.lesson,
            "minutes": c.minutes,
            "tags": c.tags,
            "requires": c.requires,
            "lesson_html": lesson_html(c, store),
            "problem_html": render_md(c.read("problem.md")),
            "hint_count": len(c.hints()),
            "visible_tests": visible_test_names(c),
            "hints": [render_md(h) for h in c.hints()[: _hints_opened(store, c.key)]],
            "hint_ready": store.hint_ready(c.key),
            "solution_open": reveal,
            "file": c.editor_file,
            "language": "markdown" if c.is_whiteboard else "python",
            "starter": c.read(c.starter_file),
            "code": draft if draft is not None else c.read(c.starter_file),
            "review": review_view(store.latest_review(c.key), reveal) if c.is_whiteboard else None,
            "files": [{"name": n, "content": c.read(n)} for n in c.support]
            + [{"name": f"tests/{f.name}", "content": f.read_text(encoding="utf-8")} for f in c.visible_test_files()],
            "solved": solved,
            "runs": store.run_count(c.key),
            "rating": store.rating(c.key),
            "framing": c.framing,
        }

    @app.get("/api/challenges/{track}/{cid}/review")
    def review(track: str, cid: str):
        c = get_challenge(track, cid)
        reveal = c.key in store.solved_keys() or "solution" in store.reveals(c.key)
        return {"review": review_view(store.latest_review(c.key), reveal), "solved": c.key in store.solved_keys()}

    @app.get("/api/challenges/{track}/{cid}/hints/{index}")
    def hint(track: str, cid: str, index: int):
        c = get_challenge(track, cid)
        hints, opened = c.hints(), _hints_opened(store, c.key)
        if not 0 <= index < len(hints) or index > opened:
            raise HTTPException(404, "Open the hints in order.")
        if index == opened:
            if not store.hint_ready(c.key):
                raise HTTPException(409, "Run the tests once more before the next hint.")
            store.record_reveal(c.key, f"hint-{index}")
            store.record_event(c.key, "hint", {"rung": index + 1, "of": len(hints)})
        return {"index": index, "html": render_md(hints[index])}

    @app.post("/api/challenges/{track}/{cid}/solution")
    def solution(track: str, cid: str, body: SolutionBody, request: Request):
        require_json(request)
        c = get_challenge(track, cid)
        if not (body.give_up or c.key in store.solved_keys() or "solution" in store.reveals(c.key)):
            raise HTTPException(409, "The solution opens after you solve the question, or when you give up.")
        if "solution" not in store.reveals(c.key):
            store.record_event(c.key, "solution", {"gave_up": body.give_up})
        store.record_reveal(c.key, "solution")
        code = c.read(c.solution_file)
        if c.is_whiteboard:
            return {"code": code, "html": render_md(code)}
        return {"code": code, "lesson_html": lesson_html(c, store)} if c.kind == "predict" else {"code": code}

    @app.get("/api/challenges/{track}/{cid}/notes")
    def notes(track: str, cid: str, after: int = 0):
        c = get_challenge(track, cid)
        return store.notes(c.key, after)

    @app.post("/api/notes/{note_id}")
    def dismiss_note(note_id: int, body: NoteDismiss, request: Request):
        require_json(request)
        if body.dismissed:
            store.dismiss_note(note_id)
        return {"ok": True}

    # ---------- Interests: the learner edits their focus, companies and paths ----------
    @app.get("/api/profile")
    def profile():
        return load_profile(settings.user_dir / "profile.md")

    @app.put("/api/profile")
    def save_interests(body: InterestsBody, request: Request):
        require_json(request)
        updates: dict = {}
        if body.focus is not None:
            known = {slugify(p["id"]) for p in load_catalog(settings)} | {t.id for t in load_tracks(settings.tracks_dir)}
            focus = list(dict.fromkeys(slugify(f) for f in body.focus))
            unknown = [f for f in focus if f not in known]
            if unknown:
                raise HTTPException(400, f"Not a module: {', '.join(unknown)}")
            updates["focus"] = focus
        if body.targets is not None:
            updates["targets"] = list(dict.fromkeys(t.strip()[:40] for t in body.targets if t.strip()))
        if body.paths is not None:
            known_paths = {lp.id for lp in load_all_paths(settings.shared_paths_dir, settings.paths_dir)}
            unknown = [x for x in body.paths if x not in known_paths]
            if unknown:
                raise HTTPException(400, f"Not a learning path: {', '.join(unknown)}")
            updates["paths"] = list(dict.fromkeys(body.paths))
        saved = save_profile_header(settings.user_dir / "profile.md", updates)
        store.record_event(None, "interests", {k: saved.get(k, []) for k in updates})
        return saved

    # ---------- Agent inbox ----------
    def check_target(kind: str, target: str) -> str:
        """The request's target, normalised, or a 400 when it names nothing real."""
        want = REQUEST_KINDS[kind]
        if want == "module":
            module = slugify(target)
            known = {slugify(p["id"]) for p in load_catalog(settings)} | {t.id for t in load_tracks(settings.tracks_dir)}
            if module not in known:
                raise HTTPException(400, f"{target} is not a module.")
            return module
        if want == "question":
            track, _, cid = target.partition("/")
            get_challenge(track, cid)
            return target
        return ""

    @app.post("/api/requests")
    def add_request(body: RequestBody, request: Request):
        require_json(request)
        target = check_target(body.kind, body.target)
        framing = body.framing if body.kind in ("build", "variant", "design") else None
        r = store.add_request(body.kind, target, framing)
        store.record_event(
            None, "requested", {"id": r["id"], "kind": r["kind"], "target": r["target"], "framing": r["framing"], "ask": request_ask(r)}
        )
        return r

    @app.get("/api/requests")
    def list_requests():
        now = datetime.now()  # the server's clock, like the rows' stamps; the browser's may be in another zone
        rows = []
        for r in store.requests():
            age = now - datetime.fromisoformat(r["updated_at"])
            rows.append({**r, "recent": age < RECENT, "stale": age > STALE})
        return {"requests": rows, "agent": agent_status(store)}

    @app.post("/api/requests/{request_id}/cancel")
    def cancel_request(request_id: int, request: Request):
        require_json(request)
        r = store.update_request(request_id, "cancelled", only_from=("queued", "claimed"))
        if not r:
            raise HTTPException(404, "No open request with that id.")
        return r

    @app.get("/api/pair")
    def pair():
        return {"mode": store.setting("pair_mode", "quiet")}

    @app.put("/api/pair")
    def set_pair(body: PairBody, request: Request):
        require_json(request)
        store.set_setting("pair_mode", body.mode)
        store.record_event(None, "mode", {"mode": body.mode})
        return {"mode": body.mode}

    @app.put("/api/challenges/{track}/{cid}/draft")
    def save_draft(track: str, cid: str, body: CodeBody):
        c = get_challenge(track, cid)
        store.save_draft(c.key, body.code)
        store.record_event(c.key, "edited", {"lines": body.code.count("\n") + 1})
        return {"saved": True}

    @app.post("/api/challenges/{track}/{cid}/reset")
    def reset(track: str, cid: str):
        c = get_challenge(track, cid)
        store.delete_draft(c.key)
        store.record_event(c.key, "reset")
        return {"code": c.read(c.starter_file)}

    @app.post("/api/challenges/{track}/{cid}/run")
    def run(track: str, cid: str, body: RunBody):
        c = get_challenge(track, cid)
        store.save_draft(c.key, body.code)
        # A design is solved only by the agent's rubric review (`whetstone grade`), never by the section check.
        mode = "run" if c.is_whiteboard else body.mode
        report = check_whiteboard(body.code, store.get_drawing(c.key)) if c.is_whiteboard else run_tests(c, body.code, mode, settings)
        first_solve = store.record_run(c.key, mode, report.status, report.passed, report.total, report.duration, body.code)
        solve = store.solve(c.key, f"hint-{len(c.hints()) - 1}") if first_solve else None
        prediction = score_prediction(body.prediction, mode, report) if body.prediction and not c.is_whiteboard else None
        if prediction and prediction["total"]:
            store.record_prediction(c.key, mode, prediction["correct"], prediction["total"], prediction.get("confidence"))
        failing = [t.name for t in report.tests if t.outcome in ("failed", "error")][:5]
        store.record_event(
            c.key,
            "ran",
            {
                "mode": mode,
                "status": report.status,
                "passed": report.passed,
                "total": report.total,
                "failing": failing,
                "solved": bool(first_solve),
                "predicted": {k: prediction[k] for k in ("correct", "total")} if prediction else None,
            },
        )
        out = {**report.to_dict(), "first_solve": first_solve, "solve": solve[1] if solve else None, "prediction": prediction}
        if c.kind == "predict" and mode == "submit":
            out["lesson_html"] = lesson_html(c, store)  # the first Submit opens the misconceptions
        return out

    @app.post("/api/challenges/{track}/{cid}/explanation")
    def explain(track: str, cid: str, body: ExplainBody, request: Request):
        require_json(request)
        c = get_challenge(track, cid)
        store.add_explanation(c.key, body.test, body.text.strip())
        store.record_event(c.key, "explained", {"test": body.test, "text": body.text.strip()[:300]})
        return {"saved": True}

    @app.post("/api/challenges/{track}/{cid}/rating")
    def rate(track: str, cid: str, body: RatingBody, request: Request):
        """How the question felt, one tap after Submit. The curator and the author read it."""
        require_json(request)
        c = get_challenge(track, cid)
        store.record_rating(c.key, body.rating)
        store.record_event(c.key, "rated", {"rating": body.rating})
        return {"saved": True}

    @app.get("/api/challenges/{track}/{cid}/drawing")
    def drawing(track: str, cid: str):
        """The whiteboard drawing, and the Mermaid the learner's agent reads from it."""
        c = get_challenge(track, cid)
        elements = store.get_drawing(c.key)
        mermaid, notes = drawing_mermaid(elements)
        return {"elements": elements, "mermaid": mermaid, "notes": notes}

    @app.put("/api/challenges/{track}/{cid}/drawing")
    def save_drawing(track: str, cid: str, body: DrawingBody, request: Request):
        require_json(request)
        c = get_challenge(track, cid)
        if not c.is_whiteboard:
            raise HTTPException(400, "Only system design questions have a whiteboard.")
        # Images would bloat the drawing and the agent cannot read them; the app hides the tool.
        elements = [e for e in body.elements if e.get("type") != "image"]
        store.save_drawing(c.key, elements)
        shapes = sum(1 for e in elements if not e.get("isDeleted") and e.get("type") in ("rectangle", "ellipse", "diamond"))
        store.record_event(c.key, "edited", {"shapes": shapes})
        return {"saved": True}

    @app.post("/api/render")
    def render(body: RenderBody, request: Request):
        """The learner's Markdown as HTML, for the design scratchpad's preview."""
        require_json(request)
        return {"html": render_md(body.text)}

    @app.get("/api/design")
    def design():
        """System design prompts: catalog problems asked in system design rounds, most asked first
        on the page, with the learner's whiteboard questions for each."""
        tracks = load_tracks(settings.tracks_dir)
        rows = {r["key"]: r for r in progress_rows(store, tracks)}
        boards: dict[str, list[dict]] = {}
        for t in tracks:
            for c in t.challenges:
                if c.is_whiteboard:
                    last = store.latest_review(c.key)
                    boards.setdefault(t.id, []).append(
                        {
                            "key": c.key,
                            "title": c.title,
                            "status": _status(rows[c.key]),
                            "covered": sum(p["verdict"] == "covered" for p in last["points"]) if last else None,
                            "points": len(last["points"]) if last else None,
                        }
                    )
        prompts = []
        for p in load_catalog(settings):
            asked = [r for r in p.get("reports", []) if r.get("round") == "system-design"]
            if not asked and p.get("format") != "design":
                continue
            module = slugify(p["id"])
            counts: dict[str, int] = {}
            for r in asked:
                counts[r["company"]] = counts.get(r["company"], 0) + 1
            prompts.append(
                {
                    "id": module,
                    "title": p["title"],
                    "summary": p.get("summary", ""),
                    "reports": len(asked),
                    "companies": sorted(counts, key=lambda co: (-counts[co], co)),
                    "asked": [r["question"] for r in asked[:3]],
                    "questions": boards.pop(module, []),
                }
            )
        titles = {t.id: t.title for t in tracks}
        prompts += [
            {"id": m, "title": titles.get(m, m), "summary": "", "reports": 0, "companies": [], "asked": [], "questions": qs}
            for m, qs in boards.items()
        ]
        return {"prompts": prompts}

    @app.get("/api/catalog")
    def catalog():
        tracks = {t.id: t for t in load_tracks(settings.tracks_dir)}
        solved = store.solved_keys()
        return {"problems": [{**p, "links": catalog_links(p, tracks, solved)} for p in load_catalog(settings)]}

    @app.get("/api/paths")
    def paths():
        tracks = {t.id: t for t in load_tracks(settings.tracks_dir)}
        solved = store.solved_keys()
        return [
            {
                "id": lp.id,
                "title": lp.title,
                "goal": lp.goal,
                "domain": lp.domain,
                "companies": lp.companies,
                "mine": lp.mine,
                "modules": path_rows(settings, lp, tracks, solved),
            }
            for lp in load_all_paths(settings.shared_paths_dir, settings.paths_dir)
        ]

    @app.post("/api/catalog/{pid}/build")
    def build(pid: str, request: Request):
        require_json(request)
        problem = find_problem(settings, pid)
        if problem is None:
            raise HTTPException(404, f"No catalog problem {pid}")
        if not settings.generator_enabled:
            raise HTTPException(400, NO_GENERATOR)
        track_id = slugify(pid)
        ensure_track(settings, track_id, problem["title"], problem.get("summary"))
        lines: list[str] = []
        topic = f"{problem['title']}: {problem.get('summary', '')}"
        try:
            key = generate_challenge(settings, topic, track_id, problem["title"], "medium", build_notes(problem), log=lines.append)
        except GenerationError as exc:
            return {"ok": False, "error": str(exc), "log": lines}
        track, cid = key.split("/", 1)
        return {"ok": True, "track": track, "id": cid, "log": lines}

    return app


def _hints_opened(store: Store, key: str) -> int:
    return sum(w.startswith("hint-") for w in store.reveals(key))


def _status(row: dict) -> str:
    """new, attempted, assisted (solved with the last hint or the solution), solved, or mastered."""
    if row["mastered"]:
        return "mastered"
    if row["solve"] == "assisted":
        return "assisted"
    return row["status"]


def lesson_html(c, store: Store) -> str:
    """The lesson. A predict lesson's misconceptions name what the hidden predictions test, so
    that section waits for the first Submit or a reveal; the rest reads before the attempt."""
    text = c.read("lesson.md")
    opened = c.key in store.solved_keys() or "solution" in store.reveals(c.key) or "first_submit" in store.facts().get(c.key, {})
    if c.kind == "predict" and not opened:
        text = re.sub(
            r"(^##[ \t]+Misconceptions[ \t]*\n).*?(?=^##[ \t]|\Z)", r"\1\n*Opens after your first Submit.*\n\n", text, flags=re.M | re.S
        )
    return render_md(text)


def visible_test_names(c) -> list[dict]:
    """The visible tests, in file order, for the learner to predict before their first run."""
    names = [m for f in c.visible_test_files() for m in re.findall(r"^\s*def (test_\w+)", f.read_text(encoding="utf-8"), flags=re.M)]
    return [{"name": n, "label": n[5:].replace("_", " ")} for n in dict.fromkeys(names)]


def score_prediction(guess: dict, mode: str, report) -> dict:
    """Compare a guess made before the run with what happened."""
    if mode == "submit":
        will_pass = bool(guess.get("all_pass"))
        confidence = guess.get("confidence")
        confidence = int(confidence) if isinstance(confidence, (int, float)) and 1 <= confidence <= 5 else None
        right = will_pass == (report.status == "passed")
        return {"correct": int(right), "total": 1, "all_pass": will_pass, "confidence": confidence, "details": []}
    actual = {t.name: t.outcome == "passed" for t in report.tests}
    guesses = guess.get("tests") or {}
    details = [
        {"test": name, "label": name[5:].replace("_", " "), "predicted": bool(will), "actual": actual[name]}
        for name, will in list(guesses.items())[:100]
        if name in actual
    ]
    return {"correct": sum(d["predicted"] == d["actual"] for d in details), "total": len(details), "details": details}


AGENT_FRESH_SECONDS = 30


def agent_status(store: Store) -> dict:
    """Whether the learner's agent is watching: `whetstone watch` checks in every few seconds."""
    from datetime import datetime

    seen = store.agent_seen()
    fresh = bool(seen) and (datetime.now() - datetime.fromisoformat(seen)).total_seconds() < AGENT_FRESH_SECONDS
    return {"connected": fresh, "seen_at": seen}


def review_view(review: dict | None, reveal: bool) -> dict | None:
    """The agent's latest grade of a design, for the app. Like hidden tests, a point the design
    misses shows only the agent's question until the learner solves it or gives up."""
    if not review:
        return None
    points = [p | {"point": p["point"] if reveal or p["verdict"] == "covered" else ""} for p in review["points"]]
    return {
        "summary": review["summary"],
        "created_at": review["created_at"],
        "points": points,
        "covered": sum(p["verdict"] == "covered" for p in points),
        "passed": all(p["verdict"] == "covered" for p in points if p["must"]),
    }


def request_ask(r: dict) -> str:
    """The plain-words job, as the learner would say it to their agent."""
    return framed(r) + framing_ask(r.get("framing")) if r["kind"] in ("build", "variant", "design") else framed(r)


def framed(r: dict) -> str:
    return {
        "build": f"Build the next Whetstone question for the {r['target']} module.",
        "variant": f"Build a Whetstone variant of {r['target']} for review.",
        "fill-path": f"Fill in my {r['target']} Whetstone path.",  # older requests; the app now queues one build per module
        "review": f"Review my solution to {r['target']}.",
        "design": f"Build a Whetstone system design question (whiteboard) for the {r['target']} module.",
        "grade": f"Grade my system design for {r['target']} against its rubric.",
        "profile": "Set up or refresh my Whetstone profile.",
    }[r["kind"]]

"""HTTP API and static UI."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .catalog import build_notes, catalog_links, find_problem, load_catalog, path_rows
from .config import Settings, load_settings
from .content import ContentError, find_challenge, load_all_paths, load_tracks, render_md, slugify
from .generator import GenerationError, ensure_track, generate_challenge
from .runner import run_tests
from .store import Store

STATIC = Path(__file__).parent / "static"


class CodeBody(BaseModel):
    code: str = Field(max_length=200_000)


class RunBody(CodeBody):
    mode: str = Field(default="run", pattern="^(run|submit)$")


class GenerateBody(BaseModel):
    topic: str = Field(min_length=3, max_length=500)
    track: str = Field(min_length=1, max_length=80)
    difficulty: str = Field(default="medium", pattern="^(easy|medium|hard)$")
    notes: str = Field(default="", max_length=2000)


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
        return {"generator_enabled": settings.generator_enabled, "model": settings.model, "redis_ok": _redis_ok(settings.redis_url), "redis_url": settings.redis_url}

    @app.get("/api/tracks")
    def tracks():
        solved = store.solved_keys()
        attempted = store.attempted_keys()
        out = []
        for t in load_tracks(settings.tracks_dir):
            out.append({
                "id": t.id,
                "title": t.title,
                "description": t.description,
                "challenges": [
                    {
                        "id": c.dir_name,
                        "number": c.number,
                        "title": c.title,
                        "difficulty": c.difficulty,
                        "minutes": c.minutes,
                        "tags": c.tags,
                        "requires": c.requires,
                        "status": "solved" if c.key in solved else ("attempted" if c.key in attempted else "new"),
                    }
                    for c in t.challenges
                ],
            })
        return out

    @app.get("/api/stats")
    def stats():
        all_keys = [c.key for t in load_tracks(settings.tracks_dir) for c in t.challenges]
        solved = store.solved_keys()
        return {"streak": store.streak(), "solved": len([k for k in all_keys if k in solved]), "total": len(all_keys), "active_days": store.active_days()}

    @app.get("/api/challenges/{track}/{cid}")
    def challenge(track: str, cid: str):
        c = get_challenge(track, cid)
        draft = store.get_draft(c.key)
        return {
            "track": track,
            "id": cid,
            "title": c.title,
            "difficulty": c.difficulty,
            "minutes": c.minutes,
            "tags": c.tags,
            "requires": c.requires,
            "lesson_html": render_md(c.read("lesson.md")),
            "problem_html": render_md(c.read("problem.md")),
            "hint_count": len(c.hints()),
            "starter": c.read("starter.py"),
            "code": draft if draft is not None else c.read("starter.py"),
            "files": [{"name": n, "content": c.read(n)} for n in c.support]
            + [{"name": f"tests/{f.name}", "content": f.read_text(encoding="utf-8")} for f in c.visible_test_files()],
            "solved": c.key in store.solved_keys(),
            "runs": store.run_count(c.key),
        }

    @app.get("/api/challenges/{track}/{cid}/hints/{index}")
    def hint(track: str, cid: str, index: int):
        c = get_challenge(track, cid)
        hints = c.hints()
        if not 0 <= index < len(hints):
            raise HTTPException(404, "No such hint")
        store.record_reveal(c.key, f"hint-{index}")
        return {"index": index, "html": render_md(hints[index])}

    @app.get("/api/challenges/{track}/{cid}/solution")
    def solution(track: str, cid: str):
        c = get_challenge(track, cid)
        store.record_reveal(c.key, "solution")
        return {"code": c.read("solution.py")}

    @app.put("/api/challenges/{track}/{cid}/draft")
    def save_draft(track: str, cid: str, body: CodeBody):
        c = get_challenge(track, cid)
        store.save_draft(c.key, body.code)
        return {"saved": True}

    @app.post("/api/challenges/{track}/{cid}/reset")
    def reset(track: str, cid: str):
        c = get_challenge(track, cid)
        store.delete_draft(c.key)
        return {"code": c.read("starter.py")}

    @app.post("/api/challenges/{track}/{cid}/run")
    def run(track: str, cid: str, body: RunBody):
        c = get_challenge(track, cid)
        store.save_draft(c.key, body.code)
        report = run_tests(c, body.code, body.mode, settings)
        first_solve = store.record_run(c.key, body.mode, report.status, report.passed, report.total, report.duration, body.code)
        return {**report.to_dict(), "first_solve": first_solve}

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
            {"id": lp.id, "title": lp.title, "goal": lp.goal, "domain": lp.domain, "companies": lp.companies,
             "mine": lp.mine, "modules": path_rows(settings, lp, tracks, solved)}
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

    @app.post("/api/generate")
    def generate(body: GenerateBody):
        if not settings.generator_enabled:
            raise HTTPException(400, NO_GENERATOR)
        lines: list[str] = []
        known = {t.id: t.title for t in load_tracks(settings.tracks_dir)}
        track_id = body.track if body.track in known else slugify(body.track)
        try:
            key = generate_challenge(settings, body.topic, track_id, known.get(track_id, body.track), body.difficulty, body.notes, log=lines.append)
        except GenerationError as exc:
            return {"ok": False, "error": str(exc), "log": lines}
        track, cid = key.split("/", 1)
        return {"ok": True, "track": track, "id": cid, "log": lines}

    return app

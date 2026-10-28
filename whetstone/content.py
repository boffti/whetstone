"""Load tracks and challenges from the content folder."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import markdown
import yaml

REQUIRED_FILES = ["challenge.yaml", "lesson.md", "problem.md", "hints.md", "starter.py", "solution.py"]
DIFFICULTIES = ("easy", "medium", "hard")
# What the learner does in a question. See AUTHORING.md and docs/PEDAGOGY.md.
QUESTION_TYPES = ("build", "predict", "fix", "review", "tests", "design", "whiteboard")
# A whiteboard question is a system design interview: the learner writes a design in Markdown,
# with Mermaid diagrams, instead of code. Whetstone checks that every section is filled in; the
# learner's own agent grades it against rubric.yaml (`whetstone grade`).
WHITEBOARD_FILES = ["challenge.yaml", "lesson.md", "problem.md", "hints.md", "starter.md", "solution.md", "rubric.yaml"]
# When the lesson opens: before the problem, or after the learner's first test run (problem first).
LESSON_MODES = ("first", "after-run")


class ContentError(Exception):
    pass


@dataclass
class Challenge:
    track_id: str
    dir_name: str
    path: Path
    title: str
    difficulty: str
    minutes: int
    tags: list[str]
    requires: list[str]
    support: list[str]
    timeout: int | None
    summary: str
    kind: str = "build"
    lesson: str = "first"
    variant_of: str | None = None
    grounded_in: list[str] = field(default_factory=list)  # source links of the interview reports it is based on
    framing: str | None = None  # what it was prepared for: work, company:<name> or domain:<name>

    @property
    def number(self) -> int:
        match = re.match(r"(\d+)", self.dir_name)
        return int(match.group(1)) if match else 0

    @property
    def key(self) -> str:
        return f"{self.track_id}/{self.dir_name}"

    def read(self, name: str) -> str:
        return (self.path / name).read_text(encoding="utf-8")

    @property
    def is_whiteboard(self) -> bool:
        return self.kind == "whiteboard"

    @property
    def starter_file(self) -> str:
        return "starter.md" if self.is_whiteboard else "starter.py"

    @property
    def solution_file(self) -> str:
        return "solution.md" if self.is_whiteboard else "solution.py"

    @property
    def editor_file(self) -> str:
        """The file name the learner sees in the editor."""
        return "design.md" if self.is_whiteboard else "solution.py"

    @property
    def required_files(self) -> list[str]:
        return WHITEBOARD_FILES if self.is_whiteboard else REQUIRED_FILES

    def rubric(self) -> list[dict]:
        """A whiteboard question's rubric points: id, section, point, must, look_for."""
        data = yaml.safe_load(self.read("rubric.yaml")) or {}
        points = data.get("points", []) if isinstance(data, dict) else data
        return [p for p in points or [] if isinstance(p, dict)]

    def test_files(self, include_hidden: bool) -> list[Path]:
        files = sorted((self.path / "tests").glob("*.py"))
        if not include_hidden:
            files = [f for f in files if "hidden" not in f.name]
        return files

    def visible_test_files(self) -> list[Path]:
        return [f for f in self.test_files(include_hidden=False) if f.name != "conftest.py"]

    def hints(self) -> list[str]:
        return split_hints(self.read("hints.md"))

    def mutants(self) -> list[Path]:
        """Wrong versions of the solution, one per misconception. Hidden from the learner."""
        return sorted((self.path / "mutants").glob("*.py"))


@dataclass
class Track:
    id: str
    title: str
    description: str
    path: Path
    order: int = 99
    challenges: list[Challenge] = field(default_factory=list)


@dataclass
class LearningPath:
    """An ordered list of modules (tracks) toward one goal, often a system to build, such as a
    payment processor. Stored as content/paths/<id>.yaml. Modules may be catalog problems that
    are not built yet: placeholders the learner's agent fills in."""

    id: str
    title: str
    goal: str = ""
    modules: list[str] = field(default_factory=list)
    domain: str = ""  # e.g. "Payments & fintech"
    companies: list[str] = field(default_factory=list)  # whose systems it is modelled on
    mine: bool = False  # from the learner's my/paths, not shared


def load_paths(paths_dir: Path) -> list[LearningPath]:
    if not paths_dir.exists():
        return []
    out = []
    for f in sorted(paths_dir.glob("*.yaml")):
        meta = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        out.append(
            LearningPath(
                f.stem,
                str(meta.get("title", f.stem)),
                str(meta.get("goal", "")),
                [str(m) for m in meta.get("modules", [])],
                str(meta.get("domain", "")),
                [str(c) for c in meta.get("companies", [])],
            )
        )
    return out


def load_all_paths(shared_dir: Path, user_dir: Path) -> list[LearningPath]:
    """Shared paths plus the learner's own. A learner's copy with the same id wins, so editing
    a shared path (copy on write into my/paths) never conflicts with `git pull`."""
    merged = {p.id: p for p in load_paths(shared_dir)}
    for p in load_paths(user_dir):
        p.mine = True
        merged[p.id] = p
    return sorted(merged.values(), key=lambda p: p.id)


def save_path(paths_dir: Path, lp: LearningPath) -> Path:
    paths_dir.mkdir(parents=True, exist_ok=True)
    dest = paths_dir / f"{lp.id}.yaml"
    meta = {"title": lp.title, "goal": lp.goal, "domain": lp.domain, "companies": lp.companies, "modules": lp.modules}
    dest.write_text(yaml.safe_dump({k: v for k, v in meta.items() if v or k == "modules"}, sort_keys=False), encoding="utf-8")
    return dest


def split_hints(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"^\s*---\s*$", text, flags=re.M) if part.strip()]


def render_md(text: str) -> str:
    return markdown.markdown(text, extensions=["fenced_code", "tables", "sane_lists"])


def load_challenge(path: Path, track_id: str) -> Challenge:
    meta_file = path / "challenge.yaml"
    if not meta_file.exists():
        raise ContentError(f"{path}: challenge.yaml is missing")
    meta = yaml.safe_load(meta_file.read_text(encoding="utf-8")) or {}
    return Challenge(
        track_id=track_id,
        dir_name=path.name,
        path=path,
        title=str(meta.get("title", path.name)),
        difficulty=str(meta.get("difficulty", "medium")),
        minutes=int(meta.get("minutes", 20)),
        tags=[str(t) for t in meta.get("tags", [])],
        requires=[str(r) for r in meta.get("requires", [])],
        support=[str(s) for s in meta.get("support", [])],
        timeout=meta.get("timeout"),
        summary=str(meta.get("summary", "")),
        kind=str(meta.get("type", "build")),
        lesson=str(meta.get("lesson", "first")),
        variant_of=meta.get("variant_of") or None,
        grounded_in=[str(u) for u in (meta.get("grounded_in") or [])],
        framing=str(meta["framing"]) if meta.get("framing") else None,
    )


def _visible_dirs(path: Path) -> list[Path]:
    return sorted(p for p in path.iterdir() if p.is_dir() and not p.name.startswith((".", "_")))


def load_tracks(tracks_dir: Path) -> list[Track]:
    tracks: list[Track] = []
    if not tracks_dir.exists():
        return tracks
    for track_path in _visible_dirs(tracks_dir):
        meta_file = track_path / "track.yaml"
        meta = (yaml.safe_load(meta_file.read_text(encoding="utf-8")) if meta_file.exists() else None) or {}
        track = Track(
            id=track_path.name,
            title=str(meta.get("title", track_path.name.replace("-", " ").capitalize())),
            description=str(meta.get("description", "")),
            path=track_path,
            order=int(meta.get("order", 99)),
        )
        for ch_path in _visible_dirs(track_path):
            if (ch_path / "challenge.yaml").exists():
                track.challenges.append(load_challenge(ch_path, track.id))
        tracks.append(track)
    tracks.sort(key=lambda t: (t.order, t.id))
    return tracks


def find_track(tracks_dir: Path, track_id: str) -> Track:
    for track in load_tracks(tracks_dir):
        if track.id == track_id:
            return track
    raise ContentError(f"No track named {track_id}")


def find_challenge(tracks_dir: Path, track_id: str, dir_name: str) -> Challenge:
    for challenge in find_track(tracks_dir, track_id).challenges:
        if challenge.dir_name == dir_name:
            return challenge
    raise ContentError(f"No challenge {track_id}/{dir_name}")


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:48].strip("-") or "challenge"


PROFILE_LISTS = ("stack", "focus", "ai_handles", "targets", "paths")


def load_profile(path: Path) -> dict:
    """The YAML header at the top of my/profile.md, which the dashboard shows. Missing or
    broken headers give an empty profile; `whetstone doctor` reports why."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    match = re.match(r"---\s*\n(.*?)\n---\s*(\n|$)", text, flags=re.S)
    if not match:
        return {}
    try:
        meta = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        return {}
    if not isinstance(meta, dict):
        return {}
    out = {k: str(meta[k]).strip() for k in ("name", "role", "goal", "github") if meta.get(k)}
    for k in PROFILE_LISTS:
        value = meta.get(k) or []
        out[k] = [str(v).strip() for v in (value if isinstance(value, list) else [value]) if str(v).strip()]
    return out


PROFILE_NOTE = "# Read by the app for your dashboard. Your agent keeps it up to date; you can edit it too."
PROFILE_STUB = '\n# Learner profile\n\nYour agent fills this in. Ask it: "Set up my Whetstone profile."\n'


def save_profile_header(path: Path, updates: dict) -> dict:
    """Change fields in the YAML header of my/profile.md and keep the free text below it."""
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    match = re.match(r"---\s*\n(.*?)\n---\s*(\n|$)", text, flags=re.S)
    meta = (yaml.safe_load(match.group(1)) if match else None) or {}
    body = text[match.end() :] if match else text
    meta = {**(meta if isinstance(meta, dict) else {}), **updates}
    header = yaml.safe_dump(meta, sort_keys=False, allow_unicode=True, width=100)
    body = body if body.strip() else PROFILE_STUB
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{PROFILE_NOTE}\n{header}---\n{body if body.startswith(chr(10)) else chr(10) + body}", encoding="utf-8")
    return load_profile(path)

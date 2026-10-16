"""Ask Claude to write a new challenge, validate it, and add it to a track."""

from __future__ import annotations

import re
import shutil
import uuid
from collections.abc import Callable
from pathlib import Path

import yaml

from .config import EXAMPLE, ROOT, Settings
from .content import ContentError, load_challenge, slugify
from .runner import validate_challenge

MAX_ATTEMPTS = 3
SAFE_PATH = re.compile(r"^(?:tests/)?[A-Za-z0-9_\-]+\.(?:py|md|yaml)$")
FILE_BLOCK = re.compile(r'<file path="([^"]+)">\n?(.*?)\n?</file>', re.S)
CHALLENGE_TAG = re.compile(r'<challenge dir="([^"]+)">')


class GenerationError(Exception):
    pass


def _system_prompt(settings: Settings) -> str:
    authoring = (ROOT / "AUTHORING.md").read_text(encoding="utf-8")
    profile_path = settings.profile_path
    profile = profile_path.read_text(encoding="utf-8") if profile_path.exists() else "(no learner profile)"
    return (
        "You write hands-on coding challenges for Whetstone, a self-hosted practice app.\n"
        "Follow the authoring guide exactly. Every test must be deterministic.\n\n"
        f"<authoring_guide>\n{authoring}\n</authoring_guide>\n\n"
        f"<learner_profile>\n{profile}\n</learner_profile>\n\n"
        'Output format: one <challenge dir="short-slug"> element that contains one '
        '<file path="..."> element per file, and nothing else. Do not use Markdown code fences '
        "inside <file> elements. Required files: challenge.yaml, lesson.md, problem.md, hints.md, "
        "starter.py, solution.py, tests/test_visible.py, tests/test_hidden.py. Optional: "
        "tests/conftest.py and support modules listed under `support` in challenge.yaml."
    )


def _example_pack(settings: Settings) -> str:
    """The shipped reference question, as the model sees a finished one."""
    if not EXAMPLE.exists():
        return ""
    parts = [f'<challenge dir="{EXAMPLE.name}">']
    for f in sorted(EXAMPLE.rglob("*")):
        if f.is_file() and "__pycache__" not in f.parts:
            parts.append(f'<file path="{f.relative_to(EXAMPLE).as_posix()}">\n{f.read_text(encoding="utf-8")}\n</file>')
    parts.append("</challenge>")
    return "\n".join(parts)


def parse_pack(text: str) -> tuple[str, dict[str, str]]:
    tag = CHALLENGE_TAG.search(text)
    slug = slugify(tag.group(1)) if tag else "challenge"
    files: dict[str, str] = {}
    for path, body in FILE_BLOCK.findall(text):
        path = path.strip()
        if not SAFE_PATH.match(path):
            raise GenerationError(f"Unsafe or unexpected file path from model: {path!r}")
        files[path] = body.rstrip() + "\n"
    if not files:
        raise GenerationError("The model reply had no <file> elements.")
    return slug, files


def _call_claude(settings: Settings, messages: list[dict]) -> str:
    try:
        import anthropic
    except ImportError as exc:  # pragma: no cover
        raise GenerationError("Install the anthropic package: pip install anthropic") from exc
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    with client.messages.stream(
        model=settings.model,
        max_tokens=16000,
        system=_system_prompt(settings),
        messages=messages,
    ) as stream:
        return stream.get_final_text()


def ensure_track(settings: Settings, track_id: str, title: str | None = None, description: str | None = None) -> Path:
    track_dir = settings.tracks_dir / track_id
    if not track_dir.exists():
        track_dir.mkdir(parents=True)
        meta = {
            "title": title or track_id.replace("-", " ").capitalize(),
            "description": description or "Generated challenges.",
            "order": 50,
        }
        (track_dir / "track.yaml").write_text(yaml.safe_dump(meta, sort_keys=False), encoding="utf-8")
    return track_dir


def _next_dir_name(track_dir: Path, slug: str) -> str:
    numbers = [int(m.group(1)) for p in track_dir.iterdir() if p.is_dir() and (m := re.match(r"(\d+)-", p.name))]
    return f"{(max(numbers) + 1 if numbers else 1):02d}-{slug}"


def install_challenge(
    settings: Settings, stage: Path, track_id: str, title: str | None = None, description: str | None = None
) -> tuple[str | None, list[str], list[str]]:
    """Validate a challenge folder. If it passes, move it into the track as the next
    numbered challenge. Returns (key or None, problems, notes)."""
    try:
        result = validate_challenge(load_challenge(stage, track_id), settings)
    except (ContentError, yaml.YAMLError, OSError) as exc:
        return None, [str(exc)], []
    if not result.ok:
        return None, result.problems, result.notes
    track_dir = ensure_track(settings, track_id, title, description)
    dir_name = _next_dir_name(track_dir, slugify(re.sub(r"^\d+-", "", stage.name)))
    shutil.move(str(stage), str(track_dir / dir_name))
    return f"{track_id}/{dir_name}", [], result.notes


def generate_challenge(
    settings: Settings,
    topic: str,
    track_id: str,
    track_title: str | None = None,
    difficulty: str = "medium",
    notes: str = "",
    log: Callable[[str], None] = print,
    call: Callable[[Settings, list[dict]], str] | None = None,
) -> str:
    """Return the new challenge key ("track/dir") after it passes validation."""
    if call is None and not settings.generator_enabled:
        raise GenerationError(
            "Set ANTHROPIC_API_KEY to generate challenges in the app, or author them with Claude Code (see AUTHORING.md)."
        )
    call = call or _call_claude
    track_id = slugify(track_id)
    track_dir = ensure_track(settings, track_id, track_title)
    existing = [p.name for p in track_dir.iterdir() if p.is_dir() and not p.name.startswith((".", "_"))]

    request = (
        "Here is one finished challenge, for format and quality:\n\n"
        f"{_example_pack(settings)}\n\n"
        "Write a NEW challenge.\n"
        f"Topic: {topic}\n"
        f"Difficulty: {difficulty}\n"
        f"Track: {track_title or track_id}\n"
        f"Existing challenges in this track (do not repeat them): {', '.join(existing) or 'none'}\n"
        f"Extra notes from the learner: {notes or 'none'}"
    )
    messages: list[dict] = [{"role": "user", "content": request}]
    staging_root = settings.staging_dir / uuid.uuid4().hex[:8]

    try:
        for attempt in range(1, MAX_ATTEMPTS + 1):
            log(f"Attempt {attempt}: asking {settings.model} to write the challenge...")
            reply = call(settings, messages)
            try:
                slug, files = parse_pack(reply)
            except GenerationError as exc:
                log(f"Could not read the reply: {exc}")
                messages += [
                    {"role": "assistant", "content": reply},
                    {"role": "user", "content": f"{exc} Reply again in the required format."},
                ]
                continue

            stage = staging_root / slug
            if stage.exists():
                shutil.rmtree(stage)
            for rel, body in files.items():
                dest = stage / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(body, encoding="utf-8")

            log("Validating: the reference solution must pass, the starter must fail...")
            key, problems, notes = install_challenge(settings, stage, track_id)
            for note in notes:
                log(f"  {note}")
            if key:
                log(f"Added {key}.")
                return key

            log("Validation failed: " + "; ".join(problems[:5]))
            messages += [
                {"role": "assistant", "content": reply},
                {
                    "role": "user",
                    "content": "Validation failed:\n- "
                    + "\n- ".join(problems)
                    + "\nFix the problems and return the COMPLETE challenge again in the same format.",
                },
            ]
        raise GenerationError(f"The challenge did not pass validation after {MAX_ATTEMPTS} attempts.")
    finally:
        shutil.rmtree(staging_root, ignore_errors=True)
        parent = settings.staging_dir
        if parent.exists() and not any(parent.iterdir()):
            parent.rmdir()

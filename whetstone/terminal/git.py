"""Build git scenarios with fixed dates, and read what a script left behind."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from .sh import ENV

START = 1767603600  # 2026-01-05 09:00 UTC; each commit is a minute after the one before


def git(repo: Path, *args: str, date: int | None = None) -> str:
    """Run git in `repo` and return its output, stripped. Raises if git fails."""
    env = {**ENV, "HOME": tempfile.gettempdir()}
    if date is not None:
        env |= {"GIT_AUTHOR_DATE": f"@{date} +0000", "GIT_COMMITTER_DATE": f"@{date} +0000"}
    done = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, env=env)
    if done.returncode:
        raise RuntimeError(f"git {' '.join(args)} failed: {done.stderr.strip()}")
    return done.stdout.strip()


def init(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    git(path, "init", "-q", "-b", "main")
    return path


def commit(repo: Path, message: str, files: dict[str, str]) -> str:
    """Write `files` (path: text), commit them a minute after the last commit, and return the hash."""
    for name, text in files.items():
        (repo / name).parent.mkdir(parents=True, exist_ok=True)
        (repo / name).write_text(text, encoding="utf-8")
    git(repo, "add", "-A")
    count = int(git(repo, "rev-list", "--all", "--reflog", "--count") or 0)
    git(repo, "commit", "-q", "-m", message, date=START + 60 * count)
    return git(repo, "rev-parse", "HEAD")


def subjects(repo: Path, ref: str = "HEAD") -> list[str]:
    """The commit subjects on `ref`, newest first."""
    out = git(repo, "log", "--format=%s", ref)
    return out.splitlines() if out else []


def branches(repo: Path) -> list[str]:
    out = git(repo, "branch", "--format=%(refname:short)")
    return out.splitlines() if out else []


def is_clean(repo: Path) -> bool:
    """No uncommitted changes and no untracked files."""
    return git(repo, "status", "--porcelain") == ""

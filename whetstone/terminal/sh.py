"""Run the learner's solution.sh the same way every time."""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

# In a run, this file is tools/sh.py and the learner's script sits next to tools/.
SCRIPT = Path(__file__).resolve().parents[1] / "solution.sh"

# The same answer gives the same output on every machine: no locale, time zone or personal git
# config, and a fixed identity and date for any commit the script makes.
ENV = {
    "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
    "LC_ALL": "C",
    "TZ": "UTC",
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_AUTHOR_NAME": "Sam Okafor",
    "GIT_AUTHOR_EMAIL": "sam@example.com",
    "GIT_COMMITTER_NAME": "Sam Okafor",
    "GIT_COMMITTER_EMAIL": "sam@example.com",
    "GIT_AUTHOR_DATE": "2026-01-05T09:00:00Z",
    "GIT_COMMITTER_DATE": "2026-01-05T09:00:00Z",
}


def run(cwd: Path, *args: str, stdin: str | None = None, timeout: float = 10) -> subprocess.CompletedProcess:
    """Run solution.sh in `cwd` with `args` and an empty HOME. The result has stdout, stderr and
    returncode, as text."""
    with tempfile.TemporaryDirectory() as home:
        return subprocess.run(
            ["bash", str(SCRIPT), *args],
            cwd=cwd,
            input=stdin,
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**ENV, "HOME": home},
        )

#!/usr/bin/env python3
"""Tutor guard: a Claude Code PreToolUse hook. The agent tutors; it does not write the learner's work.

It refuses a write to the progress database and to a solo (terminal) question's folder. Exit code 2
blocks the tool call, and the agent reads the reason on stderr. Standard library only.
"""

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOME = Path(os.environ.get("WHETSTONE_HOME") or ROOT / "my").resolve()
DB = "The learner's progress is theirs: do not write to whetstone.db. Use bin/whetstone (note, grade, request), or read it with ?mode=ro."
SOLO = "This is a solo terminal question: the learner writes solution.sh and works in sandbox/ on their own. Give one hint instead."


def is_solo(path: Path) -> bool:
    """True inside the folder of a terminal question the learner started (whetstone/rounds.py writes the marker)."""
    workspaces = HOME / "workspaces"
    if workspaces not in path.parents:
        return False
    question = workspaces.joinpath(*path.relative_to(workspaces).parts[:2])
    marker = question / "AGENTS.md"
    return marker.is_file() and marker.read_text(errors="replace").startswith("# Solo practice")


def refusal(call: dict) -> str | None:
    tool, args = call.get("tool_name"), call.get("tool_input") or {}
    if tool == "Bash":
        # ponytail: catches sqlite3 on the database only; a shell can write a file in a hundred ways. The rules in AGENTS.md cover the rest.
        command = args.get("command", "")
        return DB if re.search(r"\bsqlite3\b", command) and "whetstone.db" in command and "mode=ro" not in command else None
    target = args.get("file_path") or args.get("notebook_path")
    if tool not in ("Edit", "Write", "MultiEdit", "NotebookEdit") or not target:
        return None
    path = (Path(call.get("cwd") or ".") / target).resolve()
    if path.name.startswith("whetstone.db") and path.parent == HOME:
        return DB
    return SOLO if is_solo(path) else None


if __name__ == "__main__":
    try:
        reason = refusal(json.load(sys.stdin))
    except Exception:  # a broken guard must not block all work
        reason = None
    if reason:
        print(f"Whetstone tutor guard: {reason}", file=sys.stderr)
        sys.exit(2)

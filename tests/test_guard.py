import json
import subprocess
import sys
from pathlib import Path

GUARD = Path(__file__).resolve().parents[1] / ".claude" / "hooks" / "tutor_guard.py"


def guard(home: Path, tool: str, **tool_input) -> subprocess.CompletedProcess:
    call = {"tool_name": tool, "tool_input": tool_input, "cwd": str(home)}
    return subprocess.run(
        [sys.executable, str(GUARD)], input=json.dumps(call), capture_output=True, text=True, env={"WHETSTONE_HOME": str(home)}
    )


def test_the_guard_blocks_writes_to_the_learners_work_and_nothing_else(tmp_path):
    solo = tmp_path / "workspaces" / "git-rescue" / "01-lost-commits"
    round_ = tmp_path / "workspaces" / "workflow-engine" / "01-late-refunds"
    for folder, text in ((solo, "# Solo practice: you are a tutor here, not an assistant\n"), (round_, "# An AI-allowed round\n")):
        folder.mkdir(parents=True)
        (folder / "AGENTS.md").write_text(text)

    blocked = [
        guard(tmp_path, "Edit", file_path=str(solo / "solution.sh")),
        guard(tmp_path, "Write", file_path=str(solo / "sandbox" / "notes.txt")),
        guard(tmp_path, "Write", file_path="whetstone.db"),
        guard(tmp_path, "Bash", command="sqlite3 my/whetstone.db 'delete from runs'"),
    ]
    assert [r.returncode for r in blocked] == [2, 2, 2, 2], [r.stderr for r in blocked]
    assert "one hint" in blocked[0].stderr and "progress is theirs" in blocked[2].stderr

    allowed = [
        guard(tmp_path, "Edit", file_path=str(round_ / "refunds.py")),  # an AI-allowed round: the agent may write
        guard(tmp_path, "Write", file_path=str(tmp_path / "tracks" / "m" / "01-q" / "problem.md")),
        guard(tmp_path, "Bash", command='sqlite3 "file:my/whetstone.db?mode=ro" "select * from runs"'),
        guard(tmp_path, "Bash", command="ls my"),
        guard(tmp_path, "Read", file_path=str(solo / "solution.sh")),
    ]
    assert [r.returncode for r in allowed] == [0, 0, 0, 0, 0], [r.stderr for r in allowed]
    assert subprocess.run([sys.executable, str(GUARD)], input="not json", capture_output=True, text=True).returncode == 0

from scenario import build
from tools import sh

STORIES = {
    "week": "a full week of rotated logs",
    "fresh": "a server up for two days, just after midnight",
}


def _top(tmp_path, variant):
    """Build the variant, run solution.sh, and return (what it printed, what it should print)."""
    facts = build(tmp_path, variant)
    out = sh.run(tmp_path)
    said = f": {out.stderr.strip()[-300:]}" if out.stderr.strip() else ""
    assert out.returncode == 0, f"solution.sh exited with {out.returncode} on {STORIES[variant]}{said}"
    return [" ".join(line.split()) for line in out.stdout.splitlines() if line.strip()], facts["top"]


def test_a_full_week_of_logs_counts(tmp_path):
    got, want = _top(tmp_path, "week")
    assert got == want, "on a full week of rotated logs, the counts are off: does the script read every access log that's there?"


def test_a_new_server_with_two_logs(tmp_path):
    got, want = _top(tmp_path, "fresh")
    assert got == want, "on a server up for two days, the counts are off: today's log can be empty, and nothing is gzipped yet"

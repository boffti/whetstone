import pytest
from scenario import build
from tools import sh

STORIES = {
    "ties": "paths tie on failures",
    "busy": "one path failed more than 20 times",
    "gateway": "most failures came through the partner gateway",
    "not-found": "a broken link sent many people to the 404 page",
    "probes": "scanners and a broken client sent malformed requests",
    "few": "only two paths failed",
    "calm": "nothing failed",
}


def _top(tmp_path, variant):
    """Build the variant, run solution.sh, and return (what it printed, what it should print)."""
    facts = build(tmp_path, variant)
    out = sh.run(tmp_path)
    said = f": {out.stderr.strip()[-300:]}" if out.stderr.strip() else ""
    assert out.returncode == 0, f"solution.sh exited with {out.returncode} on a log where {STORIES[variant]}{said}"
    return [" ".join(line.split()) for line in out.stdout.splitlines() if line.strip()], facts["top"]


def test_ties_go_by_path_in_byte_order(tmp_path):
    got, want = _top(tmp_path, "ties")
    assert got == want, "when paths tie on failures, they come out in the wrong order: which part of your sort breaks a tie?"


def test_counts_of_ten_or_more_rank_as_numbers(tmp_path):
    got, want = _top(tmp_path, "busy")
    assert got == want, "when a path failed 10 or more times, the order is wrong: is the count compared as a number, or as text?"


def test_failures_through_the_partner_gateway_count(tmp_path):
    got, want = _top(tmp_path, "gateway")
    assert got == want, (
        "when most failures came through the partner gateway, the counts are off: where is the status on a line with two addresses?"
    )


def test_client_errors_are_not_failures(tmp_path):
    got, want = _top(tmp_path, "not-found")
    assert got == want, "on a day with many 404s, a path that never failed made the list: what else on a line can look like a 5xx?"


def test_malformed_requests_are_skipped(tmp_path):
    got, want = _top(tmp_path, "probes")
    assert got == want, "with malformed requests in the log, the counts are off: only a method, a path and a protocol is a request"


@pytest.mark.parametrize("variant", ["few", "calm"])
def test_a_quiet_log_prints_only_what_failed(tmp_path, variant):
    got, want = _top(tmp_path, variant)
    assert got == want, f"when {STORIES[variant]}, the output is wrong: print the paths that failed, and nothing else"

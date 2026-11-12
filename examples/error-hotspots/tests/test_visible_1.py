from scenario import build
from tools import sh


def printed(out):
    """The script's lines, without the padding before the count."""
    return [" ".join(line.split()) for line in out.stdout.splitlines() if line.strip()]


def test_the_three_paths_that_fail_most_come_first(tmp_path):
    facts = build(tmp_path, "today")
    out = sh.run(tmp_path)
    assert out.returncode == 0, out.stderr
    assert printed(out) == facts["top"]


def test_each_line_is_a_count_then_a_path_without_its_query(tmp_path):
    build(tmp_path, "today")
    out = sh.run(tmp_path)
    assert printed(out), "solution.sh printed nothing"
    for line in printed(out):
        count, _, path = line.partition(" ")
        assert count.isdigit() and path.startswith("/"), f"{line!r} is not '<count> <path>'"
        assert "?" not in path, f"{path!r} still has its query string"

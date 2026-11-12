import hashlib

from scenario import build
from tools import sh


def printed(out):
    """The script's lines, without the padding before the count."""
    return [" ".join(line.split()) for line in out.stdout.splitlines() if line.strip()]


def test_the_top_three_across_every_day_of_logs(tmp_path):
    facts = build(tmp_path, "visible")
    out = sh.run(tmp_path)
    assert out.returncode == 0, out.stderr
    assert printed(out) == facts["top"]


def test_the_logs_are_left_as_they_were(tmp_path):
    build(tmp_path, "visible")
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()[:12] for p in sorted(tmp_path.iterdir())}
    sh.run(tmp_path)
    after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()[:12] for p in sorted(tmp_path.iterdir()) if p.is_file()}
    assert sorted(after) == sorted(before), "solution.sh added or removed files in the log folder"
    assert after == before, "solution.sh changed a log file"

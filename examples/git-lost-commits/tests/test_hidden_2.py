import pytest
from scenario import build
from tools import git, sh

STORIES = {
    "merge": "after a teammate's branch was merged",
    "three": "with three lost commits and work on two branches since",
}


@pytest.mark.parametrize("variant", sorted(STORIES))
def test_everything_is_back_in_order(tmp_path, variant):
    facts = build(tmp_path, variant)
    out = sh.run(tmp_path)
    assert out.returncode == 0, f"solution.sh failed {STORIES[variant]}: {out.stderr.strip()[-300:]}"
    lost, since = facts["lost_subjects"][::-1], facts["since"]
    assert git.subjects(tmp_path, "main")[: len(lost) + len(since)] == [*lost, *since], (
        f"{STORIES[variant]}, main is missing commits or has them in the wrong order"
    )
    assert git.git(tmp_path, "rev-list", "--merges", "--count", "main") == "0", f"{STORIES[variant]}, main has a merge commit"
    assert git.git(tmp_path, "diff", "rescue", "main", "--", "fees.py") == "", f"{STORIES[variant]}, fees.py lost a change"
    assert git.is_clean(tmp_path) and git.git(tmp_path, "rev-parse", "--abbrev-ref", "HEAD") == "main"

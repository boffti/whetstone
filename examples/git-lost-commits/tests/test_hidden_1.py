from scenario import build
from tools import git, sh


def _rescue(tmp_path, variant):
    facts = build(tmp_path, variant)
    out = sh.run(tmp_path)
    assert out.returncode == 0, f"solution.sh failed on a repo where {variant_story(variant)}: {out.stderr.strip()[-300:]}"
    return facts


def variant_story(variant):
    return {
        "merge": "a teammate's branch was merged after the reset",
        "three": "three commits were lost, then work went on across two branches",
    }[variant]


def test_a_merge_after_the_reset_does_not_hide_the_lost_commits(tmp_path):
    facts = _rescue(tmp_path, "merge")
    assert git.git(tmp_path, "rev-parse", "rescue") == facts["lost"][-1], (
        "after a merge on main, rescue points at the wrong commit: a merge moves ORIG_HEAD"
    )


def test_other_messages_and_more_moves(tmp_path):
    facts = _rescue(tmp_path, "three")
    assert git.git(tmp_path, "rev-parse", "rescue") == facts["lost"][-1], (
        "with other commit messages and more work since, rescue points at the wrong commit"
    )

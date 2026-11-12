from scenario import build
from tools import git, sh


def test_lost_commits_are_back_on_top_of_main(tmp_path):
    facts = build(tmp_path, "visible")
    out = sh.run(tmp_path)
    assert out.returncode == 0, out.stderr
    lost = facts["lost_subjects"][::-1]  # newest first, as git log prints them
    assert git.subjects(tmp_path, "main")[: len(lost) + 1] == [*lost, *facts["since"]]


def test_history_stays_linear_and_rescue_stays_put(tmp_path):
    facts = build(tmp_path, "visible")
    sh.run(tmp_path)
    assert git.git(tmp_path, "rev-list", "--merges", "--count", "main") == "0", "main has a merge commit"
    assert git.git(tmp_path, "rev-parse", "rescue") == facts["lost"][-1], "rescue moved"
    assert git.git(tmp_path, "rev-parse", "--abbrev-ref", "HEAD") == "main"
    assert git.is_clean(tmp_path)

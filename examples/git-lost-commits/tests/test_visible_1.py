from scenario import build
from tools import git, sh


def test_rescue_points_at_the_newest_lost_commit(tmp_path):
    facts = build(tmp_path, "visible")
    out = sh.run(tmp_path)
    assert out.returncode == 0, out.stderr
    assert "rescue" in git.branches(tmp_path), "there is no branch named rescue"
    assert git.git(tmp_path, "rev-parse", "rescue") == facts["lost"][-1]


def test_the_work_since_stays_on_main(tmp_path):
    facts = build(tmp_path, "visible")
    sh.run(tmp_path)
    assert set(facts["since"]) <= set(git.subjects(tmp_path, "main"))
    assert git.is_clean(tmp_path)

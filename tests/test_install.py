from whetstone.__main__ import TEMPLATE
from whetstone.config import Settings
from whetstone.generator import install_challenge


def _write(folder, starter=None):
    for rel, body in TEMPLATE.items():
        dest = folder / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(body.format(title="Answer"), encoding="utf-8")
    if starter is not None:
        (folder / "starter.py").write_text(starter, encoding="utf-8")


def test_agent_written_challenge_is_validated_then_numbered_into_the_track(tmp_path):
    settings = Settings(tmp_path / "content", tmp_path, "redis://localhost:1/0", None, "model", 30)
    good = tmp_path / "staging" / "07-answer"
    _write(good)
    key, problems, _ = install_challenge(settings, good, "demo", "Demo", "A demo track.")
    assert (key, problems) == ("demo/01-answer", [])
    assert (settings.tracks_dir / "demo" / "01-answer" / "solution.py").exists() and not good.exists()

    too_easy = tmp_path / "staging" / "too-easy"
    _write(too_easy, starter=TEMPLATE["solution.py"])
    key, problems, _ = install_challenge(settings, too_easy, "demo")
    assert key is None and any("starter passes" in p for p in problems)
    assert too_easy.exists(), "a rejected challenge stays in staging so the agent can fix it"

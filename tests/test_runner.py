"""The test run is a subprocess: it must not see the app's secrets, and a timeout must take
everything it started down with it."""

import os
import time

from whetstone.config import Settings
from whetstone.runner import _pytest


def settings(tmp_path):
    return Settings(tmp_path / "content", tmp_path / "my", "redis://localhost:1/0", None, "", 10)


def test_child_gets_an_allowlisted_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-secret")
    monkeypatch.setenv("FORCE_COLOR", "1")
    files = {
        "tests/test_env.py": (
            "import os\n"
            "def test_env():\n"
            "    assert 'ANTHROPIC_API_KEY' not in os.environ\n"
            "    assert 'FORCE_COLOR' not in os.environ\n"
            "    assert os.environ['PATH'] and os.environ['NO_COLOR']\n"
        )
    }
    tests, output, _ = _pytest(files, "tests", 30, settings(tmp_path))
    assert tests is not None and [t.outcome for t in tests] == ["passed"], output


def test_timeout_kills_what_the_run_started(tmp_path):
    pid_file = tmp_path / "grandchild.pid"
    files = {
        "tests/test_slow.py": (
            "import subprocess, sys, time\n"
            "def test_slow():\n"
            f"    child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
            f"    open({str(pid_file)!r}, 'w').write(str(child.pid))\n"
            "    time.sleep(60)\n"
        )
    }
    started = time.monotonic()
    tests, _, _ = _pytest(files, "tests", 2, settings(tmp_path))
    assert tests is None, "a run that overruns reports a timeout"
    assert time.monotonic() - started < 10, "the timeout is enforced, not the grandchild's sleep"
    pid = int(pid_file.read_text())
    for _ in range(20):  # init reaps the orphan after the kill; give it a moment
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            break
        time.sleep(0.1)
    else:
        os.kill(pid, 9)
        raise AssertionError("the grandchild outlived the run")

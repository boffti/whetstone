"""Your tests for retry.py. Each function whose name starts with test_ is one test.

They must pass on the real retry.py. On Submit, they also run against hidden buggy
versions of it, and each buggy version must make at least one of your tests fail.
"""

from retry import retry


def test_returns_the_value_when_the_call_works():
    assert retry(lambda: 42, sleep=lambda seconds: None) == 42

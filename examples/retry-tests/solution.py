"""Reference tests for retry.py: they pass on it and catch every known way to break it."""

import pytest
from retry import retry


class Flaky:
    """A call that fails `failures` times, then returns. It numbers its errors."""

    def __init__(self, failures: int) -> None:
        self.failures = failures
        self.calls = 0

    def __call__(self) -> str:
        self.calls += 1
        if self.calls <= self.failures:
            raise ConnectionError(f"failure {self.calls}")
        return "ok"


def record():
    """A fake sleep that remembers each wait instead of waiting."""
    waits: list[float] = []
    return waits, waits.append


def test_returns_the_value_when_the_call_works():
    assert retry(lambda: 42, sleep=lambda seconds: None) == 42


def test_keeps_calling_until_the_call_works():
    flaky = Flaky(2)
    assert retry(flaky, attempts=3, sleep=lambda seconds: None) == "ok"
    assert flaky.calls == 3  # attempts counts calls, not retries


def test_one_attempt_means_exactly_one_call():
    flaky = Flaky(0)
    assert retry(flaky, attempts=1, sleep=lambda seconds: None) == "ok"
    assert flaky.calls == 1


def test_waits_twice_as_long_each_time():
    waits, sleep = record()
    retry(Flaky(2), attempts=3, base_delay=0.1, sleep=sleep)
    assert waits == [0.1, 0.2]


def test_raises_the_last_error_and_does_not_wait_after_it():
    waits, sleep = record()
    with pytest.raises(ConnectionError, match="failure 3"):
        retry(Flaky(5), attempts=3, base_delay=0.1, sleep=sleep)
    assert waits == [0.1, 0.2]


def test_rejects_zero_attempts():
    with pytest.raises(ValueError):
        retry(lambda: 1, attempts=0)

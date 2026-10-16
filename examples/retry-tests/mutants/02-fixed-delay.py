"""Misconception: backoff means waiting the same time between tries."""

import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


def retry(fn: Callable[[], T], attempts: int = 3, base_delay: float = 0.1, sleep: Callable[[float], None] = time.sleep) -> T:
    """Call fn until it returns, at most `attempts` times in all.

    Between tries, wait base_delay, then twice that, then four times, and so on.
    After the last failed try, raise its error. Never wait after the last try.
    """
    if attempts < 1:
        raise ValueError("attempts must be at least 1")
    for i in range(attempts):
        try:
            return fn()
        except Exception:
            if i == attempts - 1:
                raise
            sleep(base_delay)
    raise AssertionError("unreachable")

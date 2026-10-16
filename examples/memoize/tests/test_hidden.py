import time

import pytest

from solution import CachedAPI


class Counter:
    def __init__(self, fn=lambda n: n * n):
        self.fn = fn
        self.calls = 0

    def __call__(self, n):
        self.calls += 1
        return self.fn(n)


def test_each_unique_input_computed_once():
    compute = Counter()
    api = CachedAPI(compute)
    for n in [1, 2, 3, 1, 2, 3, 1]:
        api.get(n)
    assert compute.calls == 3


def test_caches_zero_and_other_falsy_results():
    compute = Counter(lambda n: 0)
    api = CachedAPI(compute)
    assert api.get(7) == 0
    assert api.get(7) == 0
    assert compute.calls == 1, "A saved 0 must count as a hit. Use `n in cache`, not `cache.get(n)`."


def test_negative_inputs_are_separate_keys():
    api = CachedAPI(lambda n: n * 10)
    assert api.get(-1) == -10
    assert api.get(1) == 10


def test_second_call_is_fast():
    def slow(n):
        time.sleep(0.2)
        return n

    api = CachedAPI(slow)
    api.get(1)
    start = time.perf_counter()
    api.get(1)
    assert time.perf_counter() - start < 0.05


def test_errors_are_not_cached():
    state = {"calls": 0}

    def flaky(n):
        state["calls"] += 1
        if state["calls"] == 1:
            raise ValueError("vendor timeout")
        return n

    api = CachedAPI(flaky)
    with pytest.raises(ValueError):
        api.get(5)
    assert api.get(5) == 5
    assert api.get(5) == 5
    assert state["calls"] == 2


def test_instances_do_not_share_a_cache():
    a = CachedAPI(lambda n: n + 100)
    b = CachedAPI(lambda n: n + 200)
    assert a.get(1) == 101
    assert b.get(1) == 201, "Each object needs its own cache. Create it in __init__."

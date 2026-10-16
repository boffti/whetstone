from solution import CachedAPI


class Counter:
    """A compute function that counts its calls."""

    def __init__(self, fn=lambda n: n * n):
        self.fn = fn
        self.calls = 0

    def __call__(self, n):
        self.calls += 1
        return self.fn(n)


def test_returns_correct_values():
    api = CachedAPI(lambda n: n * n)
    assert api.get(4) == 16
    assert api.get(5) == 25


def test_computes_each_input_once():
    compute = Counter()
    api = CachedAPI(compute)
    for _ in range(5):
        assert api.get(3) == 9
    assert compute.calls == 1


def test_stats_count_hits_and_misses():
    api = CachedAPI(lambda n: n + 1)
    api.get(1)
    api.get(1)
    api.get(2)
    assert api.stats() == {"hits": 1, "misses": 2}

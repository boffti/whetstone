from typing import Callable


class CachedAPI:
    """Wraps a slow, pure function. Each unique input is computed only once."""

    def __init__(self, compute: Callable[[int], int]) -> None:
        self._compute = compute
        # TODO: create the cache and the hit/miss counters.

    def get(self, n: int) -> int:
        # TODO: return the saved value on a hit. Compute and save it on a miss.
        return self._compute(n)

    def stats(self) -> dict[str, int]:
        # TODO: return the real counts.
        return {"hits": 0, "misses": 0}

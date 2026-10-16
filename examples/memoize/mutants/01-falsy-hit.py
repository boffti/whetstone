"""Misconception: cache.get(n) tells you whether n is cached."""

from collections.abc import Callable


class CachedAPI:
    """Wraps a slow, pure function. Each unique input is computed only once."""

    def __init__(self, compute: Callable[[int], int]) -> None:
        self._compute = compute
        self._cache: dict[int, int] = {}
        self._hits = 0
        self._misses = 0

    def get(self, n: int) -> int:
        if self._cache.get(n):
            self._hits += 1
            return self._cache[n]
        self._misses += 1
        value = self._compute(n)  # if this raises, nothing is saved
        self._cache[n] = value
        return value

    def stats(self) -> dict[str, int]:
        return {"hits": self._hits, "misses": self._misses}

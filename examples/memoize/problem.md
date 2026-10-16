## Task

You get a slow, pure function `compute(n: int) -> int`. You cannot change it. Write a class `CachedAPI` that wraps it. Each unique input must be computed only once.

## API

```python
class CachedAPI:
    def __init__(self, compute: Callable[[int], int]) -> None: ...
    def get(self, n: int) -> int: ...
    def stats(self) -> dict[str, int]:  # {"hits": int, "misses": int}
```

## Rules

- `get(n)` returns `compute(n)`. It calls `compute` at most once for each `n`.
- `stats()` returns the number of cache hits and misses since the object was created.
- Each `CachedAPI` object has its own cache.
- If `compute` raises an exception, `get` raises the same exception and saves nothing.
- You do not need thread safety yet. That comes in the next question.

## Example

```python
api = CachedAPI(lambda n: n * n)
api.get(4)   # 16, miss
api.get(4)   # 16, hit
api.stats()  # {"hits": 1, "misses": 1}
```

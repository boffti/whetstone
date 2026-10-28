## Task

A webhook sender calls `try_send(merchant)` before each delivery to a merchant's endpoint. When the call returns `False`, the sender holds the event and tries again later. The limiter is `subject.py`, read-only, next to your code.

Read it, then predict what it does on three scripted runs. Predict by reading: `solution.py` may not import `subject`, and the tests check that.

## API

Fill in `ANSWERS` in `solution.py`:

```python
ANSWERS = {
    "burst_allowed_at_61": ...,    # bool
    "burst_count_at_61": ...,      # int
    "retries_allowed_at_75": ...,  # bool
    "retries_count_at_75": ...,    # int
    "spread_allowed_at_60": ...,   # bool
}
```

Every run uses this script: a fresh limiter with `limit=3, window=60`, and a fake clock set to each time in turn.

```python
def run(times):
    clock = FakeClock()  # clock() returns clock.now, in seconds
    limiter = DeliveryLimiter(limit=3, window=60, clock=clock)
    results = []
    for t in times:
        clock.now = t
        results.append(limiter.try_send("shop_a"))
    return limiter, results
```

## Predict

**1. Burst.** `limiter, results = run([50, 55, 58, 61])`

- `burst_allowed_at_61` (bool): `results[-1]`, the try at second 61.
- `burst_count_at_61` (int): `limiter.in_window("shop_a")` right after that, with the clock still at 61.

**2. Retries.** `limiter, results = run([0, 10, 20, 30, 45, 75])`. The tries at 30 and 45 are the sender retrying a held event.

- `retries_allowed_at_75` (bool): `results[-1]`, the try at second 75.
- `retries_count_at_75` (int): `limiter.in_window("shop_a")` right after that, with the clock still at 75.

**3. Spread.** `limiter, results = run([0, 30, 40, 60])`

- `spread_allowed_at_60` (bool): `results[-1]`, the try at second 60.

## Example

A different run shows the format. `run([0, 5])` gives `results == [True, True]`, and `in_window("shop_a")` is then `2`. Written as answers:

```python
ANSWERS = {"example_allowed_at_5": True, "example_count_at_5": 2}
```

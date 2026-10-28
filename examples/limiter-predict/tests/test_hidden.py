"""The expected values come from running subject.py here, never from a copy of the answers."""

from decimal import Decimal

from solution import ANSWERS
from subject import DeliveryLimiter

PLAIN = (int, float, str, bool, Decimal)


class FakeClock:
    def __init__(self) -> None:
        self.now = 0

    def __call__(self) -> int:
        return self.now


def run(times: list[int]) -> tuple[DeliveryLimiter, list[bool]]:
    """The script in problem.md: a fresh limiter, and one try_send("shop_a") at each time."""
    clock = FakeClock()
    limiter = DeliveryLimiter(limit=3, window=60, clock=clock)
    results = []
    for t in times:
        clock.now = t
        results.append(limiter.try_send("shop_a"))
    return limiter, results


def _result() -> dict:
    burst, burst_results = run([50, 55, 58, 61])
    retries, retries_results = run([0, 10, 20, 30, 45, 75])
    _, spread_results = run([0, 30, 40, 60])
    return {
        "burst_allowed_at_61": burst_results[-1],
        "burst_count_at_61": burst.in_window("shop_a"),  # the clock is still at 61
        "retries_allowed_at_75": retries_results[-1],
        "retries_count_at_75": retries.in_window("shop_a"),  # the clock is still at 75
        "spread_allowed_at_60": spread_results[-1],
    }


RESULT = _result()


def test_predictions_are_plain_values():
    # Exact types: a value with its own __eq__ would agree with anything.
    assert type(ANSWERS) is dict, "Keep ANSWERS a plain dict."
    odd = [k for k, v in ANSWERS.items() if type(v) not in PLAIN]
    assert not odd, "Each prediction is a plain int, float, str, bool or Decimal: " + ", ".join(odd) + "."


# `ok = a == b; assert ok` so a failure shows the message and never the values.
def test_burst_allowed_at_61():
    ok = ANSWERS["burst_allowed_at_61"] == RESULT["burst_allowed_at_61"]
    assert ok, "Does the look-back start at the top of the minute? Work out `cutoff` at second 61 and check 50, 55 and 58 against it."


def test_burst_count_at_61():
    ok = ANSWERS["burst_count_at_61"] == RESULT["burst_count_at_61"]
    assert ok, "Does the try at second 61 add a time to the deque? Follow it from the limit check to `append`."


def test_retries_allowed_at_75():
    ok = ANSWERS["retries_allowed_at_75"] == RESULT["retries_allowed_at_75"]
    assert ok, "Do the refused retries at 30 and 45 count against the limit? Write the deque after each call of the retries run."


def test_retries_count_at_75():
    ok = ANSWERS["retries_count_at_75"] == RESULT["retries_count_at_75"]
    assert ok, "Which times are still in the deque at second 75? Drop each one the cutoff removes, then add what the try at 75 recorded."


def test_spread_allowed_at_60():
    ok = ANSWERS["spread_allowed_at_60"] == RESULT["spread_allowed_at_60"]
    assert ok, "Does a delivery exactly 60 seconds old still count? Read the comparison in the loop that drops old times."

"""The right predictions."""

ANSWERS = {
    # The cutoff is 61 - 60 = 1, so 50, 55 and 58 all still count: the look-back starts at the
    # call, not at the top of the minute. Three already count, so the try is refused.
    "burst_allowed_at_61": False,
    # The refused try returns before append, so nothing was added.
    "burst_count_at_61": 3,
    # The tries at 30 and 45 were refused and never recorded. At 75 the cutoff is 15, which
    # drops 0 and 10 and leaves only 20, so there is room.
    "retries_allowed_at_75": True,
    # 20 is still after the cutoff, and the delivery at 75 was just added.
    "retries_count_at_75": 2,
    # At 60 the cutoff is 0, and `<=` drops a time equal to it: the delivery at 0 stops
    # counting at exactly 60 seconds, leaving 30 and 40.
    "spread_allowed_at_60": True,
}

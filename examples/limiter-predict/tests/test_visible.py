from solution import ANSWERS

KEYS = (
    "burst_allowed_at_61",
    "burst_count_at_61",
    "retries_allowed_at_75",
    "retries_count_at_75",
    "spread_allowed_at_60",
)


def test_every_prediction_is_filled_in():
    missing = [k for k in KEYS if k not in ANSWERS or ANSWERS[k] is ...]
    assert not missing, "Fill in every prediction: " + ", ".join(missing) + "."

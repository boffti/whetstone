from orders import order
from refunds.flow import load_flow, run
from refunds.ledger import Ledger

LATE = load_flow("flows/late_order.json")


def test_a_day_late_is_very_late():
    assert run(LATE, order(24 * 60 + 30), Ledger()) == 1200, "an order a day and 30 minutes late was not refunded as very late"


def test_exactly_twenty_minutes_is_on_time():
    assert run(LATE, order(20), Ledger()) == 0, "an order exactly 20 minutes late was refunded; the promise allows 20 minutes"


def test_offsets_are_compared_as_times():
    late = {**order(0), "delivered_at": "2026-10-28T07:30:00-05:00"}  # 12:30 UTC
    assert run(LATE, late, Ledger()) == 600, "a delivery stamped in another time zone was not 30 minutes late"

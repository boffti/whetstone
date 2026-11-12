from orders import order
from refunds.flow import load_flow, run
from refunds.ledger import Ledger

LATE = load_flow("flows/late_order.json")


def test_an_early_order_gets_nothing():
    ledger = Ledger()
    assert run(LATE, order(-10), ledger) == 0
    assert ledger.refunds == []


def test_a_late_order_gets_a_quarter_back():
    assert run(LATE, order(45), Ledger()) == 600

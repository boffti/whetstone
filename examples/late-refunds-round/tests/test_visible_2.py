from orders import order
from refunds.flow import load_flow, run
from refunds.ledger import Ledger

LATE = load_flow("flows/late_order.json")
WRONG = load_flow("flows/wrong_order.json")


def test_running_twice_pays_once():
    ledger = Ledger()
    assert run(LATE, order(45), ledger) == 600
    assert run(LATE, order(45), ledger) == 0
    assert len(ledger.refunds) == 1


def test_a_wrong_order_pays_back_the_rest():
    ledger = Ledger()
    assert run(LATE, order(90), ledger) == 1200
    assert run(WRONG, order(90), ledger) == 1200
    assert ledger.paid("o-1") == 2400

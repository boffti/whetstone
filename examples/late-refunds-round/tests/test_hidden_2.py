from hidden_finance import FinanceLedger
from orders import order
from refunds.flow import load_flow, run
from refunds.ledger import Ledger

LATE = load_flow("flows/late_order.json")
WRONG = load_flow("flows/wrong_order.json")
GOODWILL = load_flow("flows/goodwill.json")


def test_another_order_still_pays():
    ledger = Ledger()
    run(LATE, order(45, order_id="o-1"), ledger)
    assert run(LATE, order(45, order_id="o-2"), ledger) == 600, "a second order was refused because another order had been refunded"


def test_two_refunds_in_one_run_both_pay():
    assert run(LATE, order(90), Ledger()) == 1200, "a very late order did not get both refunds of the late flow"


def test_the_cap_counts_every_flow():
    ledger = Ledger()
    run(WRONG, order(90), ledger)
    assert run(LATE, order(90), ledger) == 0, "an order already paid back in full was refunded again by another flow"
    assert ledger.paid("o-1") == 2400


def test_run_returns_what_it_paid():
    ledger = Ledger()
    assert run(GOODWILL, order(0), ledger) == 240
    assert run(WRONG, order(0), ledger) == 2160, "run reported the refund it meant to pay, not the part it could pay"


def test_nothing_left_writes_no_row():
    ledger = Ledger()
    run(WRONG, order(90), ledger)
    run(GOODWILL, order(90), ledger)
    assert all(r.cents > 0 for r in ledger.refunds), "a refund with nothing left to pay wrote a zero-cent row to the ledger"


def test_runs_on_finances_ledger_client():
    ledger = FinanceLedger()
    try:
        paid = [run(LATE, order(90), ledger), run(WRONG, order(90), ledger), run(WRONG, order(90), ledger)]
    except AttributeError:
        paid = None
    assert paid == [1200, 1200, 0], "run needs more of the ledger than pay, paid and refunds, which is all finance's client has"

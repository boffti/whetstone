import pytest
from orders import chain, order
from refunds.flow import FlowError, run
from refunds.ledger import Ledger


def test_a_deep_flow_runs():
    assert run(chain(50_000), order(0), Ledger()) == 240


def test_a_loop_raises():
    flow = {
        "start": "a",
        "nodes": {"a": {"type": "check", "field": "minutes_late", "over": 0, "yes": "a", "no": "end"}, "end": {"type": "end"}},
    }
    with pytest.raises(FlowError):
        run(flow, order(45), Ledger())

import pytest
from orders import chain, order
from refunds.flow import FlowError, run
from refunds.ledger import Ledger


def check(node_id, yes, no, over=20):
    return {node_id: {"type": "check", "field": "minutes_late", "over": over, "yes": yes, "no": no}}


def refund(node_id, then, percent=10):
    return {node_id: {"type": "refund", "percent": percent, "next": then}}


END = {"end": {"type": "end"}}


def test_a_loop_is_found_before_any_refund():
    flow = {"start": "r1", "nodes": {**refund("r1", "c1"), **check("c1", "r1", "end"), **END}}
    ledger = Ledger()
    with pytest.raises(FlowError):
        run(flow, order(45), ledger)
    assert ledger.refunds == [], "a refund was paid before the loop in the flow was found"


def test_a_loop_on_a_branch_not_taken_still_raises():
    flow = {"start": "c0", "nodes": {**check("c0", "r1", "c1"), **refund("r1", "end"), **check("c1", "c1", "end"), **END}}
    ledger = Ledger()
    with pytest.raises(FlowError):
        run(flow, order(45), ledger)  # late: this order takes the yes branch, away from the loop
    assert ledger.refunds == [], "a flow with a loop on another branch paid a refund"


def test_branches_that_meet_are_not_a_loop():
    flow = {"start": "c0", "nodes": {**check("c0", "c1", "c1"), **check("c1", "r1", "r1"), **refund("r1", "end", 25), **END}}
    assert run(flow, order(45), Ledger()) == 600, "two branches meeting at one node were taken for a loop"


def test_a_missing_node_raises_before_paying():
    flow = {"start": "r1", "nodes": {**refund("r1", "c1"), **check("c1", "end", "nowhere"), **END}}
    ledger = Ledger()
    with pytest.raises(FlowError):
        run(flow, order(45), ledger)
    assert ledger.refunds == [], "a flow pointing at a missing node paid a refund first"


def test_the_error_names_a_node_on_the_loop():
    flow = {"start": "c0", "nodes": {**check("c0", "x", "end"), **check("x", "y", "end"), **check("y", "x", "end"), **END}}
    with pytest.raises(FlowError) as raised:
        run(flow, order(45), Ledger())
    assert "x" in str(raised.value) or "y" in str(raised.value), "the FlowError did not name a node on the loop"


def test_a_deep_flow_ending_in_end_runs():
    assert run(chain(50_000, then="end"), order(0), Ledger()) == 0

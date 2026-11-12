"""Load a refund flow and run it on one order."""

import json
from pathlib import Path

from .clock import minutes_late
from .ledger import Ledger

# The nodes each type of node can go to next.
NEXT = {"check": ("yes", "no"), "refund": ("next",), "end": ()}


class FlowError(Exception):
    """The flow itself is broken (see README.md, Conventions)."""


def load_flow(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def facts(order: dict) -> dict:
    """What a check node can ask about an order."""
    return {"minutes_late": minutes_late(order["promised_at"], order["delivered_at"]), "total_cents": order["total_cents"]}


def check(flow: dict) -> None:
    """Raise FlowError if the flow is broken anywhere, on every branch, before anything runs.

    A depth-first walk with an explicit stack, so depth is no limit. A node is "open" while the walk
    is below it and "done" after; reaching an open node again is a loop, reaching a done one is two
    branches meeting, which is fine.
    """
    nodes, state = flow["nodes"], {}
    stack = [(flow["start"], False)]
    while stack:
        node_id, leaving = stack.pop()
        if leaving:
            state[node_id] = "done"
            continue
        if state.get(node_id) == "done":
            continue
        if state.get(node_id) == "open":
            raise FlowError(f"the flow loops back to {node_id}")
        node = nodes.get(node_id)
        if node is None:
            raise FlowError(f"no node named {node_id}")
        if node.get("type") not in NEXT:
            raise FlowError(f"{node_id} has an unknown type: {node.get('type')}")
        state[node_id] = "open"
        stack.append((node_id, True))
        stack.extend((node[key], False) for key in NEXT[node["type"]])


def run(flow: dict, order: dict, ledger: Ledger) -> int:
    """Run the flow on the order from its start node. Return the cents this run paid back."""
    check(flow)
    known, paid, node_id = facts(order), 0, flow["start"]
    while (node := flow["nodes"][node_id])["type"] != "end":
        if node["type"] == "check":
            node_id = node["yes"] if known[node["field"]] > node["over"] else node["no"]
        else:
            paid += _refund(node_id, node, order, ledger)
            node_id = node["next"]
    return paid


def _refund(node_id: str, node: dict, order: dict, ledger: Ledger) -> int:
    """Pay a refund node at most once per order, and never past what the customer paid."""
    if any(r.order_id == order["id"] and r.node_id == node_id for r in ledger.refunds):
        return 0
    cents = min(order["total_cents"] * node["percent"] // 100, order["total_cents"] - ledger.paid(order["id"]))
    if cents <= 0:
        return 0
    ledger.pay(order["id"], node_id, cents)
    return cents

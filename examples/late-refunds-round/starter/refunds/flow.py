"""Load a refund flow and run it on one order."""

import json
from pathlib import Path

from .clock import minutes_late
from .ledger import Ledger


class FlowError(Exception):
    """The flow itself is broken (see README.md, Conventions)."""


def load_flow(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def facts(order: dict) -> dict:
    """What a check node can ask about an order."""
    return {"minutes_late": minutes_late(order["promised_at"], order["delivered_at"]), "total_cents": order["total_cents"]}


def run(flow: dict, order: dict, ledger: Ledger) -> int:
    """Run the flow on the order from its start node. Return the cents this run paid back."""
    return _visit(flow, flow["start"], order, facts(order), ledger)


def _visit(flow: dict, node_id: str, order: dict, known: dict, ledger: Ledger) -> int:
    node = flow["nodes"].get(node_id)
    if node is None:
        raise FlowError(f"no node named {node_id}")
    if node["type"] == "end":
        return 0
    if node["type"] == "check":
        branch = "yes" if known[node["field"]] > node["over"] else "no"
        return _visit(flow, node[branch], order, known, ledger)
    if node["type"] == "refund":
        cents = order["total_cents"] * node["percent"] // 100
        ledger.pay(order["id"], node_id, cents)
        return cents + _visit(flow, node["next"], order, known, ledger)
    raise FlowError(f"{node_id} has an unknown type: {node['type']}")

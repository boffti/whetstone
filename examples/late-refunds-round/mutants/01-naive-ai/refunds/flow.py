"""Load a refund flow and run it on one order."""

import json
from pathlib import Path

from .clock import minutes_late
from .ledger import Ledger


class FlowError(Exception):
    """The flow itself is broken (see README.md, Conventions)."""


FACTS = ("minutes_late", "total_cents")
REQUIRED = {
    "end": (),
    "check": ("field", "over", "yes", "no"),
    "refund": ("percent", "next"),
}


def load_flow(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def facts(order: dict) -> dict:
    """What a check node can ask about an order."""
    return {"minutes_late": minutes_late(order["promised_at"], order["delivered_at"]), "total_cents": order["total_cents"]}


def _targets(node: dict) -> tuple:
    if node["type"] == "check":
        return node["yes"], node["no"]
    if node["type"] == "refund":
        return (node["next"],)
    return ()


def validate(flow: dict) -> None:
    """Raise FlowError unless every node is well formed, every pointer lands and nothing loops."""
    nodes = flow.get("nodes") if isinstance(flow, dict) else None
    if not isinstance(nodes, dict):
        raise FlowError("flow has no nodes")
    if flow.get("start") not in nodes:
        raise FlowError(f"no node named {flow.get('start')}")
    for node_id, node in nodes.items():
        kind = node.get("type") if isinstance(node, dict) else None
        if kind not in REQUIRED:
            raise FlowError(f"{node_id} has an unknown type: {kind}")
        for key in REQUIRED[kind]:
            if key not in node:
                raise FlowError(f"{node_id} is missing {key}")
        if kind == "check" and node["field"] not in FACTS:
            raise FlowError(f"{node_id} asks about unknown field {node['field']}")
        for target in _targets(node):
            if target not in nodes:
                raise FlowError(f"{node_id} points at {target}, which does not exist")
    # Loop check over every node, iteratively: 0 unseen, 1 on the current path, 2 done.
    state: dict = {}
    for root in nodes:
        if root in state:
            continue
        state[root] = 1
        stack = [(root, iter(_targets(nodes[root])))]
        while stack:
            node_id, targets = stack[-1]
            for target in targets:
                seen = state.get(target, 0)
                if seen == 1:
                    raise FlowError(f"{target} is part of a loop")
                if seen == 0:
                    state[target] = 1
                    stack.append((target, iter(_targets(nodes[target]))))
                    break
            else:
                state[node_id] = 2
                stack.pop()


def run(flow: dict, order: dict, ledger: Ledger) -> int:
    """Run the flow on the order from its start node. Return the cents this run paid back."""
    validate(flow)
    known = facts(order)
    nodes = flow["nodes"]
    paid = 0
    node_id = flow["start"]
    while True:
        node = nodes[node_id]
        if node["type"] == "end":
            return paid
        if node["type"] == "check":
            node_id = node["yes"] if known[node["field"]] > node["over"] else node["no"]
        else:
            cents = order["total_cents"] * node["percent"] // 100
            paid += ledger.refund_up_to(order["id"], node_id, cents, order["total_cents"])
            node_id = node["next"]

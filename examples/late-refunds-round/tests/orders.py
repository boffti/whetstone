"""Orders and flows for the tests."""

from datetime import UTC, datetime, timedelta

PROMISED = datetime(2026, 10, 28, 12, 0, tzinfo=UTC)


def order(minutes_late: float, total_cents: int = 2400, order_id: str = "o-1") -> dict:
    return {
        "id": order_id,
        "total_cents": total_cents,
        "promised_at": PROMISED.isoformat(),
        "delivered_at": (PROMISED + timedelta(minutes=minutes_late)).isoformat(),
    }


def chain(length: int, then: str = "refund") -> dict:
    """A flow of `length` check nodes in a row, every branch going on to the next, then one node."""
    nodes = {
        f"c{i}": {"type": "check", "field": "minutes_late", "over": -1e9, "yes": f"c{i + 1}", "no": f"c{i + 1}"} for i in range(length)
    }
    nodes[f"c{length}"] = {"type": "refund", "percent": 10, "next": "end"} if then == "refund" else {"type": "end"}
    nodes["end"] = {"type": "end"}
    return {"start": "c0", "nodes": nodes}

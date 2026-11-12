"""Time helpers. Every timestamp on an order is an ISO 8601 string with a UTC offset."""

from datetime import datetime


def minutes_late(promised_at: str, delivered_at: str) -> float:
    """How many minutes after the promised time the order arrived. An early order is negative."""
    late = datetime.fromisoformat(delivered_at) - datetime.fromisoformat(promised_at)
    return late.total_seconds() / 60

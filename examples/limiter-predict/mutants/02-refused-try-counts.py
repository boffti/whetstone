"""Misconception: a refused try still counts against the merchant's limit."""

from collections import deque
from collections.abc import Callable


class DeliveryLimiter:
    """At most `limit` webhook deliveries per merchant per `window` seconds."""

    def __init__(self, limit: int, window: float, clock: Callable[[], float]) -> None:
        self.limit = limit
        self.window = window
        self.clock = clock  # returns the current time in seconds
        self._sent: dict[str, deque[float]] = {}

    def _recent(self, merchant: str, now: float) -> deque[float]:
        """The merchant's delivery times that still count, oldest first."""
        sent = self._sent.setdefault(merchant, deque())
        cutoff = now - self.window
        while sent and sent[0] <= cutoff:
            sent.popleft()
        return sent

    def try_send(self, merchant: str) -> bool:
        """Call before each delivery. False means: hold the event and try again later."""
        now = self.clock()
        sent = self._recent(merchant, now)
        sent.append(now)
        return len(sent) <= self.limit

    def in_window(self, merchant: str) -> int:
        """How many deliveries count against the merchant's limit right now."""
        return len(self._recent(merchant, self.clock()))

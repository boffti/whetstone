"""Misconception: the ledger is ours to extend. (What a fresh AI wrote from TASK.md alone: it
added refund_up_to here and called it from run, which finance's client does not have.)"""

from dataclasses import dataclass, field
from threading import Lock


@dataclass(frozen=True)
class Refund:
    order_id: str
    node_id: str
    cents: int


@dataclass
class Ledger:
    refunds: list[Refund] = field(default_factory=list)
    _lock: Lock = field(default_factory=Lock, repr=False, compare=False)
    _seen: int = field(default=0, repr=False, compare=False)
    _totals: dict = field(default_factory=dict, repr=False, compare=False)
    _nodes: set = field(default_factory=set, repr=False, compare=False)

    def _sync(self) -> None:
        # Indexes over `refunds`, rebuilt if rows were added behind our back.
        if self._seen != len(self.refunds):
            self._totals, self._nodes = {}, set()
            for r in self.refunds:
                self._totals[r.order_id] = self._totals.get(r.order_id, 0) + r.cents
                self._nodes.add((r.order_id, r.node_id))
            self._seen = len(self.refunds)

    def pay(self, order_id: str, node_id: str, cents: int) -> Refund:
        with self._lock:
            return self._pay(order_id, node_id, cents)

    def _pay(self, order_id: str, node_id: str, cents: int) -> Refund:
        self._sync()
        refund = Refund(order_id, node_id, cents)
        self.refunds.append(refund)
        self._seen += 1
        self._totals[order_id] = self._totals.get(order_id, 0) + cents
        self._nodes.add((order_id, node_id))
        return refund

    def paid(self, order_id: str) -> int:
        """Cents paid back on this order so far, by every flow."""
        with self._lock:
            self._sync()
            return self._totals.get(order_id, 0)

    def refund_up_to(self, order_id: str, node_id: str, cents: int, total_cents: int) -> int:
        """Pay `cents` for this node, once per order and never past `total_cents` in all.

        Returns the cents actually paid. Nothing is written when that is zero.
        """
        with self._lock:
            self._sync()
            if (order_id, node_id) in self._nodes:
                return 0
            cents = min(cents, total_cents - self._totals.get(order_id, 0))
            if cents <= 0:
                return 0
            self._pay(order_id, node_id, cents)
            return cents

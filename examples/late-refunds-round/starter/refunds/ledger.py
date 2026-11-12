"""A stand-in for finance's ledger client, for tests and local runs. The real client records every
refund paid, finance reconciles it each night, and it has these three members and nothing else."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Refund:
    order_id: str
    node_id: str
    cents: int


@dataclass
class Ledger:
    refunds: list[Refund] = field(default_factory=list)

    def pay(self, order_id: str, node_id: str, cents: int) -> Refund:
        refund = Refund(order_id, node_id, cents)
        self.refunds.append(refund)
        return refund

    def paid(self, order_id: str) -> int:
        """Cents paid back on this order so far, by every flow."""
        return sum(r.cents for r in self.refunds if r.order_id == order_id)

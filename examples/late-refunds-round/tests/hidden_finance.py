"""A ledger client for the hidden tests: hidden, so the learner's folder does not get it."""


class FinanceLedger:
    """Like finance's ledger client in production: pay, paid and refunds, and nothing else."""

    __slots__ = ("refunds",)

    def __init__(self):
        self.refunds = []

    def pay(self, order_id, node_id, cents):
        from refunds.ledger import Refund

        refund = Refund(order_id, node_id, cents)
        self.refunds.append(refund)
        return refund

    def paid(self, order_id):
        return sum(r.cents for r in self.refunds if r.order_id == order_id)

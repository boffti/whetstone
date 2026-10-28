"""The scheduled payment run: charge every payment that is due, and report what happened."""

from dataclasses import dataclass

from gateway import CardDeclined, GatewayTimeout


@dataclass(frozen=True)
class Payment:
    payment_id: str  # one per scheduled payment, e.g. "pay-0301-42"; a later run sees the same id
    customer_id: int
    amount_cents: int
    due: str  # ISO date, e.g. "2026-03-01"


class PaymentRunner:
    """The scheduler calls run() with the payments that are due. A "failed" payment goes into a later run."""

    def __init__(self, gateway, max_attempts: int = 3) -> None:
        self._gateway = gateway
        self._max_attempts = max_attempts

    def run(self, due: list[Payment]) -> dict[str, str]:
        """Charge each due payment. Return {payment_id: "paid" | "declined" | "failed"}."""
        return {payment.payment_id: self._collect(payment) for payment in due}

    def _collect(self, payment: Payment) -> str:
        for _ in range(self._max_attempts):
            try:
                self._gateway.charge(payment.customer_id, payment.amount_cents)
            except CardDeclined:
                return "declined"  # the issuer said no; asking again will not change that
            except GatewayTimeout:
                continue  # transient: try again
            return "paid"
        return "failed"  # no reply on any try; the scheduler puts it in a later run

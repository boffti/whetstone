"""The payment gateway as the runner sees it, and the in-memory fake the tests use. Read-only.

The real client has the same `charge` method and raises the same errors.
"""


class GatewayTimeout(Exception):
    """No reply from the gateway before the deadline."""


class CardDeclined(Exception):
    """The card issuer refused the charge. Asking again does not change the answer."""


class FakeGateway:
    """An in-memory gateway: no network, no clock.

    `faults` scripts what goes wrong, per customer: one entry for each charge request, in order.
    When a customer's script runs out, their requests go through.
      "lost-request": the request never arrives. No money moves, and the caller times out.
      "lost-ack":     the charge goes through, but the reply is lost, so the caller times out.
      "declined":     the issuer refuses the charge.
    """

    def __init__(self, faults: dict[int, list[str]] | None = None) -> None:
        self._faults = {customer: list(script) for customer, script in (faults or {}).items()}
        self._by_key: dict[str, str] = {}
        self.charges: list[tuple[str, int, int]] = []  # for tests: (charge id, customer id, cents) per charge that moved money
        self.requests = 0  # for tests: how many times charge() was called

    def charge(self, customer_id: int, amount_cents: int, idempotency_key: str | None = None) -> str:
        """Charge the customer and return the charge id.

        A request with an idempotency_key that the gateway has already charged moves no money:
        it returns the id of that earlier charge.
        """
        self.requests += 1
        script = self._faults.get(customer_id, [])
        fault = script.pop(0) if script else "ok"
        if fault == "lost-request":
            raise GatewayTimeout("no reply from the gateway")
        if fault == "declined":
            raise CardDeclined(f"customer {customer_id}: card declined")
        if idempotency_key is not None and idempotency_key in self._by_key:
            charge_id = self._by_key[idempotency_key]
        else:
            charge_id = f"ch_{len(self.charges) + 1}"
            self.charges.append((charge_id, customer_id, amount_cents))
            if idempotency_key is not None:
                self._by_key[idempotency_key] = charge_id
        if fault == "lost-ack":
            raise GatewayTimeout("no reply from the gateway")
        return charge_id

    def charged(self, customer_id: int) -> list[int]:
        """For tests: the amounts that moved for one customer, in order."""
        return [cents for _, customer, cents in self.charges if customer == customer_id]

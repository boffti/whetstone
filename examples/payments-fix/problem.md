## Task

A bug report from the billing team:

> **Customer 42 was charged twice on 2026-03-01.**
>
> The scheduled payment run on 2026-03-01 charged customer 42 twice for one 49.99 payment, about a second apart. The run report lists the payment once, as paid. The other customers in that run were charged once. Our logs show one timeout on the first charge request for customer 42.
>
> **Steps to reproduce.** `FakeGateway` in `gateway.py` can lose the gateway's reply to one request.
>
> ```python
> due = [
>     Payment("pay-0301-41", 41, 1999, "2026-03-01"),
>     Payment("pay-0301-42", 42, 4999, "2026-03-01"),
>     Payment("pay-0301-43", 43, 999, "2026-03-01"),
> ]
> gateway = FakeGateway(faults={42: ["lost-ack"]})   # customer 42's first reply is lost
> report = PaymentRunner(gateway).run(due)
> gateway.charged(42)
> ```
>
> **Expected:** `[4999]`, and `report["pay-0301-42"] == "paid"`.
>
> **Actual:** `[4999, 4999]`.

Fix `PaymentRunner` in `solution.py`. The rest of the run works, so keep the change small.

## API

```python
# solution.py
@dataclass(frozen=True)
class Payment:
    payment_id: str      # one per scheduled payment; a later run sees the same id
    customer_id: int
    amount_cents: int
    due: str             # ISO date

class PaymentRunner:
    def __init__(self, gateway, max_attempts: int = 3) -> None: ...
    def run(self, due: list[Payment]) -> dict[str, str]: ...   # {payment_id: "paid" | "declined" | "failed"}

# gateway.py (read-only, next to your code)
class GatewayTimeout(Exception): ...
class CardDeclined(Exception): ...

class FakeGateway:
    def __init__(self, faults: dict[int, list[str]] | None = None) -> None: ...
    def charge(self, customer_id: int, amount_cents: int, idempotency_key: str | None = None) -> str: ...
    charges: list[tuple[str, int, int]]                  # for tests
    requests: int                                        # for tests
    def charged(self, customer_id: int) -> list[int]: ...  # for tests
```

The runner calls only `charge`: the real gateway client has nothing else.

## Rules

- `run` returns one status for every due payment: `"paid"`, `"declined"` or `"failed"`.
- A paid payment moves money exactly once, whatever goes wrong on the way, and however many runs pick it up.
- Two payments are two charges, even for one customer, one amount and one day.
- A timeout gets another try, up to `max_attempts` tries in all. When no try gets a reply, the status is `"failed"`, and the scheduler puts the payment in a later run.
- A declined card gets no other try. Its status is `"declined"`.
- `run` never waits in real time. The scheduler spaces out the runs.

## Example

How the scheduler uses the runner:

```python
report = PaymentRunner(gateway).run(due_today)
# {"pay-0301-41": "paid", "pay-0301-42": "failed", "pay-0301-43": "declined"}
due_tomorrow += [p for p in due_today if report[p.payment_id] == "failed"]
```

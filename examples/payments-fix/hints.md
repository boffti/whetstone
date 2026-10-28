Customer 42's first request timed out. At that moment, what does the runner know about whether the money moved?

---

A timeout is an unknown outcome. Use the lesson's subgoals: **name the payment**, **keep the name stable**, and **let the gateway replay** the first result, so another try is safe.

---

Make `test_customer_42_is_charged_once_when_the_reply_is_lost` pass first. Read `charge` in `gateway.py`: how can it tell a new charge from a repeat? Then ask whether your answer still holds tomorrow, in a new process, for the same payment.

---

```python
def _collect(self, payment):
    key = ...  # the same on every try and in every run, and different for every payment
    for _ in range(self._max_attempts):
        try:
            self._gateway.charge(payment.customer_id, payment.amount_cents, ...)
        except CardDeclined:
            return "declined"
        except GatewayTimeout:
            continue
        return "paid"
    return "failed"
```

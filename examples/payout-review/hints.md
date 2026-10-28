This month three merchants called support: one was paid twice, one was never paid for a sale, and one waited all night because the job hung. Which line in `subject.py` could explain each call?

---

Use the lesson's subgoals: **replay it** on every call that moves money, **stall it** on every network call, and **walk the edges** of every window. Put each finding on the line where a docstring's promise breaks, not on the line that looks unusual.

---

Make `test_every_seeded_defect_is_found` pass. Trace one merchant through `run_payouts` three times: with a payment captured at exactly 00:00:00 UTC on `day`; with a gateway that accepts the connection and never replies; and with a transfer the gateway made whose response was lost, so the loop tries again.

---

```python
FINDINGS = [
    (..., "not-idempotent"),   # the line that decides what a retry sends
    (..., "missing-timeout"),  # the line that waits on the gateway
    (..., "wrong-boundary"),   # the line that decides which payments belong to `day`
]
```

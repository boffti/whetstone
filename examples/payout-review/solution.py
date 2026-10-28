"""The seeded defects in subject.py, and why a reviewer would block the pull request for each."""

FINDINGS = [
    # A fresh key on every attempt. When the gateway makes the transfer but the response is
    # lost, the retry is a new request, and so is a re-run after a crash: the merchant is paid
    # twice. The key must come from what is being paid, for example the merchant and the day.
    (50, "not-idempotent"),
    # requests has no default timeout. A gateway that accepts the connection and never answers
    # holds the whole batch: no merchant after this one is paid tonight, and nothing alerts.
    (52, "missing-timeout"),
    # `start <` drops a payment captured at exactly 00:00:00 UTC. The day before excludes it
    # too (`< end`), so no run ever pays it out. Each instant belongs in one day: start <= t < end.
    (69, "wrong-boundary"),
]

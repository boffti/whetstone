## The idea

A call over the network can fail in two places. The **request** can be lost on the way there: nothing happens. Or the work happens, and the **acknowledgement** (the reply) is lost on the way back. The caller sees the same thing both times: a **timeout**. A timeout is an **unknown outcome**, not a failure.

A retry is safe only when it is **idempotent**: doing it twice has the same effect as doing it once. The usual tool is an **idempotency key**, sent with the request. The server remembers each key it has done. For a repeat, it returns the first result and does not do the work again.

## Subgoals

1. **Treat a timeout as unknown**: the money may have moved.
2. **Name the payment**: derive the key from what makes this payment one payment.
3. **Keep the name stable**: the same key on every try and in every run.
4. **Let the gateway replay**: a repeat returns the first charge, and the payment is paid.

## In Python

A random key differs on every call. A derived key is the same in any process.

```python
import uuid

uuid.uuid4()                                   # random: different every time
uuid.uuid5(uuid.NAMESPACE_URL, "orders/881")   # derived: the same for "orders/881", always
```

## Misconceptions

- "Any unique key makes a retry safe." A key made fresh for each run is new to the gateway, so the next run charges again.
- "The customer and the day identify a payment." Then two payments for one customer on one day share a key, and one is never collected.
- "When the outcome is unknown, giving up is safe." The charge may have gone through or never arrived; either way, the books are wrong.

## Interview angle

Expect: "The gateway timed out. Do you retry?" Yes, with an idempotency key, because a timeout is not a failure. Then: How long does the server keep keys? What if a key comes back with a different amount? What if the server crashes between the charge and saving the key? A staff engineer also names the alternative: look the charge up before retrying.

## Tie-in to your work

Find a retry around a call that moves money or creates a record. If the reply is lost, what does the second try do? (Your AI ties this section to your own work, from your profile.)

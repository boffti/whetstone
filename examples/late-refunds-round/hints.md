Stage 1: an order 10 minutes early came out more than a thousand minutes late. Print what `minutes_late` returns for it. Which part of a `timedelta` is that number?

Stage 2: what names one refund, so that a second run can tell it was already paid? And where does the true total paid on an order live?

Stage 3: what should happen when the walk reaches a node it has already reached? Is it the same answer when it got there by another branch?

---

Stage 1: `timedelta.seconds` is only the seconds part, 0 to 86,399; days are kept apart, and a negative delta borrows a whole day. `total_seconds()` is the whole span.

Stage 2: an idempotency key. README.md says an order id and a node id together name one refund. The cap is cumulative: what this refund may pay is what is left of the order, which only the ledger knows.

Stage 3: validate the whole graph before running any of it, with a depth-first walk that tells "on the path I am walking now" apart from "finished earlier". Only the first is a loop.

---

Stage 1: `test_an_early_order_gets_nothing` fails in `refunds/clock.py`, and the fix is one word.

Stage 2: in `refunds/flow.py`, using only the ledger's `pay`, `paid` and `refunds`, before paying, look for a ledger row with this order id and this node id; then pay `min(the percent, total_cents - ledger.paid(order id))`, and pay nothing at all when that is zero.

Stage 3: `test_a_loop_raises` needs `run` to call a `check(flow)` first, and `test_a_deep_flow_runs` needs a loop instead of recursion, in both `check` and `run`.

---

```python
def check(flow):
    state, stack = {}, [(flow["start"], False)]
    while stack:
        node_id, leaving = stack.pop()
        if leaving:
            state[node_id] = ...          # finished: reaching it again is fine
            continue
        if state.get(node_id) == ...:     # still on the current path: a loop
            raise FlowError(...)
        ...                               # missing node? unknown type?
        state[node_id] = "open"
        stack.append((node_id, True))
        stack.extend(...)                 # the node's next nodes
```

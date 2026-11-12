# refunds

Runs refund flows on delivered orders. About 40,000 orders a day go through the late-delivery flow.

A flow is a small graph that ops writes in JSON (see `flows/`). A `check` node asks a question
about the order and goes to its `yes` or `no` node. A `refund` node pays back a percent of what
the customer paid, then goes to its `next` node. An `end` node stops.

## Layout

- `refunds/flow.py`: load a flow and run it on one order
- `refunds/clock.py`: time helpers
- `refunds/ledger.py`: a stand-in for finance's ledger, for tests and local runs
- `flows/`: the flows ops maintains

## Conventions

- Money is integer cents. A percent refund rounds down to the cent.
- Timestamps are ISO 8601 strings with a UTC offset. Compare them as aware datetimes.
- Node ids are unique across all flows, so an order id and a node id together name one refund.
- The ledger is the truth about what an order has been paid back, by every flow. Finance's
  reconciliation rejects rows of zero cents: never write one.
- The ledger is finance's, not ours. In production `run` gets their ledger client, which has
  `pay`, `paid` and `refunds` and nothing else, so flow code uses only those. `refunds/ledger.py`
  is a stand-in with the same three; keep it that way.
- A flow is valid or broken as a whole. It is broken when a node points at a node that does not
  exist, when a node has an unknown type, or when its nodes form a loop anywhere, even on a branch
  no order has taken yet. Two branches that meet again at one node are not a loop. Never run any
  part of a broken flow.

## Tests

    python -m pytest tests

You have joined the team that owns refund flows for a food delivery service. A flow is a small graph that ops writes in JSON: check nodes ask a question about an order, refund nodes pay back a percent of what the customer paid, and an end node stops. `refunds/flow.py` runs one flow on one order and pays through the ledger. About 40,000 orders a day go through the late-delivery flow.

This is an AI-allowed round: work in your folder with the AI tool you use at work. Read `README.md` and the code before you change anything; the team's conventions are there.

## Stage 1

Support escalated two tickets this morning:

> Customers whose orders arrived **early** are getting late-delivery refunds. And a customer whose order arrived a day late got nothing.

Find the cause and fix it. The promise allows 20 minutes: an order exactly 20 minutes late is on time.

## Stage 2

The orders service sends each delivery event at least once, so the same order can reach a flow twice, and support re-runs flows by hand. `flows/wrong_order.json` now runs when a customer got someone else's order: it pays everything back. Make refunds safe to repeat:

- A refund node pays an order at most once, however many times flows run.
- The refunds on one order never add up to more than its `total_cents`, across every flow. A refund that would go over pays only what is left.
- `run` returns the cents that run actually paid.

## Stage 3

Ops now builds flows in a visual editor, and last week two of them took a worker down: one had 3,000 check nodes in a row and crashed it, and one pointed its last node back at its first and ran until the worker was killed.

- `run` handles a flow of any depth. The tests use 50,000 nodes.
- A broken flow raises `FlowError` before `run` pays anything. README.md says what broken means.

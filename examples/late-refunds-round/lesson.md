## The idea

An AI-allowed round tests the judgment around the code, not the typing. Interviewers watch how you find your way in code you did not write, how you ask the AI for help, and whether you check what it gives you before you trust it. The code still has to be right: hidden tests decide each stage.

This round has three ideas in it, all common in payment code:

- **A duration is a whole.** `timedelta.seconds` is only the seconds part, from 0 to 86,399. A delta of minus ten minutes is "minus one day plus 85,800 seconds", so `.seconds` says 1,430 minutes late. `total_seconds()` is the whole span.
- **Idempotency needs a key, and a cap needs the ledger.** A refund that may run twice needs a name for "this refund" (here, order id and node id). A limit across flows has to read what was already paid, from the one place that knows.
- **Validate the whole graph before running any of it.** A loop on a branch this order never takes is still a broken flow, and finding it halfway through means you already paid.

## Subgoals

1. Read README.md and the code before you prompt. The conventions decide stage 2 and stage 3.
2. Reproduce each stage's failure yourself, so you know what "fixed" looks like.
3. Ask the AI for small, checkable pieces, and name the function, the symptom and the constraint.
4. Run the visible tests after every change you accept. Read each diff.

## Misconceptions

- "The AI's answer passed the visible tests, so it is done." The hidden tests check the conventions in README.md, which a prompt with TASK.md alone never mentions.
- "Already visited means a loop." Two branches that meet again reach a node twice without a loop. Only a node still on the current path closes a loop.
- "Dedupe by order id." The late flow pays two different nodes on one order in a single run.
- "Cap each refund at the order total." The cap is on everything paid so far, by every flow.
- "The ledger is ours to extend." In production `run` gets finance's client, with `pay`, `paid` and `refunds` only. A helper added to the stand-in passes every local test and breaks in production. Read the AI's diff for files it should not touch.

## Interview angle

Rounds like this run in stages: fix a bug, build a feature, then make it hold up at scale. Interviewers note whether you read before prompting, whether your prompts carry context, whether you catch a confident wrong answer, and whether you can explain every line you keep. Saying what you hand to the AI, and why, counts as much as the code.

## Tie-in to your work

Every system that pays or credits money has some version of stage 2: retries, re-runs and two flows touching one balance. When your AI writes that code at work, check the key and the cap first.

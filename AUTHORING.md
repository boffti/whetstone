# Authoring guide

This file is the contract for every question in Whetstone. AI agents follow it when they build questions for a learner (see AGENTS.md), and the optional in-app generator sends it to Claude word for word. `examples/memoize/` is a finished question that follows every rule here.

A good challenge teaches one concept by making the learner build it. The tests prove that the learner understood the hard part, not only the happy path.

## Folder layout

Questions are personal: they are written for one learner, from their profile. They live in the learner's git-ignored `my/` folder, never in the shared repo. A "module" is a track folder.

```
my/
  profile.md                       # who the learner is; read it before you write
  tracks/
    <module-id>/
      track.yaml                   # title, description, order
      <NN-slug>/                   # NN = two-digit position in the module
        challenge.yaml
        lesson.md                  # the reading
        problem.md                 # the task and the exact API
        hints.md                   # 3 or 4 hints, separated by lines with only ---
        starter.py                 # what the learner starts from
        solution.py                # the reference solution
        <support>.py               # optional read-only helpers (list them in challenge.yaml)
        tests/
          test_visible.py          # shown to the learner; run by "Run tests"
          test_hidden.py           # not shown; run by "Submit"
          conftest.py              # optional shared fixtures (for example, Redis)
```

The learner's code is saved as `solution.py` in a temporary folder, next to the support files and the `tests/` folder. Tests import from it: `from solution import Thing`.

## challenge.yaml

```yaml
title: Stop the cache stampede      # sentence case, under 40 characters
difficulty: medium                  # easy | medium | hard
minutes: 30                         # honest estimate for a strong engineer
tags: [concurrency, cache-stampede]
requires: []                        # [redis] if the tests need Redis
support: []                         # extra .py files shown read-only, e.g. [harness.py]
timeout: 60                         # optional; seconds before the run is stopped
summary: One sentence about what the learner builds.
```

## lesson.md

Write in Simplified Technical English most of the time: short sentences, active voice, one idea per sentence, common words. Use these sections, in this order:

1. `## The idea`: the concept in plain words, with the correct technical names in **bold** the first time.
2. `## Analogy`: one concrete everyday picture. Map each part of the picture to a part of the concept.
3. `## In Python`: the standard-library tools, with one short code block.
4. `## Common mistakes`: 3 or 4 bullets. Each bullet names a bug that a hidden test catches.
5. `## Interview angle`: what an interviewer asks next, and the trade-offs a staff engineer names.
6. `## Tie-in to your work`: one or two sentences that connect the concept to the learner's systems (see `profile.md`).

Length: 350 to 650 words. Do not paste the solution into the lesson.

## problem.md

Sections: `## Task`, `## API` (a code block with exact signatures), `## Rules` (bullets; each rule must be testable), `## Example`. Every rule in the problem must have a test. Every test must check a stated rule.

## hints.md

Three or four hints, separated by a line that contains only `---`. Hint 1 points the direction. The last hint is almost the answer but is not a full solution.

## starter.py

- It imports cleanly and has the full API (classes, methods, signatures), so tests can run.
- It is incomplete or subtly wrong, so **at least one test fails**. A naive version that "works for one thread" is often the best starter: the learner sees exactly why it breaks.
- It must not hang. If it would block forever, make it return or raise instead, so failures are readable.

## solution.py

Clean, idiomatic Python 3.12, standard library first. It passes every visible and hidden test, every time. Comments explain *why*, not *what*.

## Tests

The tests are the grader. They must be deterministic. Follow these rules:

- **Name tests as sentences.** The app shows `test_errors_are_shared_with_all_waiters` as "errors are shared with all waiters".
- **Assertion messages teach.** When a common mistake fails, say what to fix: `assert calls == 1, "A saved 0 must count as a hit. Use 'n in cache'."`
- **Visible tests** (2 to 4) check the core behavior. **Hidden tests** (5 to 8) check edge cases, errors, concurrency, and each "common mistake" in the lesson.
- **Time.** Inject a clock for anything with expiry or deadlines; never sleep for minutes. When you must measure real time (for example, "keys run in parallel"), use a margin of at least 2x between the correct and the wrong behavior.
- **Concurrency.** Start threads together with `threading.Barrier(n)`. Count calls with a lock-protected counter. Join every thread with a timeout. Collect exceptions in a list and assert on it in the main thread.
- **Make races visible.** Python's GIL hides many races. If a test must catch a missing lock, use a support helper that calls `time.sleep(0)` between the steps of an operation and detects overlap (for example, a `str` subclass key whose `__hash__` calls `time.sleep(0)`, so that every dict access becomes a chance to switch threads).
- **Never hang.** Every wait has a timeout. A correct solution finishes the whole suite in under 10 seconds.
- **External services.** Only Redis, through a `conftest.py` fixture that reads `REDIS_URL` and calls `pytest.skip` when Redis is down. Use a unique key prefix per test (`uuid4`) and delete the keys afterward. No other network access.
- **Forbidden shortcuts.** If the point is to build something yourself, enforce it: monkeypatch the forbidden function to raise, then `importlib.reload(solution)`.
- Hidden tests may import helpers from `test_visible.py`.

## Validate before you finish

```bash
bin/whetstone question check <module-id>/<NN-slug>
```

Validation passes only when every required file exists, the reference solution passes all tests, and the starter fails at least one. Run it three times to catch flaky timing.

## Build questions with your AI agent

Open this folder in Claude Code, Codex, Cursor or another coding agent and ask, for example, "Build the next Whetstone question for the rate-limiter module." The agent follows AGENTS.md. It runs `bin/whetstone question brief`, writes the files, and files them with `bin/whetstone question add`, which runs the same check as above.

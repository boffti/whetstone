# Authoring guide

This file is the contract for every question in Whetstone. AI agents follow it when they build questions for a learner (see AGENTS.md and the `whetstone-author` skill). The optional in-app generator sends it to Claude word for word. `examples/memoize/` (a build question) and `examples/retry-tests/` (a tests question) are finished questions that follow every rule here. [docs/PEDAGOGY.md](docs/PEDAGOGY.md) explains why the rules are what they are.

## What a good question does

- **It teaches one concept by making the learner do the hard part.** The tests prove they understood the hard part, not only the happy path.
- **It starts from the problem.** The learner is an experienced engineer. They learn more by trying first, so most lessons open after the first test run.
- **It trains what AI use wears down:** recalling ideas, reading and predicting code, debugging, judging generated code, and reasoning about failure. Building from a blank file is one type among several.
- **Its feedback names what went wrong in the learner's world**, for example "the second charge with the same key created a new payment". It never praises and never gives away the fix.

## Folder layout

Questions are personal: they are written for one learner, from their profile. They live in the learner's git-ignored `my/` folder, never in the shared repo. A module is a track folder.

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
        hints.md                   # exactly 4 hints, separated by lines with only ---
        starter.py                 # what the learner starts from
        solution.py                # the reference solution
        <support>.py               # read-only files the learner sees, e.g. subject.py (list them in challenge.yaml)
        mutants/                   # hidden: wrong versions of the solution, one per misconception
          01-<misconception>.py
        tests/
          test_visible.py          # shown to the learner; run by "Run tests"
          test_hidden.py           # not shown; run by "Submit"
          conftest.py              # optional shared fixtures (for example, Redis)
```

The learner's code is saved as `solution.py` in a temporary folder, next to the support files and the `tests/` folder. Tests import from it: `from solution import Thing`.

## challenge.yaml

```yaml
title: Stop the cache stampede      # sentence case, under 40 characters; name the scenario, not the technique
type: build                         # build | predict | fix | review | tests | design (see "Question types")
lesson: after-run                   # after-run: problem first, lesson opens after the first run; first: lesson first
difficulty: medium                  # easy | medium | hard
minutes: 30                         # honest estimate for a strong engineer
tags: [concurrency, cache-stampede]
requires: []                        # [redis] if the tests need Redis
support: []                         # read-only files shown to the learner, e.g. [subject.py]
variant_of: caching/02-ttl          # optional: this re-tests an earlier question on a new surface
timeout: 60                         # optional; seconds before the run is stopped
summary: One sentence about what the learner does.
```

- **Titles name the scenario** ("Throttle a webhook sender"), not the technique ("Token bucket"). A technique in the title gives away the approach.
- **`lesson: after-run`** is the default for `build` and `fix`. Use `lesson: first` for `predict` questions, and for a first contact with truly unfamiliar ideas.
- **`variant_of`** marks a question that re-tests the same idea as an earlier one, with a new surface (different domain, names, data). Always point at the original question, even for a variant of a variant. Variants are how spaced review works: `bin/whetstone progress` shows when each review is due.

## Question types

| Type | The learner | `starter.py` | Graded by |
|---|---|---|---|
| `build` | implements an API | the full API, incomplete or naive | visible and hidden tests on their implementation |
| `predict` | reads working code (`subject.py`) and predicts what it does on a scripted input | an `ANSWERS` dict with `...` values | hidden tests run `subject.py` and compare |
| `fix` | finds and fixes one realistic bug | a complete, plausible implementation with the bug | tests that fail on the bug and pass on the fix |
| `review` | reviews AI-written code (`subject.py`) with 2 or 3 seeded defects | an empty `FINDINGS` list | tests compare their (line, category) findings with the seeded defects |
| `tests` | writes the tests for working code (`subject.py`) | one weak happy-path test | their tests must pass on `subject.py`, and on Submit each hidden mutant must make one of them fail |
| `design` | writes a short design note, then code for the option they chose | the API, plus an empty design note | a check that the note is filled in, plus tests of the guarantee the note promises |

### build
The core type. The starter is often a naive version that "works for one thread", so the learner sees exactly why it breaks.

### predict
- Put the code under study in `subject.py` and list it in `support`. It must be correct, realistic and short (under 60 lines).
- `problem.md` gives the scripted input or interleaving and names each prediction, for example "tokens left after the burst". It does not explain what the code does.
- `starter.py`:
  ```python
  ANSWERS = {
      "tokens_after_burst": ...,   # int
      "allowed_at_t_1_5": ...,     # bool
  }
  ```
- `solution.py` holds the right values. The **hidden tests compute the expected values by running `subject.py`**, so the answers are never written into the tests.
- The visible test checks only the format: every key is present, and no value is `...`.
- Forbid the shortcut: a hidden test checks that `solution.py` does not import `subject`.
- Use 3 to 6 predictions. At least one targets a misconception, for example "read-then-write is atomic".

### fix
- `starter.py` is a complete implementation with **one** realistic bug, for example:
  - an atomicity or ordering violation;
  - a lost acknowledgement;
  - a retry that is not idempotent;
  - an off-by-one at a window boundary;
  - a missing timeout.
- `problem.md` is a bug report: the symptom, the steps to reproduce, and the expected and actual results. **Never name the cause.**
- A visible test reproduces the reported symptom. Hidden tests reject fixes that only hide the symptom, such as a sleep, or a special case for the reported input.
- Keep the bug small: the reference fix changes a few lines. `question add` reports the size.

### review
- Put plausible AI-written code in `subject.py`: clean style and good names, with 2 or 3 seeded defects of different categories.
- `problem.md` gives the categories to use, for example `race`, `not-idempotent`, `missing-timeout`, `wrong-boundary`, `resource-leak`, `unvalidated-input`. It asks for:
  ```python
  FINDINGS = [(17, "race"), (42, "not-idempotent")]   # (line in subject.py, category)
  ```
- Hidden tests pass when each seeded defect is found (line within ±2, right category) and there is at most one false positive. The visible test checks only the format.
- Every seeded defect is something an experienced reviewer would flag in a real pull request. No trick questions.

### tests
Practises what most learners now hand to AI: writing the tests.
- `subject.py` (listed in `support`) is correct code with a clear docstring contract. The learner reads it.
- `starter.py` holds one weak happy-path test, which catches no mutant.
- `solution.py` holds strong reference tests that pass on `subject.py` and catch every mutant.
- `mutants/` holds 3 to 5 buggy versions of `subject.py`, one per misconception. Whetstone builds the grading itself: Run checks that the learner's tests pass on `subject.py`, and Submit adds one result per mutant, labelled with its misconception, such as "catches the bug: backoff means waiting the same time between tries".
- No `tests/` folder is needed. See `examples/retry-tests/`.

### design
A system-level trade-off, decided and then built.
- `problem.md` names two or three options and the guarantee each gives, for example at-least-once against at-most-once delivery.
- `solution.py` opens with a design note that has four lines: `Options:`, `Trade-off:`, `Choice:` and `Failure mode:` (the one the learner accepts). Whetstone checks that the note is filled in. The reviewer and interviewer skills judge what it says.
- The code declares its choice, for example `GUARANTEE = "at-least-once"`. Hidden tests check the guarantee that was declared, and attack it with an adversary such as a crash between write and ack, duplicate delivery, or clock skew.

## mutants/

Every `build`, `fix`, `design` and `tests` question has 2 to 5 mutants. A mutant is a complete copy of the reference with **one** realistic bug that encodes a misconception from the lesson. Its docstring's first line names it:

```python
"""Misconception: a dict in the class body belongs to each object."""
```

- **The tests must catch every mutant.** `question add` runs the full test suite against each one, and refuses the question if any mutant passes ("survives"). A survivor means a hidden test is missing.
- One mutant per misconception in the lesson, so each misconception is proven to have a test.
- Keep the change small and realistic: a missing lock, a falsy check, an off-by-one window, a retry that is not idempotent. No syntax errors and no obviously absurd code.
- Mutants are never shown to the learner.

## The module recipe

A module has about 5 questions. `question brief` suggests the type for each position:

1. **predict**: read working code first.
2. **build**: the core version, problem first.
3. **build**: the next step up: concurrency, scale or failure. From here on, **mix in ideas from earlier modules without naming them**.
4. **fix**, **review** or **tests**: a realistic bug to fix, AI-written code to judge, or the missing tests to write.
5. **build** or **design**: an adversary arrives, such as a retry storm, clock skew, or a crash between write and ack. A design question has the learner choose the guarantee first. Hidden tests attack it.

After the core recipe, write variants (`variant_of`), and **one question that uses the idea in another domain or in the learner's own stack** (from `my/profile.md`). Adapt to the learner's progress:
- a clean solve (no hints, 3 runs or fewer) means skip ahead;
- an assisted solve (the last hint or the solution) means a variant of the same idea next.

## lesson.md

Write in Simplified Technical English most of the time: short sentences, active voice, one idea per sentence, common words. Use these sections, in this order:

1. `## The idea`: the concept in plain words, with the correct technical names in **bold** the first time.
2. `## Subgoals`: the 3 to 6 named steps of a correct solution, as a numbered list without code. For example: derive the key, reserve it atomically, execute, persist the result, replay on a duplicate. Hints reuse these names. In the first question of a module, add one short worked example under the list. The example solves a *different* problem with the same subgoals, so it doesn't give away the answer. From the third question on, list the subgoal names only.
3. `## In Python`: the standard-library tools, with one short code block. Never the solution.
4. `## Misconceptions`: 3 or 4 bullets. Each names a wrong belief that a hidden test targets, for example "a read followed by a write is atomic under the GIL".
5. `## Interview angle`: what an interviewer asks next, and the trade-offs a staff engineer names.
6. `## Tie-in to your work`: one or two sentences that connect the concept to the learner's systems (see `profile.md`).

Add an `## Analogy` section after "The idea" only if the learner's profile asks for analogies.

Length: 250 to 500 words.

## problem.md

Sections:
- `## Task`: the scenario.
- `## API`: a code block with exact signatures.
- `## Rules`: bullets; each rule must be testable.
- `## Example`.

For `predict`, `## Predict` replaces `## Rules`. For `review`, `## Categories` replaces it.

Every rule in the problem has a test, and every test checks a stated rule. **Do not restate the lesson**: the learner should recall it, not copy it.

## hints.md

Exactly four hints, separated by a line that contains only `---`. They are a ladder, and each rung gives a little more:

1. **A question** about the failing behavior. Example: "What does a second caller see while the first is still computing?"
2. **The concept or subgoal** behind it, by its lesson name.
3. **A concrete next step** tied to a named test. Example: "Make `test_errors_are_shared_with_all_waiters` pass first: store the exception, not only the value."
4. **A skeleton**: the structure of the solution with the key 1 to 3 lines left as `...`.

**No hint contains the full solution.** The reference solution is for after a solve or an explicit give-up.

## starter.py

- It imports cleanly and has the full API (classes, methods, signatures), so the tests can run.
- It supplies the boilerplate, so all effort goes into the target concept.
- It is incomplete or subtly wrong, so **at least one test fails**.
- It must not hang. If it would block forever, make it return or raise instead, so failures are readable.

## solution.py

Clean, idiomatic Python 3.12, standard library first. It passes every visible and hidden test, every time. Comments explain *why*, not *what*.

## Tests

The tests are the grader and the feedback. They must be deterministic. Follow these rules:

- **Name tests as scenarios.** The app shows `test_second_charge_with_same_key_returns_first_result` as "second charge with same key returns first result".
- **Assertion messages name the misconception and a next step, never the fix code.** Example: `assert calls == 1, "A saved 0 must count as a hit. How do you tell 'missing' from 'falsy'?"`
- **Visible tests** (2 to 4) check the core behavior. **Hidden tests** (5 to 8) check edge cases, errors, failure modes and concurrency. Every misconception in the lesson has a hidden test.
- **Time.** Inject a clock for anything with expiry or deadlines; never sleep for minutes. When you must measure real time (for example, "keys run in parallel"), use a margin of at least 2x between correct and wrong behavior.
- **Concurrency: force the ordering, don't hope for it.** A test that passes by luck teaches the wrong lesson. In order of preference:
  1. **Hooks.** The API takes an injected clock, a `step` callback or a fault point. The test uses `threading.Event` to stop one thread between two steps and run the other in the gap.
  2. **A race amplifier**, when the API has no hook point. Use a support helper that calls `time.sleep(0)` between the steps of an operation and detects overlap. For example, a `str` subclass key whose `__hash__` calls `time.sleep(0)`, so every dict access becomes a chance to switch threads.

  In both cases:
  - start threads together with `threading.Barrier(n)`;
  - count calls with a lock-protected counter;
  - join every thread with a timeout;
  - collect exceptions in a list and assert on it in the main thread.
- **Never hang.** Every wait has a timeout. A correct solution finishes the whole suite in under 10 seconds.
- **External services.** Only Redis, through a `conftest.py` fixture that reads `REDIS_URL` and calls `pytest.skip` when Redis is down. Use a unique key prefix per test (`uuid4`) and delete the keys afterward. No other network access.
- **Forbidden shortcuts.** If the point is to build something yourself, enforce it: monkeypatch the forbidden function to raise, then `importlib.reload(solution)`.
- Hidden tests may import helpers from `test_visible.py`.

## Before you file it

Check every item:
- [ ] The title names a scenario, not a technique.
- [ ] `type` and `lesson` are set. `variant_of` is set if this is a variant.
- [ ] The problem does not restate the lesson.
- [ ] Hints climb the four rungs, use the lesson's subgoal names, and contain no full solution.
- [ ] Each misconception in the lesson has a hidden test and a mutant in `mutants/` that the tests catch, and each failure message names a scenario.
- [ ] Concurrency tests force the ordering (hooks first).
- [ ] The question connects to the learner's profile: their stack, their goal, or what they hand off to AI at work.

## Validate

```bash
bin/whetstone question add my/.staging/<slug> --module <module-id>   # files a new question
bin/whetstone question check <module-id>/<NN-slug>                   # re-checks a filed one
```

A question passes when:
- every required file exists;
- the fields are valid;
- the reference solution passes all tests;
- the starter fails at least one.

`question add` also enforces the current format: exactly four hints, and 2 or more mutants that the tests all catch. `question check` only reports these gaps in older questions. Run `question check` three times to catch flaky timing.

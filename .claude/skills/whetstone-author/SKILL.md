---
name: whetstone-author
description: Build the next Whetstone question for a module, a variant for spaced review, or the first question of every unbuilt module in a path. Use when the learner asks to "build the next question for X", "fill in my path", "make a variant", or picks an option the curator offered.
---

# Author: build a question

You write one question at a time. `bin/whetstone` checks it and files it. **AUTHORING.md is the contract; follow it exactly.** `docs/PEDAGOGY.md` explains why.

## Steps

1. Run `bin/whetstone question brief <module>`. It gives:
   - the topic;
   - what already exists, with types;
   - real interview reports;
   - the **suggested question type** for this position in the module.
2. Read `my/profile.md` and `bin/whetstone progress --json`. Adjust the plan to the learner:
   - **Clean solves** (no hints, 3 runs or fewer): skip a scaffold step or go harder.
   - **Assisted solves or many runs:** stay on the concept, and target the misconception they hit.
   - **A variant for review** (the curator chose one): same idea, new surface. Use a new domain, new names and new data. Set `variant_of` to the *original* question's key.
   - **Their stack and what they hand off to AI at work:** use these for the scenario and the tie-in.
3. Choose the type: **build**, **predict**, **fix**, **review**, **tests**, **design** or **whiteboard**. A `design` request from the app always means **whiteboard**: run the brief with `--type whiteboard`. Take the brief's suggestion unless the progress gives a reason not to, and say the reason.
4. Run `bin/whetstone question new <module> <slug>`. Write every file in `my/.staging/<slug>/`.
   - For **predict** and **review**, the code to read goes in `subject.py`, listed in `support`.
   - Copy the quality of `examples/memoize/` (build) or `examples/retry-tests/` (tests).
5. Go through the checklist below. Then run `bin/whetstone question add my/.staging/<slug> --module <module>`. Fix every problem it prints and run it again until it says "Added".
6. Run `bin/whetstone question check <key>` twice more to catch flaky timing.
7. Give the learner the link it printed, and one line on what the question practices. Never describe the solution.

## Checklist before `question add`

- [ ] The title names a scenario, not the technique.
- [ ] `type` and `lesson` are set (`after-run` for build and fix). `variant_of` is set for a variant.
- [ ] The problem does not restate the lesson. The lesson lists named subgoals, and the hints reuse those names.
- [ ] Exactly 4 hints: a question, the concept, a next step tied to a named test, a skeleton with `...`. No full solution.
- [ ] Every misconception in the lesson has a hidden test **and a mutant** in `mutants/` (a wrong version of the reference that encodes it). `question add` refuses the question if any mutant passes every test. Test names are scenarios. Failure messages name the misconception and ask a question; they never give the fix code.
- [ ] Concurrency tests force the ordering with hooks (or the race amplifier). Nothing relies on luck or long sleeps.
- [ ] From question 3 of a module on, an idea from an earlier module appears without being named.
- [ ] The tie-in uses the learner's real stack from the profile.

## A system design question (whiteboard)

1. `bin/whetstone question brief <module> --type whiteboard`, then `bin/whetstone question new <module> <slug> --type whiteboard`.
2. Base the prompt on the system design reports in the brief. Set real scale numbers in `problem.md`; leave the approach out.
3. Write `solution.md` as the design a staff engineer would give: every section filled in, a Mermaid flowchart in High-level design, and the estimate arithmetic shown.
4. Write `rubric.yaml`: 5 to 10 points, 3 or more `must: true`. One point per misconception in the lesson. `look_for` says what evidence in the learner's text earns the point.
5. Copy the quality of `examples/short-links-whiteboard/`. Then file it with `question add` as usual.

## Filling a module or a path

- **A module:** repeat the steps 3 to 5 times, following the recipe (predict, build, build, then fix, review or tests, then build or design with an adversary).
- **A path:** run `bin/whetstone path show <path>` and build the first question of each module marked "not built".

## Never

- Never edit the learner's existing questions, drafts or `my/whetstone.db`.
- Never copy anything from `my/` into `content/`, `examples/` or a commit.

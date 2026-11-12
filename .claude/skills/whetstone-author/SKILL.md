---
name: whetstone-author
description: Build the next Whetstone question for a module, a variant for spaced review, or the first question of every unbuilt module in a path. Use when the learner asks to "build the next question for X", "fill in my path", "make a variant", or picks an option the curator offered.
---

# Author: build a question

You write one question at a time. `bin/whetstone` checks it and files it. **AUTHORING.md is the contract; follow it exactly.** `docs/PEDAGOGY.md` explains why.

## Steps

1. Run `bin/whetstone question brief <module>`, adding `--for <framing>` when the request has one. It gives:
   - the topic;
   - what already exists, with types;
   - real interview reports;
   - the **suggested question type** for this position in the module.
2. Read `my/profile.md` and `bin/whetstone progress --json`. Adjust the plan to the learner:
   - **Clean solves** (no hints, 3 runs or fewer): skip a scaffold step or go harder.
   - **Assisted solves or many runs:** stay on the concept, and target the misconception they hit.
   - **Their ratings** (`rating`, one tap after Submit; the brief shows them too): after `too-hard` add scaffolding and stay on the concept; after `too-easy` skip a step; after `artificial` set the next scenario in their real work from the profile.
   - **A variant for review** (the curator chose one): same idea, new surface. Use a new domain, new names and new data. Set `variant_of` to the *original* question's key.
   - **Prepare again for…** (a `variant` request with a `framing`): the learner wants a question they already have, set in another world. Keep the skill and the rubric's must-haves; reframe the scenario, scale and follow-ups per the brief's Framing. Set `variant_of` to the original and `framing:` to the new one. The original stays, with its progress.
   - **Their stack and what they hand off to AI at work:** use these for the scenario and the tie-in.
3. Choose the type: **build**, **predict**, **fix**, **review**, **tests**, **design**, **whiteboard**, **project** (an AI-allowed round) or **terminal** (a command-line question; the brief picks it for modules with `format: terminal`). A `design` request from the app always means **whiteboard**: run the brief with `--type whiteboard`. Take the brief's suggestion unless the progress gives a reason not to, and say the reason. When the brief says the learner's AI handles tests, code review or reading code, pull a **tests** or **review** question forward to position 2 or 3; do not wait for position 4. Those skills fade fastest.
4. Run `bin/whetstone question new <module> <slug> --type <type>`. It scaffolds a toy of that type that already passes `question add`: **predict** and **review** get `subject.py` and an `ANSWERS` dict or `FINDINGS` list; **tests** gets `subject.py`, one weak test and no `tests/` folder. Replace every file in `my/.staging/<slug>/`, keeping that shape.
   - Copy the quality of `examples/memoize/` (build) or `examples/retry-tests/` (tests).
5. Go through the checklist below. Then ask for a second read before you file: start a fresh subagent that has not seen your draft, give it AUTHORING.md, `my/profile.md` and the folder `my/.staging/<slug>/`, and ask only four things: is the scenario a real problem from the reports in `grounded_in`, is it set in this learner's world, does the problem or a test name give the technique away, and could a strong engineer finish in the stated minutes. Take at most three findings, fix them, and only then run `bin/whetstone question add my/.staging/<slug> --module <module>`. Fix every problem it prints and run it again until it says "Added".
6. Run `bin/whetstone question check <key>` twice more to catch flaky timing.
7. Give the learner the link it printed, and one line on what the question practices. Never describe the solution.

## Checklist before `question add`

- [ ] The title names a scenario, not the technique.
- [ ] The scenario follows the brief's **Framing**: the learner's own work, the company they are preparing for (their product, scale and follow-ups; never the learner's employer), or the domain. `framing:` in challenge.yaml says which. For a review variant with no framing given, pick a different world from the original: same idea, new surface.
- [ ] `grounded_in` lists the Source links of the reports the scenario comes from. Reports marked "title only" in the brief give breadth, not the anchor.
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

## An AI-allowed round (project)

When the learner prepares for a company whose reports include AI-allowed rounds (the brief says so), or asks to practice working with their AI:

1. `bin/whetstone question brief <module> --type project`, then `bin/whetstone question new <module> <slug> --type project`. Follow the project section of AUTHORING.md.
2. Write a small codebase in `starter/` (5 to 10 files) with a `README.md` holding the team's conventions, and 2 to 4 stages in `problem.md`: a bug report, a feature, then scale or failure.
3. Check it with a fresh AI before filing. Copy `starter/`, the visible tests and the full `problem.md` (as `TASK.md`) to an empty folder outside Whetstone. Start a subagent there, ideally on a smaller model, told only to solve TASK.md in that folder. Run the hidden tests on what it wrote. When they catch it, file its answer as `mutants/01-naive-ai/`. When they all pass, put what decides a stage in the conventions or the data and try once more; a careful AI may still pass, and the review and the ownership check cover that.
4. A variant of a project question for spaced review is a solo `build` or `fix` on the same idea, without the AI (docs/PEDAGOGY.md, rule 13).

## A terminal question

For a command-line module (the brief says terminal), or when the learner asks to practice a CLI:

1. `bin/whetstone question new <module> <slug> --type terminal --tool <pack>`, with the packs from `content/tools.yaml` it needs. Follow the terminal section of AUTHORING.md and copy the quality of `examples/git-lost-commits/`.
2. Write `scenario.py` first: the visible variant becomes the learner's `sandbox/`, and each hidden variant is named for the shortcut it defeats. Return the expected facts from `build()`; never copy them by hand.
3. Write one mutant per shortcut the lesson warns about. A script that hardcodes anything from `sandbox/` must fail a hidden test.
4. A variant for spaced review is another terminal question on a new scenario, with the same tools.

## Filling a module or a path

- **A module:** repeat the steps 3 to 5 times, following the recipe (predict, build, build, then fix, review or tests, then build or design with an adversary).
- **A path:** run `bin/whetstone path show <path>` and build the first question of each module marked "not built".

## Never

- Never edit the learner's existing questions, drafts or `my/whetstone.db`.
- Never copy anything from `my/` into `content/`, `examples/` or a commit.

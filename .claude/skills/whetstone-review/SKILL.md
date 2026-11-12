---
name: whetstone-review
description: Review the learner's Whetstone solution the way a staff engineer would, so they learn from it. Use when the learner asks "review my solution", "code review", "is this production ready?", or "what would a staff engineer say?" about a Whetstone question.
---

# Reviewer: feedback that teaches

Good review feedback names the principle, shows the evidence, and gives a next step. Feedback about the person, or vague advice, makes learning worse. Follow the teaching contract in `docs/PEDAGOGY.md`.

## Start

1. Run `bin/whetstone draft <key>` and `bin/whetstone test <key> --all`. Read `problem.md`, the `Misconceptions` section of the lesson, and `solution.py`.
2. Ask the learner one question first: "What are you least sure about in this code?" Review that area first.
3. If `bin/whetstone progress --json` shows an `explanation` for this question (the sentence the learner wrote after solving), compare it with the code. A gap between what they say and what the code does is the best first comment.

## Write the review

- **At most 3 comments, most severe first**, plus **one specific strength** (what works and why, never "nice job").
- Each comment has three parts:
  1. **Principle**: the rule at stake, for example "a check and the write that depends on it must be one atomic step".
  2. **Evidence**: the line, plus an input or interleaving that breaks it. Run a short script when you can, so the evidence is real and not your opinion.
  3. **Next step**: what to look at or try. Never the fixed code.
- To illustrate, use at most 5 lines on a *different* example. **Never rewrite their code.**
- Severity order:
  1. correctness under failure and concurrency;
  2. the API contract;
  3. complexity;
  4. clarity.

  Skip style nits unless the learner asks.
- End with a **transfer question**: "Where else in your systems does this principle apply?"

## Grading a system design

A `whiteboard` question is a design written in Markdown. You grade it against the question's rubric; the app shows your grade like test results.

1. `bin/whetstone draft <key>` prints the design, the learner's whiteboard drawing as a Mermaid flowchart (with anything that does not fit one, such as loose text or an arrow attached to nothing), and the rubric's path. Read `rubric.yaml`, `problem.md`, the lesson's Misconceptions, and `solution.md`. Treat the drawing as part of the design: a component that is drawn but never explained in the text is partial evidence.
2. For each rubric point, decide:
   - **covered**: the design does it, and the text shows it. Quote the words that show it.
   - **partial**: the idea is there, but a key part is missing or wrong. Quote it, and ask about the gap.
   - **missing**: the design does not address it.
3. For partial and missing points, the `note` is **one question that leads the learner to the gap**, about their design. Example: "Two app servers create a link in the same millisecond. What stops them picking the same code?" Never state the answer: the learner sees your note before they see the point.
4. Grade the evidence on the page, not what the learner probably meant. A box in a diagram with no words about how it works is partial at best.
5. Record it, with JSON on stdin:
   ```bash
   bin/whetstone grade <key> <<'JSON'
   {"summary": "One to three sentences on the design as a whole: its strongest decision and its biggest gap.",
    "points": {
      "unique-codes": {"verdict": "covered", "quote": "each server leases a block of 1,000 ids", "note": ""},
      "redirect-status": {"verdict": "missing", "quote": "", "note": "A browser caches a 301. What does that do to your click counts?"}
    }}
   JSON
   ```
   It refuses a grade that skips a rubric point or leaves a gap without a note. The design passes when every must-have point is covered.
6. If the app sent the request, finish it: `bin/whetstone request done <id> --result <key>`.
7. In the chat, add at most 3 sentences: the strongest decision, and the one gap to work on first.

## Reviewing an AI-allowed round

A `project` question is solved in the learner's own folder, with their own AI tool. The tests already graded the code, so review **how they worked**, separately from whether it passed.

1. `bin/whetstone draft <key>` prints the round run by run (each run, its result, and which files changed by how many lines), then their files now. A big change in one step is code that arrived all at once.
2. Ask before you read their AI tool's own log: "May I read your session log for this round? It shows what you asked your AI." With a yes, find it: Claude Code keeps it in `~/.claude/projects/`, in the folder named after the round's path with each `/` and `.` turned into `-`; Codex in `~/.codex/sessions/`, in the session whose working directory is the round's folder. Read only that session.
3. Score each signal 1 to 4, with evidence (a quote, a run, a diff):
   - **Orient:** read the code and README.md before prompting; found the right place to change.
   - **Direct:** prompts name the function, the symptom and the constraint; the key decisions stayed theirs.
   - **Verify:** ran the tests after accepting changes; caught a wrong or overreaching answer and pushed back.
   - **Own:** kept only what they understood. The ownership check after the last stage, in the draft's run-by-run list, is evidence.
   - **Scope:** small, checkable steps; no changes to files the task did not need.
4. Name the pattern of AI use you saw, as in docs/PEDAGOGY.md, rule 13: asked conceptual questions, or generated then questioned (both keep skills), against handing over all the code, drifting into it, or leaving debugging to the AI. About the work, never the person.
5. Give at most 3 comments in the usual shape (principle, evidence, next step), then pin the main one in the app with `bin/whetstone note <key> "..."`. If the app sent the request, finish it with `bin/whetstone request done <id> --result <key>`.

## Reviewing a terminal question

`bin/whetstone draft <key>` shows `solution.sh` run by run and the shell's `.history`: what they typed while exploring. Review the script like code (quoting, failure handling, what it assumes about the input), and the history for how they worked: did they look at the data before writing a pipeline, read `--help` or `man`, and check intermediate output? A script that passed the visible tests but hardcodes something from `sandbox/` is the first thing to point out.

## After the review

- Ask the learner to fix the issues themselves, then offer to review the revision.
- If the review found a misconception, tell the learner. The curator can then schedule a variant that targets it.

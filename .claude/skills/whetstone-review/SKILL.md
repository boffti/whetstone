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

1. `bin/whetstone draft <key>` prints the design and the rubric's path. Read `rubric.yaml`, `problem.md`, the lesson's Misconceptions, and `solution.md`.
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

## After the review

- Ask the learner to fix the issues themselves, then offer to review the revision.
- If the review found a misconception, tell the learner. The curator can then schedule a variant that targets it.

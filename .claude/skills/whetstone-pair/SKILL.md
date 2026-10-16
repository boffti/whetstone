---
name: whetstone-pair
description: Pair with the learner live while they solve a Whetstone question in the app, as a quiet reviewer, a coach or an interviewer. Watch their activity with `bin/whetstone watch` and reply in the app with `bin/whetstone note`. Use when the learner says "pair with me", "watch me solve this", "be my interviewer while I code", or "keep an eye on my session".
---

# Pair: a reviewer at the learner's shoulder

You watch what the learner does in the app and speak at the right moments, like a good human pair. You never type for them. Follow the teaching contract in `docs/PEDAGOGY.md`. The tutor's help ladder and the interviewer's rubric apply here too.

## Start watching

1. Run `bin/whetstone watch` as a **background** process whose output wakes you:
   - **Claude Code:** use the Monitor tool on `bin/whetstone watch`.
   - **Without background monitoring:** run `bin/whetstone watch --for 120` whenever the learner says "check", and react to what it printed.

2. Each line is a JSON event:

   | `event` | Meaning |
   |---|---|
   | `watching` | The stream started. |
   | `opened` | The learner opened a question. |
   | `paused` | They stopped typing for 20 s. It includes `editing_seconds` and `lines`. |
   | `ran` | A test run finished. It includes `mode` (run or submit), `status`, `passed`, `total`, `failing` and `solved`. |
   | `hint` | They opened a hint. It includes `rung` and `of`. |
   | `solution` | They opened the solution. It includes `gave_up`. |
   | `reset` | They reset the code to the starter. |
   | `idle` | Nothing happened for 10 minutes. |
   | `mode` | They changed the pair mode. |

   Every line carries `pair`, the mode the learner chose in the app: `off`, `quiet`, `coach` or `interviewer`.

3. To see the code, run `bin/whetstone draft <question>`. To see test results without recording a run, run `bin/whetstone test <question>`. Read the question's `problem.md`, `hints.md` and `solution.py` once, so your remarks match the tests and the reference.

## A system design question

When the question's type is `whiteboard`, the learner is writing a design, not code. `ran` events are section checks; a `reviewed` event means a grade was recorded.
- `bin/whetstone draft <question>` shows the design and the whiteboard drawing as Mermaid. A `paused` event with `shapes` means the learner was drawing. Read `rubric.yaml` so your questions point at what matters, but never quote it.
- Pin a note to the line of the section you are asking about. Ask as an interviewer would: "Where does the 50,000 requests per second in Estimates go in your High-level design?", "What happens to a payment in flight when this region fails?"
- In `interviewer` mode, push on numbers, bottlenecks and failure modes, one question per pause. In `quiet` mode, speak only when a section has stayed empty after the learner moved on.

## When to speak

| `pair` | Speak when | Stay quiet when |
|---|---|---|
| `off` | Never. Stop watching and say so in one line. | Always |
| `quiet` (default) | They are stuck: the same test fails 3 runs in a row, an `idle` event, or the last hint opened. Also after a solve, for a short debrief. | They are making progress: more tests pass, or they are typing |
| `coach` | All of `quiet`, plus once after each `ran`: one question about the result, and once on a `paused` event if the draft has a real problem | Twice in a row without the learner doing anything in between |
| `interviewer` | At `opened`: ask them to restate the problem and the edge cases. On the first `paused` with code: ask for the approach and its complexity. Before they Submit: ask for two failure modes. After the solve: score with the rubric in the `whetstone-interview` skill. | While they are mid-thought (typing) |

## How to speak

- **In the app:** `bin/whetstone note <question> "<one idea>" --line <N>`. The note appears over their editor, with a marker in the margin at line N. Use a line whenever your point is about specific code.
- **One idea per note, under 40 words, phrased as a question or an observation.** Good: "What happens on line 14 if two threads both see `n not in cache`?" Bad: "You need a lock around lines 14-18; use `with self._lock:`".
- **Never paste code that fixes their problem. Never name the exact bug early.** Climb the help ladder from the tutor skill: their hypothesis, then the concept, the region, the next app hint, an analogous example, and the reference only on a plain request.
- **No praise, and nothing about the person.** After a solve: name the principle they used, plus one thing to compare with the reference.
- You can also reply in the chat. Use notes for remarks about their code, and chat for longer discussion.

## Stop

Stop the watcher when the learner says stop, sets the pair mode to `off`, or closes the session. Then close with three lines: the highest help rung you used, the misconception you saw, and the next step (usually a variant via the `whetstone-curate` skill).

# How Whetstone teaches

This file explains *why* Whetstone questions and agents work the way they do. AUTHORING.md and the agent skills turn these rules into steps. Read this file when you change those rules.

The learner is an experienced engineer who wants to stay sharp. Often their AI writes most of their work code. So Whetstone trains what that habit wears down: recalling ideas, reading and predicting code, debugging, judging generated code, and reasoning about failure.

**About the evidence.** Most studies below are of students, not senior engineers. Where we extrapolate, we say so. Strength: *strong* means meta-analyses or many trials, *moderate* means a few trials or large field data, *weak* means small, observational or vendor-reported. Sources were gathered in October 2026.

## The rules, in order of impact

### 1. Problem first, not lesson first
Experts learn less from worked examples and long explanations than novices do; for experts, solving beats studying (the *expertise reversal effect*). Trying a problem before instruction helps conceptual understanding, though not procedural fluency (*productive failure*).
- Strength: strong for expertise reversal; moderate for productive failure.
- In Whetstone: conceptual questions open on the problem. The lesson unlocks after the first test run. A worked example appears only as the last hint.
- Sources: [Kalyuga et al. 2003](https://doi.org/10.1207/S15326985EP3801_4), [Sinha & Kapur 2021](https://doi.org/10.3102/00346543211019105)

### 2. Practice what AI use skips
In a randomized trial, developers who learned a library with an AI assistant scored 17% lower on a later quiz, with the biggest gap in debugging. Those who asked conceptual questions, or read and questioned the generated code, kept their scores. Unrestricted GPT-4 raised practice scores but cut later exam scores; a tutor with guardrails avoided the harm.
- Strength: moderate.
- In Whetstone: every module mixes question types (see the menu below): predict, fix, review AI code, write the missing test, design and break. Building from a blank file is one type among several.
- Sources: [Shen & Tamkin 2026](https://www.anthropic.com/research/AI-assistance-coding-skills), [Bastani et al. 2025](https://doi.org/10.1073/pnas.2422633122)

### 3. Space it out, and re-solve variants
Recall spread over time beats massed practice (g≈0.74 for spaced recall). Procedural skill loses about half its gain in months without use. A simple even schedule works as well as an expanding one.
- Strength: strong.
- In Whetstone: after a solve, schedule a *variant* (same idea, new surface) at about 3 days, 3 weeks, 3 months, 6 months, then yearly. A session puts due reviews before new work. A clean review lengthens the gap; a failed one shortens it to 2 days.
- Sources: [Cepeda et al. 2008](https://doi.org/10.1111/j.1467-9280.2008.02209.x), [Latimier et al. 2021](https://doi.org/10.1007/s10648-020-09572-8), [skill decay meta-analysis 2025](https://doi.org/10.1037/bul0000481)

### 4. Mastery means clean and lasting
A first checkmark is not mastery. Mastery learning with correction loops raises achievement.
- Strength: moderate.
- In Whetstone: a question is *mastered* when the hidden tests pass with no bottom-out hint and no viewed solution, and a spaced variant also passes when it comes due; a variant solved early does not count. A solve after the last hint or the solution is *assisted*, and it queues a variant.
- Source: [Kulik et al. 1990](https://doi.org/10.3102/00346543060002265)

### 5. A gated hint ladder
Next-step hints help now, but help later only with self-explanation. Learners misuse on-demand help. Early answer giveaways are the main way AI tutors harm learning.
- Strength: moderate.
- In Whetstone, hints.md has four fixed rungs:
  1. a question about the failing behavior;
  2. the concept or subgoal behind it;
  3. a concrete next step tied to a named test;
  4. a skeleton with the key lines blank.

  The next hint unlocks only after a new test run. The solution shows only after a solve or an explicit give-up.
- Sources: [Marwan et al. 2019](https://doi.org/10.1145/3291279.3339420), [Aleven et al. 2016](https://doi.org/10.1007/s40593-015-0089-1)

### 6. Mix topics from question 3 on
Mixing problem types, so the learner must choose the approach, beats practicing one type in a block. It helps most when types are easy to confuse. Learners rate it as less effective even when it works better.
- Strength: moderate.
- In Whetstone: questions 1–2 of a module stay on one idea. From question 3, reuse earlier modules' ideas without naming them. Title questions by scenario ("Throttle a webhook sender"), not by technique ("Token bucket"). Add pairs that look alike but need different solutions.
- Source: [Brunmair & Richter 2019](https://doi.org/10.1037/bul0000209)

### 7. Feedback on the work, never the person
Feedback helps on average (d≈0.48). Over a third of feedback interventions made things worse, mostly feedback aimed at the person, such as praise.
- Strength: strong.
- In Whetstone: a failing test names the scenario ("second charge with the same key created a new payment"). A hidden failure reports its category, not the test body. No scores, points or "great job".
- Sources: [Wisniewski et al. 2020](https://doi.org/10.3389/fpsyg.2019.03087), [Kluger & DeNisi 1996](https://doi.org/10.1037/0033-2909.119.2.254)

### 8. Predict, then explain
Prompted self-explanation improves learning (g≈0.55). Overconfidence makes people stop practicing too early. Confident errors that get corrected are remembered well.
- Strength: moderate to strong.
- In Whetstone: before a run, the learner predicts which tests pass. After a solve, they answer one question: "Why does your code handle *this* hidden case?" The app tracks prediction accuracy over time.
- Sources: [Bisra et al. 2018](https://doi.org/10.1007/s10648-018-9434-x), [Deslauriers et al. 2019](https://doi.org/10.1073/pnas.1821936116)

### 9. Read before you write
The ability to trace and explain code predicts the ability to write it. Predict–Run–Investigate–Modify–Make (PRIMM) beat normal lessons in a multi-school study.
- Strength: moderate; novice studies.
- In Whetstone: a module goes from reading given code, to changing it, to building from blank (Use → Modify → Create).
- Sources: [Lister et al. 2008](https://doi.org/10.1145/1404520.1404531), [Sentance et al. 2019](https://doi.org/10.1080/08993408.2019.1608781)

### 10. Make concurrency deterministic, and target misconceptions
Non-determinism lets wrong programs look correct, so a lucky pass reinforces the misconception. About 92% of real concurrency bugs appear when one ordering of four or fewer memory accesses is forced.
- Strength: moderate.
- In Whetstone: concurrency tests force interleavings through hooks (an injected clock, step hooks, fault points). They don't rely on threads and luck. Each hidden test names the misconception it targets, for example "read-then-write is atomic", "one passing run proves it", "clocks agree", "an ack means durable".
- Sources: [Strömbäck et al. 2021](https://doi.org/10.15388/infedu.2021.29), [DSLabs 2019](https://homes.cs.washington.edu/~mernst/pubs/dslabs-eurosys2019.pdf)

### 11. Transfer needs comparison and variety
Far transfer is rare. Comparing cases to draw out the shared principle, and varied practice, improve it.
- Strength: moderate.
- In Whetstone: each module has one question that uses the idea in another domain, and one in the learner's own stack (from my/profile.md). After two related solves, ask what principle they share, then state it.
- Sources: [Alfieri et al. 2013](https://doi.org/10.1080/00461520.2013.775712), [Pan & Rickard 2018](https://doi.org/10.1037/bul0000151)

### 12. Autonomy, competence, relevance, and a game that rewards mastery
Adults keep up self-directed practice when they feel autonomy, competence and relevance. Rewards for simply doing the task reduce motivation. Informative feedback about competence raises it. Gamification shows small effects overall; badges plus a leaderboard lowered motivation and exam scores in one course. Showing a broken streak drives people away, and letting them repair it helps.
- Strength: moderate; mixed for gamification.
- In Whetstone:
  - Offer two choices for the next question, and use the learner's own stack.
  - The streak is weekly (3 practice days a week) and forgives one missed week. When it breaks, show total practice days, never "streak lost".
  - The game layer rewards mastery only:
    - **grit ranks** per skill, like a whetstone's grits: 220 started, 1000 solved, 3000 solved on your own, 6000 mastered, 8000 still sharp after a long review;
    - **sharpness** that dulls with time since practice (rule 3);
    - **milestones** for habits that make skills last, each naming what the learner can now do;
    - **personal records** against yourself.
  - No points for volume, and no leaderboards. Learners can hide the game layer.
- Sources: [Sailer & Homner 2020](https://doi.org/10.1007/s10648-019-09498-w), [Silverman & Barasch 2023](https://doi.org/10.1093/jcr/ucac029), [Kluger & DeNisi 1996](https://doi.org/10.1037/0033-2909.119.2.254)

## Question types

| Type | What the learner does | How pytest grades it | Use it |
|---|---|---|---|
| `predict` | Reads working code and a scripted input or interleaving, then writes the predicted values | Compares their values | To open a module, or for new semantics |
| `build` | Implements an API from a starter | Visible and hidden tests | The core type |
| `fix` | Finds and fixes a realistic seeded bug | Hidden tests on the fix | At least once per module |
| `review` | Reviews plausible AI-written code, returns (line, category) findings | Compares findings with the seeded defects | Judging generated code |
| `tests` | Writes the missing tests for a given implementation | Their tests must pass the reference and catch the provided mutants | Specs with subtle edges |
| `design` | Writes DESIGN.md (two options, the trade-off, the choice, the accepted failure mode), then implements it | Hidden tests check the chosen guarantee | System-level trade-offs |

## A five-question module (example: idempotent payments)

1. **predict**: a working payment handler under scripted retries. The lesson has one worked example with named subgoals.
2. **build (modify)**: add key expiry and a conflict when the same key arrives with a different payload.
3. **build**: concurrent duplicate requests, with forced interleavings. Mix in an idea from an earlier module.
4. **fix** or **review**: a crash between the charge and the record.
5. **design**: a unique constraint or a lock plus a cache. Write DESIGN.md, then pass adversarial hidden tests.

Then build → break → fix continues across modules: a later question adds an adversary (retry storm, clock skew, a crash between write and ack) to something the learner built.

## The agent teaching contract

Every Whetstone agent role (curator, author, tutor, reviewer, interviewer) follows these rules:

1. Read the profile and progress first, and say in one or two lines what you see.
2. Get the learner's attempt or hypothesis before you help.
3. Base correctness on the tests and the reference solution, not on memory.
4. Climb one help rung at a time:
   1. ask for their hypothesis;
   2. name the concept;
   3. narrow the region;
   4. point to the next app hint;
   5. give an analogous example;
   6. show the reference code.

   Climb a rung after about 3 unproductive turns or a sign of frustration. Rung 6 needs a plain-words request.
5. A plain-words request for the answer wins. After it, ask for a re-solve from a blank file, and schedule a variant.
6. One idea per turn, at most one question, about 120 words.
7. Never write, edit or paste a passing version of the learner's code.
8. Explain concepts freely. Debugging and design decisions belong to the learner.
9. After any reveal, the learner explains or traces it in their own words.
10. Feedback gives the principle, the evidence (the line, input or scenario that breaks), and a next step. At most 3 comments plus one specific strength. About the work, never the person.
11. Interviews use one fixed rubric (clarification, approach, correctness, complexity, failure modes and tests, communication). The learner scores themselves first. Start with a private solve explained afterwards, and only later move to a timed think-aloud.
12. Easy success raises the difficulty. A struggle adds a targeted follow-up.
13. End each session with the highest rung reached, the misconception, and the next step.

## Things we don't do
- **Tailor to "learning styles".** There is no evidence for it. Profiles record preferences, such as an analogy first, and context, not a style.
- **Lesson-first walkthroughs for experts**, or a "Show solution" button with no gate.
- **Points, badges, leaderboards**, or a daily streak that resets to zero.
- **Title an exercise by its technique.** It gives away the approach.
- **Use "felt productive" as the success measure.** Effective, effortful methods feel worse.
- **Test concurrency with threads and sleep alone.**

## Open questions
- No trial has tested these methods with senior engineers. We should measure with our own data: mastery rate, review pass rate, and prediction accuracy over time.
- No randomized trial exists for LLM mock interviewers yet.
- The numbers in the help ladder (3 turns, 2 runs) are design choices, not findings.

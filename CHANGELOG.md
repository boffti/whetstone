# Changelog

All notable changes are listed here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0] - 2026-10-28

The first public release. Whetstone is a private practice space that runs on your machine. Your own AI agent writes the questions for you; real tests grade them.

### Practice
- A question page with a lesson, the problem, a four-rung hint ladder, a Monaco editor and pytest grading. Hints open one test run at a time; the reference opens after a solve or a confirmed give-up.
- Question types: build, predict, fix, review, tests (write the tests; Submit runs them against hidden buggy versions), design (a design note, then code for the guarantee it declares) and whiteboard system design. `examples/` has a finished question of each type.
- Predict then explain: guess which tests pass before a run and before Submit, then explain one hidden case in a sentence after a solve.
- Spaced review: a solved idea comes back as a variant on a new surface after 3 days, 3 weeks, 3 months, 6 months and a year. Mastery is a clean solve plus one passed review.
- Today: your next step, one alternative and the next review, then your focus, each skill with an edge that dulls with time. A Progress page has the calendar, honest numbers, milestones and records; the game layer rewards mastery, never volume, and can be hidden.
- Built for a side pane next to your agent: in the Code view, the problem's sections open as popovers over the editor. It also works full screen and on a phone, in light and dark.
- One tap after Submit says how a question felt (too easy, about right, too hard, felt artificial); your agent reads it when it writes the next one.

### Your agent
- Whetstone has no AI of its own. Your agent (Claude Code, Codex, Cursor or another) drives the `bin/whetstone` CLI on your own subscription, guided by `AGENTS.md` and eight skills: profile, curate, author, agent, tutor, pair, review and interview.
- Prepare buttons queue requests that your agent picks up while it watches (`whetstone watch`, `whetstone request claim|done|fail`). Buttons show queued, preparing and Start; a stopped agent's claim can be cancelled or retried. Prepare all queues one module at a time, in path order, so the first is ready while the rest are built.
- Prepare asks what a question is for: your own work (from your profile), a company you are preparing for (its own interview reports lead the brief), or a domain. Prepare again for… reframes a question you already have as a linked variant; the original keeps its progress.
- Live pair: your agent watches your session and replies in the editor's margin, at the line that matters, as a quiet reviewer, a coach or an interviewer.
- `whetstone today` starts a session with the reviews due, the question in progress and each path's next step; it can run from a Claude Code SessionStart hook.
- `whetstone-profile` drafts your profile from what your agent already knows and, with consent, your GitHub activity, including what your AI co-writes.

### System design
- A Design page of the design questions companies ask, most asked first. Draw on an Excalidraw whiteboard; your agent reads the drawing as a Mermaid diagram and grades the design against a rubric, quoting it.

### Catalog and paths
- 2,771 paraphrased interview reports from 397 companies, organised into 271 modules, each with links to its sources. Questions record which reports they are grounded in.
- 78 learning paths: systems to build, modelled on big-tech systems, across 11 domains. Filters, a sort, and a route map per path: point at a stop for its module, pick it to see every path that uses it.
- Company logos (Simple Icons, CC0) and domain icons, served from your machine.

### Privacy and security
- Everything stays on your machine: your profile, questions and progress live in the git-ignored `my/` folder. No account, no telemetry.
- The server answers only your own machine (local Host and Origin checks against DNS rebinding and cross-site requests).
- Test runs get an allowlisted environment (no `ANTHROPIC_API_KEY`), their own process group, and in Docker a memory cap, a process cap and a read-only `content/`. A failed hidden test shows only its message, never the expected values.
- Dependencies are pinned by hash (`uv.lock`), images by digest, and CI actions by commit SHA; CI runs tests on Python 3.11 to 3.13, CodeQL, zizmor and Scorecard.

[Unreleased]: https://github.com/boffti/whetstone/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/boffti/whetstone/releases/tag/v0.1.0

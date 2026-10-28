<a href="https://github.com/boffti/whetstone">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/brand/banner-dark.svg">
    <img src="docs/brand/banner-light.svg" width="100%" alt="Whetstone. Learn what you don't know. Relearn what you do. Keep every skill sharp, privately, around your own work.">
  </picture>
</a>

<p align="center">
  <b>A private practice space built around your work. Real-world problems from real interviews, written for you by your own AI, which also reviews your work and interviews you.</b>
</p>

<p align="center">
<a href="https://github.com/boffti/whetstone/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/boffti/whetstone/ci.yml?branch=main&style=flat-square&label=CI&labelColor=262624" alt="CI status"></a> <a href="https://scorecard.dev/viewer/?uri=github.com/boffti/whetstone"><img src="https://img.shields.io/ossf-scorecard/github.com/boffti/whetstone?style=flat-square&label=OpenSSF%20Scorecard&labelColor=262624" alt="OpenSSF Scorecard"></a> <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-2F6497?style=flat-square&labelColor=262624" alt="License: MIT"></a> <img src="https://img.shields.io/badge/python-3.11%2B-2F6497?style=flat-square&labelColor=262624" alt="Python 3.11 or later"> <img src="https://img.shields.io/badge/works_with-Claude_Code_%7C_Codex_%7C_Cursor-B8572F?style=flat-square&labelColor=262624" alt="Works with Claude Code, Codex and Cursor"> <img src="https://img.shields.io/badge/runs-on_your_machine-2E7A4D?style=flat-square&labelColor=262624" alt="Runs on your machine">
</p>

<p align="center">
  <a href="#why-whetstone">Why Whetstone</a> ·
  <a href="#quick-start">Quick start</a> ·
  <a href="#how-to-use-it">How to use it</a> ·
  <a href="#screenshots">Screenshots</a> ·
  <a href="#features">Features</a> ·
  <a href="#roadmap">Roadmap</a> ·
  <a href="CONTRIBUTING.md">Contributing</a>
</p>

<p align="center">
  <img src="docs/demo.webp" width="860" alt="Whetstone in the browser pane of an AI agent's desktop app. The learner presses Prepare, the agent builds a caching question, the learner reads the problem's sections over the code, guesses then runs the tests, a hidden test fails, the agent asks a question at line 13, the fix passes every test, and the learner explains why. Then the Paths page, where pointing at a stop shows its module, and the Design page.">
</p>

## Why Whetstone

Skills need three kinds of care, and Whetstone gives all three:

- **Learn what you don't know.** Pick a system you want to understand, or a topic your next role will need. Your agent writes it as a series of steps, each one a little harder than the last, starting from what you already know.
- **Relearn what you know.** The things you learned years ago, or now hand to your AI, fade quietly. Whetstone brings them back as fresh problems, so you find out what is still there.
- **Keep your skills sharp.** Every idea you solve returns on a new surface after 3 days, 3 weeks and 3 months. Each skill shows how sharp it is today, and your agent suggests what to practice next.

**Built around you.** Your agent already knows you from the work you've done together: what you build, your stack and experience, where you're headed, and what it now writes for you. It drafts your profile from that, and from your GitHub activity if you agree, so there's nothing to fill in. You only check the draft. Every question is then written for you: a scenario from your world, at the step you're ready for, explained the way you learn.

**Real problems from real interviews.** The question bank is grounded in 2,771 interview reports from 397 companies, organised into 271 modules and 78 systems to build. The problems are practical: ledgers that must balance, retries that must not charge twice, rate limiters, caches and schedulers. There are no throwaway puzzles. That makes Whetstone good interview preparation too: filter by the companies you're aiming for, practice system design on a whiteboard, and ask your agent for a mock interview.

**Your AI as reviewer and interviewer.** The same agent that writes your questions also reviews your solutions like a staff engineer, nudges you one step at a time when you're stuck without giving the answer away, pairs with you in the editor's margin, and runs mock interviews.

**Private by design.** Whetstone runs on your machine. Your profile, your questions and your progress never leave it. There's no account and no telemetry, and it runs on the AI subscription you already have.

### Same idea, written for you

Three engineers ask their agents for the next question in the rate limiter module. Each one practices the same idea, a token bucket, in the world they work in:

| The learner | The question their agent writes |
|---|---|
| A payments engineer | **Throttle the webhook sender.** Card networks accept 50 calls a second per merchant. Queue the rest instead of dropping them, and never let one busy merchant starve the others. |
| A trading engineer | **Stay under the exchange's order limit.** The venue rejects a burst over 200 orders a second and bans you for a minute. Smooth a burst at the open without losing the order. |
| An LLM platform engineer | **Share a token budget across model providers.** Each provider allows a number of tokens a minute. Spend the budget across many users fairly, and fall back when one provider is full. |

> [!NOTE]
> Whetstone has no AI of its own. Your agent (Claude Code, Codex, Cursor or another) writes the questions on the subscription you already pay for, and Whetstone checks and grades them on your machine.

## What you practice

| What your AI does for you | What you practice in Whetstone |
|---|---|
| Writes the code | **Build** questions: the problem comes first; the lesson opens after your first try |
| Explains code you didn't write | **Predict** questions: read working code and say what it does before you run it |
| Finds the bug | **Fix** questions: a bug report with symptoms, never the cause |
| Reviews its own pull request | **Review** questions: find the defects planted in plausible AI-written code |
| Writes the tests | **Tests** questions: your tests must catch hidden bugs you never see |
| Sketches the architecture | **Design** questions: draw it on a whiteboard, and your agent grades it against a rubric |

## Quick start

You need Docker and an AI coding agent that can run commands in a folder.

```bash
git clone https://github.com/boffti/whetstone && cd whetstone
cp .env.example .env
docker compose up -d --build        # then open http://localhost:8000
claude                              # or codex, or open the folder in Cursor
```

Open `http://localhost:8000` in a browser pane next to your agent, such as the built-in browser in Claude's desktop app, or in any browser tab. Then tell your agent: *"Set up my Whetstone profile."* If something doesn't work, run `bin/whetstone doctor`: it checks your setup and says how to fix each problem.

## How it works

```mermaid
flowchart LR
    P["Your profile"]:::clay --> W["Your agent<br/>writes a question"]:::steel
    W --> C["Whetstone<br/>checks it"]:::steel
    C --> S["You solve it,<br/>tests grade it"]:::green
    S --> R["It comes back<br/>days and weeks later"]:::clay
    R --> W
    classDef clay fill:#B8572F,stroke:#9C4526,color:#FFFFFF
    classDef steel fill:#2F6497,stroke:#244C77,color:#FFFFFF
    classDef green fill:#2E7A4D,stroke:#245F3C,color:#FFFFFF
```

Your profile holds your job, stack, goals and gaps. Before a question reaches you, Whetstone checks that its reference solution passes, its starter fails, and every wrong version of the solution is caught by the tests. Solved ideas come back as variants after 3 days, 3 weeks and 3 months.

Your agent drives a plain command line (`bin/whetstone`); the app only creates, checks and grades. While you work, your agent can watch the app and ask one question at a time in your editor's margin, like a pair would. (An optional in-app generator can use your own Anthropic API key. It is off unless you set one.)

## How to use it

### Ask your agent

Talk to your agent in plain words. It follows the skill files in `.claude/skills/` and drives Whetstone through the `bin/whetstone` command line.

| You say | What happens |
|---|---|
| *"Set up my Whetstone profile."* | It drafts `my/profile.md` from what it already knows about you and shows you the draft to check. With your consent it also reads your GitHub activity, including which code your AI co-wrote, because those skills fade first. |
| *"Watch Whetstone."* | It waits in the background for the buttons you press in the app, and does the work while you keep practicing. |
| *"What should I practice next?"* | It reads your progress and offers two choices. Reviews that are due come first. |
| *"Make me a learning path to build a checkout system."* | It proposes an ordered list of modules, or finds a shipped path that fits, and creates it when you agree. |
| *"Build the next question for the rate-limiter module."* | It writes the lesson, problem, hints, tests and wrong versions of the solution, then files the question once Whetstone's checks pass. |
| *"I'm stuck on rate-limiter/02."* | It runs your code, then helps one step at a time: a question first, then the idea, then a hint. It doesn't write your solution unless you ask. |
| *"Pair with me as an interviewer."* | It watches you work and asks one question at a time in your editor's margin. |
| *"Review my solution."* | It gives up to three comments, most severe first, each with the principle, the evidence and a next step. |
| *"Interview me on system design."* | It runs a mock interview and scores you against a rubric. |

### Or use the buttons

While your agent watches, you can work from the app instead:

- **Prepare** on a module, a path or a system design question asks your agent to build it. The button turns into **Start** when the question is ready.
- **Ask for review** on a design has your agent grade it against the rubric.
- **Follow this path** and **+ Focus** tell your agent what you want to keep sharp.

## Screenshots

These are at side-pane width (820 px), the size the app is designed for. It also works full screen and on a phone. They follow your GitHub theme, light or dark.

### Today and progress

<table>
<tr>
<td width="50%" valign="top"><picture><source media="(prefers-color-scheme: dark)" srcset="docs/screenshots/today-dark.png"><img src="docs/screenshots/today.png" alt="Today: Your next step, one alternative and when your next review is due, then your focus: each skill with an edge that shows how sharp it is today."></picture><br><b>Today.</b> Your next step, one alternative and when your next review is due, then your focus: each skill with an edge that shows how sharp it is today.</td>
<td width="50%" valign="top"><picture><source media="(prefers-color-scheme: dark)" srcset="docs/screenshots/progress-dark.png"><img src="docs/screenshots/progress.png" alt="Progress: Practice days, honest numbers, milestones and personal records. The game layer rewards mastery, never volume."></picture><br><b>Progress.</b> Practice days, honest numbers, milestones and personal records. The game layer rewards mastery, never volume.</td>
</tr>
</table>

### Solving a question

<table>
<tr>
<td width="50%" valign="top"><picture><source media="(prefers-color-scheme: dark)" srcset="docs/screenshots/question-guess-dark.png"><img src="docs/screenshots/question-guess.png" alt="Guess first: Before your first run, you guess which tests will pass. Predicting is how reading code sticks."></picture><br><b>Guess first.</b> Before your first run, you guess which tests will pass. Predicting is how reading code sticks.</td>
<td width="50%" valign="top"><picture><source media="(prefers-color-scheme: dark)" srcset="docs/screenshots/question-sections-dark.png"><img src="docs/screenshots/question-sections.png" alt="The problem, beside your code: In a side pane, each section of the problem opens over the editor, so you read it without leaving your code."></picture><br><b>The problem, beside your code.</b> In a side pane, each section of the problem opens over the editor, so you read it without leaving your code.</td>
</tr>
<tr>
<td width="50%" valign="top"><picture><source media="(prefers-color-scheme: dark)" srcset="docs/screenshots/question-note-dark.png"><img src="docs/screenshots/question-note.png" alt="A note from your agent: A hidden test fails. Your agent, watching, asks one question at the line that matters."></picture><br><b>A note from your agent.</b> A hidden test fails. Your agent, watching, asks one question at the line that matters.</td>
<td width="50%" valign="top"><picture><source media="(prefers-color-scheme: dark)" srcset="docs/screenshots/question-solved-dark.png"><img src="docs/screenshots/question-solved.png" alt="Solved: Every test passes. Whetstone asks you to explain one hidden case in your own words, and a variant comes back in 3 days."></picture><br><b>Solved.</b> Every test passes. Whetstone asks you to explain one hidden case in your own words, and a variant comes back in 3 days.</td>
</tr>
</table>

<picture><source media="(prefers-color-scheme: dark)" srcset="docs/screenshots/full-question-dark.png"><img src="docs/screenshots/full-question.png" alt="A question at full screen: the module rail, the problem, and the editor with a failing hidden test and a note from the agent at line 13."></picture>

<p align="center"><sub>The same question at full screen: the module's questions, the problem, and the editor with test results.</sub></p>

### Paths and the catalog

<table>
<tr>
<td width="50%" valign="top"><picture><source media="(prefers-color-scheme: dark)" srcset="docs/screenshots/paths-dark.png"><img src="docs/screenshots/paths.png" alt="Paths: 78 systems to build. Filter by what suits you, what is ready now, a domain or a company. Pick a stop to see every path that uses that module."></picture><br><b>Paths.</b> 78 systems to build. Filter by what suits you, what is ready now, a domain or a company. Pick a stop to see every path that uses that module.</td>
<td width="50%" valign="top"><picture><source media="(prefers-color-scheme: dark)" srcset="docs/screenshots/path-detail-dark.png"><img src="docs/screenshots/path-detail.png" alt="One path: The modules in order, with the companies it is modelled on and your focus marked. Prepare all queues them in order, so you start the first while your agent prepares the rest."></picture><br><b>One path.</b> The modules in order, with the companies it is modelled on and your focus marked. Prepare all queues them in order, so you start the first while your agent prepares the rest.</td>
</tr>
<tr>
<td width="50%" valign="top"><picture><source media="(prefers-color-scheme: dark)" srcset="docs/screenshots/path-stop-dark.png"><img src="docs/screenshots/path-stop.png" alt="Every stop: Point at a stop to see the module, where you are with it, and what it covers."></picture><br><b>Every stop.</b> Point at a stop to see the module, where you are with it, and what it covers.</td>
<td width="50%" valign="top"><picture><source media="(prefers-color-scheme: dark)" srcset="docs/screenshots/catalog-dark.png"><img src="docs/screenshots/catalog.png" alt="Catalog: Every problem companies ask, with the reports behind it, most asked first."></picture><br><b>Catalog.</b> Every problem companies ask, with the reports behind it, most asked first.</td>
</tr>
</table>

<picture><source media="(prefers-color-scheme: dark)" srcset="docs/screenshots/full-paths-dark.png"><img src="docs/screenshots/full-paths.png" alt="The Paths page at full screen, filtered to paths that suit the learner, with each path's modules drawn as a route of stops."></picture>

### System design

<table>
<tr>
<td width="50%" valign="top"><picture><source media="(prefers-color-scheme: dark)" srcset="docs/screenshots/design-dark.png"><img src="docs/screenshots/design.png" alt="Design: System design questions from 217 interview reports, most asked first."></picture><br><b>Design.</b> System design questions from 217 interview reports, most asked first.</td>
<td width="50%" valign="top"><picture><source media="(prefers-color-scheme: dark)" srcset="docs/screenshots/design-whiteboard-dark.png"><img src="docs/screenshots/design-whiteboard.png" alt="Whiteboard: Draw the design with boxes and arrows (Excalidraw). No diagram syntax to learn."></picture><br><b>Whiteboard.</b> Draw the design with boxes and arrows (Excalidraw). No diagram syntax to learn.</td>
</tr>
<tr>
<td width="50%" valign="top"><picture><source media="(prefers-color-scheme: dark)" srcset="docs/screenshots/design-preview-dark.png"><img src="docs/screenshots/design-preview.png" alt="Preview: Your sections, plus the drawing exactly as your agent reads it: a Mermaid diagram."></picture><br><b>Preview.</b> Your sections, plus the drawing exactly as your agent reads it: a Mermaid diagram.</td>
<td width="50%" valign="top"><picture><source media="(prefers-color-scheme: dark)" srcset="docs/screenshots/design-review-dark.png"><img src="docs/screenshots/design-review.png" alt="Review: Your agent grades each rubric point with a quote from your design. A missed point shows only a question until you pass."></picture><br><b>Review.</b> Your agent grades each rubric point with a quote from your design. A missed point shows only a question until you pass.</td>
</tr>
</table>

## Features

<table>
<tr>
<td width="50%" valign="top"><img src="docs/brand/icons/for-you.svg" width="44" height="44" align="left" alt=""><b>Built around you</b><br>Your agent already knows your work, stack, experience and goals, and writes every question for you.</td>
<td width="50%" valign="top"><img src="docs/brand/icons/systems.svg" width="44" height="44" align="left" alt=""><b>Real problems from real interviews</b><br>2,771 interview reports from 397 companies, organised into 271 modules and 78 systems to build.</td>
</tr>
<tr>
<td width="50%" valign="top"><img src="docs/brand/icons/spaced.svg" width="44" height="44" align="left" alt=""><b>Learn, relearn, keep sharp</b><br>New ideas step by step, faded ones brought back, and every solved idea returning after 3 days, 3 weeks and 3 months.</td>
<td width="50%" valign="top"><img src="docs/brand/icons/agent.svg" width="44" height="44" align="left" alt=""><b>Your AI as reviewer and interviewer</b><br>It curates, writes, tutors, pairs in your editor's margin, reviews like a staff engineer and runs mock interviews.</td>
</tr>
<tr>
<td width="50%" valign="top"><img src="docs/brand/icons/tests.svg" width="44" height="44" align="left" alt=""><b>Graded by real tests</b><br>Visible tests check the basics; hidden tests check the edge cases. Each question ships with wrong solutions that the tests must catch.</td>
<td width="50%" valign="top"><img src="docs/brand/icons/design.svg" width="44" height="44" align="left" alt=""><b>System design on a whiteboard</b><br>Write the design, draw it in Excalidraw, and get it graded point by point against a rubric.</td>
</tr>
<tr>
<td width="50%" valign="top"><img src="docs/brand/icons/local.svg" width="44" height="44" align="left" alt=""><b>Private by design</b><br>Runs on your machine. No account, no telemetry, no API keys. Your work stays in a git-ignored folder.</td>
<td width="50%" valign="top"><img src="docs/brand/icons/mastery.svg" width="44" height="44" align="left" alt=""><b>Ready for interviews, too</b><br>Filter by the companies you're aiming for, practice their real questions, and ask your agent for a mock interview.</td>
</tr>
</table>

<details>
<summary><strong>The learning paths, by domain</strong></summary>

| Domain | Examples |
|---|---|
| Payments & fintech | payment processor, checkout, wallet, crypto exchange |
| Trading & markets | high-frequency trading, matching engine, risk, backtesting |
| Marketplaces & mobility | taxi booking, meal delivery, hotel booking, flash-sale tickets |
| Social & media | news feed, short-video feed, video and music streaming |
| Messaging & collaboration | chat, video calls, collaborative docs, email |
| AI & developer platforms | an LLM gateway like OpenRouter, LLM serving, RAG, CI, SSO |
| Data & infrastructure | data warehouse, Kafka-style log, S3, databases, observability |
| Search & ads, enterprise software, devices & industry | search engine, maps, CRM, payroll, vehicle OTA, fab scheduling |

</details>

## Your data

> [!IMPORTANT]
> Everything written for you lives in `my/`, which git ignores and Whetstone never commits. Your questions can mention your job, so they stay on your machine.

| Folder | Committed | What is in it |
|---|---|---|
| `whetstone/`, `bin/`, `scripts/`, `tests/` | yes | The app, the command line and their tests |
| `content/` | yes | The shared catalog and learning paths that contributors improve |
| `examples/` | yes | Finished questions that set the quality bar for agents |
| `my/` | **never** | Your profile, the questions written for you, your paths, drafts and progress |

A `git pull` brings new paths and research without touching your work. The server only answers requests from your own machine, and with Docker your code runs as a non-root user in a container. To keep your data somewhere else, set `WHETSTONE_HOME`.

## Roadmap

- [x] Build, predict, fix, review, tests and design questions, with mutation-checked tests
- [x] Requests from the app to your agent, and live pairing in the editor's margin
- [x] System design on a whiteboard, graded against a rubric
- [ ] **Terminal**: bash, text tools, jq and git, then the AWS CLI and Terraform, graded in a sandbox
- [ ] **More languages**: TypeScript and Go, chosen from your profile
- [ ] A hosted, read-only showcase of the catalog and paths

Have an idea? [Open an issue](https://github.com/boffti/whetstone/issues). [docs/PEDAGOGY.md](docs/PEDAGOGY.md) has the teaching rules every feature follows.

## Contributing

New learning paths, modules, paraphrased interview research, and app or command-line improvements are all welcome. [CONTRIBUTING.md](CONTRIBUTING.md) has the formats and the checks. Questions themselves are personal, so they stay out of the repo.

To report a security problem, follow [SECURITY.md](SECURITY.md).

<details>
<summary><strong>For AI agents</strong></summary>

Start with [AGENTS.md](AGENTS.md). It explains the content model, the `bin/whetstone` commands, and which skill file in `.claude/skills/` covers each job: setting up a profile, curating, writing questions, tutoring, pairing, reviewing and interviewing. [AUTHORING.md](AUTHORING.md) is the contract every question follows.

</details>

<details>
<summary><strong>Command line reference</strong></summary>

`bin/whetstone` runs inside the Docker app when it is up, so tests run in the container. Otherwise it runs locally with `uv`. Agents: start with [AGENTS.md](AGENTS.md).

```
bin/whetstone serve [--host 127.0.0.1] [--port 8000]
bin/whetstone doctor                                   # check the setup; says how to fix each problem

bin/whetstone path list [--domain D] [--json]
bin/whetstone path show <path> [--json]
bin/whetstone path create <id> --goal "..." [--title "..."] [--domain D] [--company C ...]
bin/whetstone path add <path> <module> [<module> ...]

bin/whetstone module create <id> [--from-catalog <problem>] [--title "..."] [--description "..."]
bin/whetstone module list [--json]

bin/whetstone question brief <module> [--topic "..."] [--type whiteboard] [--difficulty medium] [--notes "..."]
bin/whetstone question new <module> <slug> [--title "..."] [--type whiteboard]
bin/whetstone question add <folder> --module <module>
bin/whetstone question check [module | module/question ...]      # also: bin/whetstone validate

bin/whetstone catalog [<problem-id>] [--company X] [--round R] [--search W] [--json]
bin/whetstone progress [--json]
bin/whetstone draft <module/question>
bin/whetstone test <module/question> [--all]
bin/whetstone watch [--key K] [--for SECONDS]           # stream app activity for a pairing agent
bin/whetstone note <module/question> "..." [--line N]    # show a remark over the learner's editor
bin/whetstone grade <module/question> < grade.json       # record a system design grade against its rubric
bin/whetstone requests [--json] [--all]                  # work the learner queued in the app
bin/whetstone request claim|done|fail <id> [--result ...]

bin/whetstone generate "<topic>" [--module generated] [--difficulty medium] [--notes "..."]   # optional; needs ANTHROPIC_API_KEY
```

To re-record the README GIF and screenshots after a UI change: `uv run --group demo python scripts/demo/record_demo.py` and `uv run --group demo python scripts/demo/screenshots.py`.

</details>

## License

[MIT](LICENSE)

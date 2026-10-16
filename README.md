# Whetstone

A self-hosted practice dojo where your own AI agent builds the lessons. Pick a system you want to understand, such as a payment processor, a taxi booking service, high-frequency trading, or an LLM gateway like OpenRouter. Your agent (Claude Code, Codex, Cursor, or another) writes each step for you: a short lesson, a practical problem, and a pytest suite that grades your code. Visible tests check the basics. Hidden tests check the edge cases interviewers ask about.

This repo is the shell: the app, the CLI your agent drives, and a shared catalog of systems and real interview reports. Everything written for you stays on your machine, in `my/`, and is never committed.

## Quick start

```bash
git clone <this repo> whetstone && cd whetstone
cp .env.example .env
docker compose up -d --build        # http://localhost:8000 (includes Redis)
claude                              # or codex, or open the folder in Cursor
```

Then ask your agent, in plain words:

- *"Set up my Whetstone profile."* It writes `my/profile.md` from what it knows about you, plus a few questions.
- *"Make me a learning path to build a checkout system."*, or pick one on the **Paths** page.
- *"Build the next question for the rate-limiter module."*
- *"I'm stuck on rate-limiter/01-token-bucket."*

The agent follows [AGENTS.md](AGENTS.md) and drives `bin/whetstone`. Whetstone has no AI inside, so it runs on your existing AI subscription with no API key. Every question goes through `bin/whetstone question add`, which files it only when the reference solution passes and the starter fails.

**Without Docker:** run `uv run whetstone serve`. Redis-based questions then need Redis at `REDIS_URL` (default `redis://localhost:6379/0`). On a Mac: `brew install redis && brew services start redis`.

**Side by side with your agent:** the app is built to run in a narrow browser pane next to your chat, such as Claude's built-in browser. Below 1100px it switches to one column with a full-height code editor.

## What is shared, and what is yours

| Folder | Committed | What is in it |
|---|---|---|
| `whetstone/`, `bin/`, `scripts/`, `tests/` | yes | The app, the CLI, and their tests |
| `content/catalog.yaml` | yes | About 250 modules (one topic each), with about 430 paraphrased interview reports from real companies |
| `content/paths/` | yes | About 70 learning paths: systems to build, modelled on the products of about 90 companies |
| `content/profile.example.md` | yes | The template your agent fills in |
| `examples/memoize/` | yes | A finished question that shows the format and quality bar |
| `my/` | **never** | Your profile, the questions your agent built for you, your own paths, your progress, your drafts |

Whetstone reads `content/` and `my/` together, and writes only to `my/`. If you change a shared path, your copy is saved in `my/paths/` and overrides the shared one. So `git pull` brings new paths and catalog research without touching your work, and your work, which may mention your job, can't be pushed by accident. To use a different folder for your data, set `WHETSTONE_HOME`.

## Content model

- A **question** is one exercise: a lesson, a problem, hints, starter code, a reference solution, and tests. It lives in `my/tracks/<module>/<NN-slug>/`.
- A **module** is a topic made of ordered questions, each a step up from the last. It is defined in `content/catalog.yaml`, often as a placeholder with no questions yet.
- A **learning path** is an ordered list of modules toward one goal, usually a system to build:

| Domain | Examples |
|---|---|
| Payments & fintech | payment processor, checkout, wallet, crypto exchange |
| Trading & markets | high-frequency trading, matching engine, risk, backtesting |
| Marketplaces & mobility | taxi booking, meal delivery, hotel booking, flash-sale tickets |
| Social & media | news feed, short-video feed, video and music streaming |
| Messaging & collaboration | chat, video calls, collaborative docs, email |
| AI & developer platforms | an LLM gateway like OpenRouter, LLM serving, RAG, CI, SSO |
| Data & infrastructure | data warehouse, Kafka-style log, S3, databases, observability |
| Search & ads, Enterprise software, Devices & industry | search engine, maps, CRM, payroll, vehicle OTA, fab scheduling |

## Using the app

- **Catalog:** problems that companies actually ask, with each report's question, follow-ups and sources.
- **Paths:** pick a system to build; modules not built yet show the request to give your agent.
- **Practice:**
  1. Read the **Lesson** and **Problem** tabs.
  2. Write code in `solution.py`.
  3. Press **Run tests** (Ctrl/Cmd + Enter) for the visible tests, or **Submit** (Ctrl/Cmd + Shift + Enter) for all of them.
  4. If you're stuck, open hints one at a time.

  Your drafts and progress are saved in `my/whetstone.db`.

## Contributing

Shared improvements are welcome. They are what every user pulls and then has their own agent fill in:

- **New learning paths:** add `content/paths/<id>.yaml` with `title`, `goal`, `domain`, `companies` and an ordered list of `modules`.
- **New modules:** add a placeholder to `content/catalog.yaml` with an `id`, a `title`, and a `summary` of what the learner builds.
- **Interview research:**
  1. Write paraphrased reports as JSON in `data/research/`, which is git-ignored.
  2. Merge them with `uv run --no-project --with pyyaml python scripts/merge_catalog.py data/research/*.json`.
  3. Commit only the updated `catalog.yaml`.

  The merge dedupes reports, folds narrow topics into broader modules (`ALIASES` in the script), and keeps hand-written fields.
- **The app and CLI:** run the tests with `uv run python -m pytest tests -q`.

Keep personal and employer details out of anything you commit. Questions themselves are personal, so they are not contributed.

## Safety

Whetstone runs the code you submit, with your user's permissions. It listens on `127.0.0.1` only, so do not expose it to the internet. The Docker setup runs submissions inside the container as a non-root user.

## Command line

`bin/whetstone` runs inside the Docker app when it is up, so tests run in the container. Otherwise it runs locally with `uv`.

```
bin/whetstone serve [--host 127.0.0.1] [--port 8000]

bin/whetstone path list [--domain D] [--json]
bin/whetstone path show <path> [--json]
bin/whetstone path create <id> --goal "..." [--title "..."] [--domain D] [--company C ...]
bin/whetstone path add <path> <module> [<module> ...]

bin/whetstone module create <id> [--from-catalog <problem>] [--title "..."] [--description "..."]
bin/whetstone module list [--json]

bin/whetstone question brief <module> [--topic "..."] [--difficulty medium] [--notes "..."]
bin/whetstone question new <module> <slug> [--title "..."]
bin/whetstone question add <folder> --module <module>
bin/whetstone question check [module | module/question ...]      # also: bin/whetstone validate

bin/whetstone catalog [<problem-id>] [--company X] [--round R] [--search W] [--json]
bin/whetstone progress [--json]
bin/whetstone draft <module/question>
bin/whetstone test <module/question> [--all]

bin/whetstone generate "<topic>" [--module generated] [--difficulty medium] [--notes "..."]   # optional; needs ANTHROPIC_API_KEY
```

# Whetstone: instructions for AI agents

Whetstone is a self-hosted practice dojo. The learner works in the web app at http://localhost:8000: a lesson, an editor, and pytest grading. You are their AI agent (Claude Code, Codex, Cursor, or another). You run on the learner's own subscription, and Whetstone has no AI of its own. You do the thinking and writing; the `bin/whetstone` CLI creates things and checks them.

## How content is organised

- A **question** is one exercise: a lesson, a problem, hints, starter code, a reference solution, and tests.
- A **module** is a topic made of ordered questions, each a step up from the last. An example is `rate-limiter`.
- A **learning path** is an ordered list of modules toward one goal, usually a system to build: a payment processor, a taxi service, an LLM gateway like OpenRouter, a high-frequency trading system. About 70 paths ship, grouped by domain and modelled on the systems of about 90 companies.
- The **catalog** (`content/catalog.yaml`) defines every module: its id, title and summary, plus any interview reports from real companies. Most path modules start as **placeholders**: they are defined in the catalog, but no questions exist yet. You build them when the learner reaches them.

Run every command from this folder. When the Docker app is up, `bin/whetstone` runs inside the container.

## Where things live

| Folder | Committed | What is in it |
|---|---|---|
| `content/` | yes | The shared catalog (`catalog.yaml`) and shared paths (`paths/`). Contributors improve these. |
| `examples/` | yes | A finished question to copy the format and quality from. |
| `my/` | **never** | The learner's profile, the questions you build for them, their own paths, and their progress. |

Everything you build for the learner goes into `my/`; the CLI writes nowhere else. When you change a shared path, the CLI saves the learner's copy in `my/paths/`.

## First run: the learner's profile

If `my/profile.md` does not exist, create it before anything else. Copy `content/profile.example.md` and fill it in from what you already know about the learner: their projects, their chats with you, and their memory files. Ask a few short questions to fill the gaps. Every question you write is tailored to this file. Ask especially what their AI does for them at work: those skills fade fastest, so Whetstone practises them first.

## Commands

| Command | What it does |
|---|---|
| `bin/whetstone catalog [--company X] [--round R] [--search W]` | Lists catalog problems, most asked first. `catalog <id>` shows one in full. |
| `bin/whetstone progress` | Shows each question's runs, hints opened and solution views, whether a solve was clean or assisted, mastery, and when its spaced review is due. |
| `bin/whetstone path list [--domain D]` | Lists paths grouped by domain, for example "Payments & fintech" or "Trading & markets". |
| `bin/whetstone path create <id> --goal "..." [--domain D] [--company C]...` | Creates a learning path. |
| `bin/whetstone path add <path> <module>...` | Appends modules in order. A catalog problem that is not built yet is allowed. |
| `bin/whetstone path show <path>` | Lists the path's modules in order, with progress, and says which modules are not built. |
| `bin/whetstone module create <id> [--from-catalog <problem>]` | Creates an empty module. `question add` also creates a module when it needs one. |
| `bin/whetstone module list` | Lists all modules, with progress. |
| `bin/whetstone question brief <module> [--topic "..."]` | Gives instructions for the module's next question: what to read, what exists, real reports, and the suggested question type. |
| `bin/whetstone question new <module> <slug>` | Creates the question's files to fill in, in `my/.staging/<slug>/`. |
| `bin/whetstone question add <folder> --module <id>` | Checks the format, that the reference solution passes and that the starter fails, then files the question as the module's next one. |
| `bin/whetstone question check [module or module/question]` | Checks questions again. Run it to catch flaky tests. |
| `bin/whetstone draft <module/question>` | Shows the learner's current code. |
| `bin/whetstone test <module/question> [--all]` | Runs the tests on the learner's code. These runs are not recorded. |

`catalog`, `progress`, `path show`, `path list` and `module list` also take `--json`.

## Jobs: use the skill for each one

Each job has a skill file with the full steps. Claude Code loads them automatically. Other agents: read the file and follow it.

| The learner says | Skill |
|---|---|
| "What should I practise?", "What's next?", "Make me a learning path" | [.claude/skills/whetstone-curate/SKILL.md](.claude/skills/whetstone-curate/SKILL.md) |
| "Build the next question for X", "Fill in my path", "Make a variant" | [.claude/skills/whetstone-author/SKILL.md](.claude/skills/whetstone-author/SKILL.md) |
| "I'm stuck on X", "Why does this fail?" | [.claude/skills/whetstone-tutor/SKILL.md](.claude/skills/whetstone-tutor/SKILL.md) |
| "Review my solution" | [.claude/skills/whetstone-review/SKILL.md](.claude/skills/whetstone-review/SKILL.md) |
| "Interview me on X", "Mock interview" | [.claude/skills/whetstone-interview/SKILL.md](.claude/skills/whetstone-interview/SKILL.md) |

All of them follow the teaching contract in [docs/PEDAGOGY.md](docs/PEDAGOGY.md). In short:
- get the learner's attempt first;
- climb one help rung at a time;
- never write their code;
- give feedback about the work, never the person;
- bring solved ideas back as spaced variants.

## Rules

- Never edit the learner's code, drafts, or `my/whetstone.db`. Their progress is theirs.
- Never copy anything from `my/` into `content/`, `examples/`, or a commit. `my/` can hold details of the learner's job.
- Contributing to the shared repo is a different job: adding catalog research, shared paths, or modules. Edit `content/` only when the learner asks for that, and keep it free of personal details.
- Do not change existing questions unless the learner asks.
- `content/catalog.yaml` holds paraphrased reports with source links. To add research, follow the Catalog section of README.md.
- If your sandbox blocks Docker or uv, run commands as `WHETSTONE_PYTHON=<python with the dependencies> bin/whetstone ...`.

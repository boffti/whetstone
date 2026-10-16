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

If `my/profile.md` does not exist, create it before anything else. Copy `content/profile.example.md` and fill it in from what you already know about the learner: their projects, their chats with you, and their memory files. Ask a few short questions to fill the gaps. Every question you write is tailored to this file.

| Command | What it does |
|---|---|
| `bin/whetstone catalog [--company X] [--round R] [--search W]` | Lists catalog problems, most asked first. `catalog <id>` shows one in full. |
| `bin/whetstone progress` | Shows what the learner solved and attempted, the hints they opened, and the solutions they viewed. |
| `bin/whetstone path list [--domain D]` | Lists paths grouped by domain, for example "Payments & fintech" or "Trading & markets". |
| `bin/whetstone path create <id> --goal "..." [--domain D] [--company C]...` | Creates a learning path. |
| `bin/whetstone path add <path> <module>...` | Appends modules in order. A catalog problem that is not built yet is allowed. |
| `bin/whetstone path show <path>` | Lists the path's modules in order, with progress, and says which modules are not built. |
| `bin/whetstone module create <id> [--from-catalog <problem>]` | Creates an empty module. `question add` also creates a module when it needs one. |
| `bin/whetstone module list` | Lists all modules, with progress. |
| `bin/whetstone question brief <module> [--topic "..."]` | Gives instructions for the module's next question: what to read, what exists, and real reports. |
| `bin/whetstone question new <module> <slug>` | Creates the question's files to fill in, in `my/.staging/<slug>/`. |
| `bin/whetstone question add <folder> --module <id>` | Checks that the reference solution passes and the starter fails, then files the question as the module's next one. |
| `bin/whetstone question check [module or module/question]` | Checks questions again. Run it to catch flaky tests. |
| `bin/whetstone draft <module/question>` | Shows the learner's current code. |
| `bin/whetstone test <module/question> [--all]` | Runs the tests on the learner's code. These runs are not recorded. |

`catalog`, `progress`, `path show`, `path list` and `module list` also take `--json`.

## Curate: "What should I practise?" or "Make me a learning path"

1. Read `my/profile.md`, which holds the learner's work, goals and learning style. Then run `bin/whetstone progress` and `bin/whetstone catalog`.
2. For a quick pick, propose 3 modules. Give one line on why each fits: what their work touches, what they struggled with (many runs, opened hints, viewed solutions), and what is asked often.
3. For a path, first check `bin/whetstone path list`, because a shipped path may already match, such as "Build a checkout system". If none fits, propose an ordered list of modules. Reuse catalog modules where they fit, and add a new placeholder with `module create`. Wait for the learner to agree, then run `path create` and `path add`.
4. Do not build questions until the learner picks.

## Build: "Build the next question for X" or "Fill in my path"

1. Run `bin/whetstone question brief <module>` and follow it exactly.
2. Run `bin/whetstone question new <module> <slug>`, then write every file. Follow AUTHORING.md.
3. Run `bin/whetstone question add my/.staging/<slug> --module <module>`. If it prints problems, fix them and run it again until it says "Added".
4. Run `bin/whetstone question check <key>` twice more.
5. Give the learner the link it printed.

To fill a module, repeat the build steps 3 to 5 times; each question takes on the next follow-up from the reports. To fill a path, run `path show` and build the first question of each module marked "not built".

## Tutor: "I'm stuck on X"

1. Run `bin/whetstone draft <key>` and `bin/whetstone test <key>`.
2. Name the failing behavior and the concept behind it. Ask one question that leads the learner toward the fix.
3. If they are still stuck, point them to the next hint in the app, or paraphrase it from the question's `hints.md`.
4. Do not write their solution or paste the reference solution unless they ask for it in plain words.

## Rules

- Never edit the learner's code, drafts, or `my/whetstone.db`. Their progress is theirs.
- Never copy anything from `my/` into `content/`, `examples/`, or a commit. `my/` can hold details of the learner's job.
- Contributing to the shared repo is a different job: adding catalog research, shared paths, or modules. Edit `content/` only when the learner asks for that, and keep it free of personal details.
- Do not change existing questions unless the learner asks.
- `content/catalog.yaml` holds paraphrased reports with source links. To add research, follow the Catalog section of README.md.
- If your sandbox blocks Docker or uv, run commands as `WHETSTONE_PYTHON=<python with the dependencies> bin/whetstone ...`.

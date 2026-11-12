# Terminal dojo: design

Status: agreed 2026-11-07. Roadmap item: "Terminal: bash, text tools, jq and git".

## Goal

Practice the command-line work that AI now does for people: text pipelines, jq, git rescues, safe
shell scripts. Then other CLIs (sqlite3, kubectl, Terraform, the AWS CLI) without changing app code.

## Decisions

1. **A real shell, not a simulated one.** A fake shell cannot behave like git or jq, and every new
   CLI would have to be rebuilt. The learner uses their own terminal app.
2. **The shell runs in the Whetstone image.** Grading runs on Linux with GNU tools; macOS ships BSD
   `sed`, `grep` and `date`, so a script that works on the Mac can fail on Submit.
   `bin/whetstone shell <key>` opens bash in the question's folder, in a container with no network
   that mounts only that folder. Nothing else (the rest of `my/`, the database) can be broken.
   Without Docker it opens the learner's own shell, with a warning. A browser terminal can come
   later; it would be the same container shell in another window, behind the server's Host/Origin check.
3. **Every answer is a replayable `solution.sh`.** The learner explores live in `sandbox/`, then
   writes the commands into the script. Tests replay it on fresh scenarios, so hidden variants
   (other data, other commit hashes, edge cases) and the mutation gate work as for every other type.
4. **Content follows the existing model.** Whetstone ships the type, the scaffold, helpers, tool
   packs and one example per kind; the learner's AI writes the questions into `my/`, and
   `question add` checks them.

## The question

`type: terminal` reuses the AI-allowed round's machinery (workspace folder, stages, a snapshot per
run, folder mutants, the run-by-run timeline in `draft`) with these differences: it is solo (no AI;
an agent opened in the folder only gives hints), it has no ownership check, and `scenario.py`
builds what the script works on.

```
challenge.yaml          type: terminal, tools: [git]
problem.md              ## Stage 1, ## Stage 2 ...
lesson.md  hints.md
scenario.py             build(path, variant): the files or repo to work on
starter/solution.sh     the empty script
solution/solution.sh    the reference
tests/test_visible_1.py  tests/test_hidden_1.py ...
mutants/<name>/solution.sh   one wrong script per misconception ("# Misconception: ...")
```

- **Start** copies `starter/` into `my/workspaces/<module>/<question>/` and builds the visible
  scenario into `sandbox/`. Deleting `sandbox/` and starting again rebuilds it.
- **Run** copies `solution.sh`, `scenario.py`, the helpers and the tests into a throwaway folder.
  Each test builds a fresh scenario and runs the script with a fixed environment (`LC_ALL=C`,
  `TZ=UTC`, fixed git identity and dates, an empty `HOME`, a timeout), then checks stdout, the exit
  code, files or git state. **Submit** adds the hidden tests.
- `scenario.py` and the tests never reach the workspace, so the hidden data stays hidden.

## Tool packs

`content/tools.yaml` lists each CLI: its Debian packages, a check command, and whether the image
installs it by default. The Dockerfile installs the default packs plus any named in
`WHETSTONE_TOOLS` in `.env`. The runner and `question add` refuse a question whose `tools:` are
not installed, with the fix; `doctor` lists the packs and their versions.

Helpers in `whetstone/terminal/` (`sh.py`, `git.py`) are copied into every terminal run as the
`tools` package: tests and scenarios write `from tools import sh, git`.

Adding a CLI: a registry entry, a helper if it needs one, one example question, catalog modules.

## Ships first

Packs `shell`, `git`, `jq`; examples `examples/git-lost-commits/` (a git rescue) and
`examples/error-hotspots/` (a text pipeline); catalog modules `git-rescue`, `text-pipelines`,
`json-on-the-cli`, `safe-shell-scripts`; a "Terminal fluency" path.

## Later

A browser terminal; heavier packs (sqlite3, kubectl, Terraform, the AWS CLI on a local fake);
predict questions for pipelines; incident drills on top of the shell.

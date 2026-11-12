## What and why

<!-- What does this change, and why? Link an issue if there is one. -->

## Type

- [ ] Learning path(s) in `content/paths/`
- [ ] Module(s) in `content/catalog.yaml`
- [ ] Interview research merged into `content/catalog.yaml`
- [ ] App, CLI, or docs
- [ ] Agent tooling: skills or hooks in `.claude/`, or the mod in `mods/`

## Checklist

- [ ] Nothing comes from my `my/` folder, and nothing describes my employer or private work.
- [ ] Research is paraphrased in my own words, with a source link for each report.
- [ ] `uv run ruff check . && uv run ruff format --check .` passes.
- [ ] `uv run python -m pytest` passes.
- [ ] `uv run python scripts/check_content.py` passes.
- [ ] `CHANGELOG.md` has a line under Unreleased, if a learner or a contributor would notice the change.
- [ ] A change to `mods/whetstone/` passes `claude plugin validate mods/whetstone` and `claude plugin test mods/whetstone`.
- [ ] UI changes were checked at desktop width and in a narrow pane (under 1100px).

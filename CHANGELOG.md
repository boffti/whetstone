# Changelog

All notable changes are listed here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Web app: catalog of interview problems, learning paths by domain, and a practice view with an editor and pytest grading. It also works in a narrow pane next to your AI agent.
- CLI (`bin/whetstone`) for AI agents: `path`, `module`, `question`, `catalog`, `progress`, `draft` and `test` commands, with `AGENTS.md`.
- Shared content: about 260 modules with about 620 paraphrased interview reports, and 78 learning paths modelled on big-tech systems.
- Catalog research from r/InterviewCoderHQ: 188 reports added with thin-source confidence, 8 new modules (incident triage, live data migration, joins under a memory limit, profiler events, a data-source gateway, a REST take-home, longest-prefix routing, a Conv2D forward pass) and 6 new paths (production operations, a Temporal-style workflow engine, Ramp-style spend management, a Retool-style tools builder, a Cursor-style editor backend, a feature-flag service).
- Personal content in a git-ignored `my/` folder: profile, built questions, own paths and progress.
- Interface: IBM Plex type, slate and wet-stone colors in dark and light, keyboard hints on Run tests and Submit, and a per-test edge meter after each run.
- Teaching: five agent skills (curate, author, tutor, review, interview) built on `docs/PEDAGOGY.md`. Questions now have a type (build, predict, fix, review), problem-first lessons, a four-rung hint ladder and spaced variants. `progress` reports clean or assisted solves, mastery and review dates.
- App: a Practice home page, which is now the landing page. Problem-first lessons, hints that unlock one test run at a time, a solution that opens after a solve or a confirmed give-up, clean, assisted and mastered statuses, and a weekly streak with one forgiven week. The UI says question and module instead of challenge and track.
- `whetstone doctor` checks the setup and explains each fix. The progress database is versioned: upgrades run automatically, after a backup to `whetstone.db.v<N>.bak`.
- Shared content: the "Six pressures of system design" foundations path, with `realtime-push` and `cqrs-read-model` modules.
- Test output is plain text even when the app's environment sets FORCE_COLOR (no escape codes in the results panel).
- Practice home is a personal dashboard: profile header, skill edges that dull over time, up next, a 26-week calendar, a numbers ledger, milestones, personal records, target companies and recent runs. Grit ranks and milestones reward mastery, never volume, and can be hidden.
- `whetstone-profile` skill: builds the profile header from what the agent knows, plus GitHub activity and AI co-author trailers, with consent.
- Live pair: the app records what you do (migration 3). `whetstone watch` streams it for your agent, `whetstone note` shows its remarks over your editor with a margin marker, and a Pair switch (off, quiet, coach, interviewer) sets how often it speaks. New `whetstone-pair` skill.
- Catalog as compact rows with an All / Ready / Not built filter, keyboard navigation (`/`, `j`, `k`, Enter) and grouped sources. Paths show each path as a strip of modules, list your started paths first, and offer one "Fill in my path" request.
- Code blocks in lessons, problems, hints and solutions are syntax highlighted.
- Predict then explain: guess which tests pass before your first run and before Submit, explain one hidden case after a solve, and see prediction accuracy on the dashboard (migration 4). Skippable, with an off switch.
- Pages that cannot load now say why instead of staying blank.
- Mutation-check gate: every new build, fix and design question ships 2 to 5 mutants (wrong versions of the reference, one per misconception), and `question add` refuses it if any mutant passes the tests.
- New question types: `tests` (write the tests for working code; Submit runs them against hidden mutants, see `examples/retry-tests/`) and `design` (a design note naming options, trade-off, choice and accepted failure mode, then code for the declared guarantee).
- Colours follow Claude Desktop: warm cream and charcoal surfaces, clay for the main action, neutral selected states, so the app reads as part of Claude in its side pane.
- Security: localhost-only requests (blocks DNS rebinding and cross-site requests), hash-pinned dependencies, digest-pinned images, and SHA-pinned CI actions.

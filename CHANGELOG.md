# Changelog

All notable changes are listed here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Web app: catalog of interview problems, learning paths by domain, and a practice view with an editor and pytest grading. It also works in a narrow pane next to your AI agent.
- CLI (`bin/whetstone`) for AI agents: `path`, `module`, `question`, `catalog`, `progress`, `draft` and `test` commands, with `AGENTS.md`.
- Shared content: about 250 modules with paraphrased interview reports, and 71 learning paths modelled on big-tech systems.
- Personal content in a git-ignored `my/` folder: profile, built questions, own paths and progress.
- Interface: IBM Plex type, slate and wet-stone colors in dark and light, keyboard hints on Run tests and Submit, and a per-test edge meter after each run.
- Teaching: five agent skills (curate, author, tutor, review, interview) built on `docs/PEDAGOGY.md`. Questions now have a type (build, predict, fix, review), problem-first lessons, a four-rung hint ladder and spaced variants. `progress` reports clean or assisted solves, mastery and review dates.
- App: a Practice home page, which is now the landing page. Problem-first lessons, hints that unlock one test run at a time, a solution that opens after a solve or a confirmed give-up, clean, assisted and mastered statuses, and a weekly streak with one forgiven week. The UI says question and module instead of challenge and track.
- `whetstone doctor` checks the setup and explains each fix. The progress database is versioned: upgrades run automatically, after a backup to `whetstone.db.v<N>.bak`.
- Shared content: the "Six pressures of system design" foundations path, with `realtime-push` and `cqrs-read-model` modules.
- Security: localhost-only requests (blocks DNS rebinding and cross-site requests), hash-pinned dependencies, digest-pinned images, and SHA-pinned CI actions.

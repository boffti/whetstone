# Contributing to Whetstone

Thanks for helping. Whetstone is a shared shell: contributors improve the parts everyone uses, and each learner's own AI agent writes their questions from those parts. So most contributions are **content**: learning paths, modules, and interview research. Code improvements are welcome too.

## What to contribute, and what not to

| Welcome | Please don't |
|---|---|
| New learning paths in `content/paths/` | Questions written for you (they are personal and live in your `my/`) |
| New placeholder modules in `content/catalog.yaml` | Anything from your `my/` folder, or details about your employer |
| Paraphrased interview reports with sources | Text copied from posts, sites, or books |
| Fixes and features in the app, CLI, and docs | New dependencies without a clear need |

## Set up

```bash
git clone https://github.com/boffti/whetstone && cd whetstone
uv sync --group dev                 # Python 3.11+; installs exactly what uv.lock pins
uv run whetstone serve              # or: docker compose up -d --build
```

Run every check before you open a pull request. CI runs the same ones:

```bash
uv run ruff check . && uv run ruff format --check .
uv run python -m pytest
uv run python scripts/check_content.py    # catalog, paths and privacy rules
```

## Add a learning path

A path is a system to build, made of 5 to 8 modules ordered from building blocks to the whole system. Add `content/paths/<id>.yaml`:

```yaml
title: Build a payment processor          # starts with "Build a" or "Build an"
goal: Accept card payments safely, retry without double charges, settle merchants daily.
domain: Payments & fintech                # reuse an existing domain where one fits
companies: [Stripe, Adyen]                # whose systems it is modelled on
modules: [idempotent-api, payment-lifecycle, ledger, webhook-delivery, payout-settlement]
```

- The file name is the id, in kebab-case and named after the system, not a company.
- Every module must exist in `content/catalog.yaml`. Reuse existing modules before you add new ones (`uv run whetstone catalog` lists them).

## Add a module

A module is one topic a learner builds, step by step. A new module starts as a placeholder in `content/catalog.yaml`, with no questions; each learner's agent builds the questions later:

```yaml
- id: webhook-delivery                    # kebab-case, generic, never company-specific
  title: Webhook delivery                 # 40 characters or fewer
  summary: Sign payloads, retry with backoff, isolate failing endpoints, and park dead events.
  format: hands-on
  track: null                             # shared modules never link a learner's own questions
  tags: [retries, signatures]
  report_count: 0
  companies: []
  rounds: []
  reports: []
```

The summary says what the learner **builds**, in 25 words or fewer. It must be buildable in Python 3.12 with pytest, using fake clocks, fake networks, and simulated servers. Nothing should need a real cloud service.

## Add interview research

Reports are what real candidates say they were asked. They ground each module in reality.

1. Write a JSON array in `data/research/<topic>.json`. The `data/` folder is git-ignored.

   ```json
   [{"company": "Stripe", "round": "practical-coding", "level": null, "year": 2025,
     "question": "Build a rate limiter that allows N requests per user per minute, then make it work across servers.",
     "follow_ups": ["Make it thread-safe", "Share state through Redis"],
     "tags": ["rate-limiting"], "archetype": "rate-limiter",
     "sources": ["https://example.com/where-you-read-it"], "confidence": "medium"}]
   ```

   - `round` is one of `practical-coding`, `system-design`, `low-level-design`, `concurrency`, `debugging`, `api-integration`, `data-modeling`.
   - `archetype` is the id of the module the report belongs to.
   - `confidence` is `high` when 2 or more independent sources agree, `medium` for one specific source, and `low` for a vague mention.
2. Merge it with `uv run --no-project --with pyyaml python scripts/merge_catalog.py data/research/<topic>.json`. The merge dedupes and folds near-duplicate topics (see `ALIASES`).
3. Commit only `content/catalog.yaml`.

**Rules for reports**
- **Paraphrase.** Write each question in your own words, 30 words or fewer. Never copy text.
- **Cite.** Include at least one link to where the report came from.
- **Stay public.** Skip anything you saw behind a login, under an NDA, or at your own job.

## Change the app or CLI

- The code is standard-library-first Python. Keep diffs small and match the surrounding style. `ruff` enforces formatting.
- Add or update a test for any behavior you change; `tests/` has examples.
- A new dependency needs a reason in the pull request. Add it with `uv add`, and commit `uv.lock`.
- The web UI is plain HTML, CSS and JavaScript in `whetstone/static/`. Check it at desktop width and at a narrow side-pane width (under 1100px).

## Using AI to contribute

AI-assisted contributions are welcome. You are responsible for what you submit: read it, run the checks, and confirm that any research is paraphrased and cited.

## Pull requests

- Keep each pull request focused, and describe what changed and why.
- CI must pass. A maintainer reviews every change; changes to `examples/`, `scripts/`, and `.github/` get extra scrutiny because they hold code that runs.
- For security problems, follow [SECURITY.md](SECURITY.md) instead of opening an issue.

By contributing, you agree that your contribution is licensed under the [MIT License](LICENSE), and you agree to follow the [code of conduct](CODE_OF_CONDUCT.md).

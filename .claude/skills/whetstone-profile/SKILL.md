---
name: whetstone-profile
description: Set up or refresh the learner's Whetstone profile (my/profile.md) from what you know about them, their GitHub activity and their local repositories. Use on first run, when the learner says "set up my Whetstone profile", "update my profile", "refresh my profile from GitHub", or when my/profile.md has no header.
---

# Profile: learn who the learner is

Every question, review and dashboard line is tailored to `my/profile.md`. It has two parts:
- **A YAML header** that the app shows on the dashboard. Its fields are `name`, `role`, `goal`, `stack`, `focus`, `ai_handles`, `targets` and `github`.
- **Free text below the header** that agents read: their daily work, preferences and writing style.

`content/profile.example.md` is the template. The file stays on this machine and is never committed.

## 1. Gather, with consent

Start from what you already know about the learner: your memory, their earlier chats, the projects open on this machine. Then ask once:

> "Can I look at your GitHub activity and the repositories in <folder> to fill in your profile? I'll only read, and only summaries go into my/profile.md."

If they agree, collect evidence. Use whatever GitHub access you already have: the `gh` CLI, or a GitHub connector or MCP server. Never ask for a token.

- **Who they are:** `gh api user --jq '{login, name, bio, company}'`.
- **What they build:** `gh repo list --limit 100 --json name,description,primaryLanguage,pushedAt,isPrivate,isFork`. Weight repos pushed in the last 12 months, and skip forks.
- **How much, and where:** `gh api graphql -f query='{ viewer { contributionsCollection { totalCommitContributions totalPullRequestReviewContributions commitContributionsByRepository(maxRepositories: 20) { repository { nameWithOwner primaryLanguage { name } } contributions { totalCount } } } } }'`
- **What their AI writes:** count commits that carry an AI co-author trailer. In local repos, run `git log --since=6.months --author="<their email>" --format='%H %(trailers:key=Co-authored-by,valueonly)'`, and look for Claude, Copilot, Cursor, Codex and similar. Then look at which files those commits touch: tests, migrations, concurrency code, SQL, infrastructure. That shows what the learner no longer writes by hand. **This is the most useful signal you will find**, because those skills fade fastest.
- **What is missing:** for example, repos with no tests, no retries or timeouts around network calls, or no concurrency control around shared state. These are gaps to practice, not judgements. Keep the wording neutral.

Read only the learner's own account and the folders they named. Read code only to classify it. Never copy code, secrets, customer names or internal hostnames into the profile.

## 2. Propose, then write

Show the learner a draft header and three short paragraphs of free text. Wait for corrections. Then write `my/profile.md`:

```yaml
---
name: Sam
role: Senior backend engineer, marketplaces
goal: Staff-level depth in distributed systems
stack: [Python, Django, Celery, Postgres, Redis]
focus: [idempotent-api, retry-backoff, rate-limiter, task-queue-workers]
ai_handles: [tests, SQL migrations, concurrency code]
targets: [Shopify]
github: sam-dev
---
```

- **`focus`** holds module ids from `bin/whetstone catalog`, chosen from the goal, the gaps, and what their AI handles. Use 3 to 6 ids.
- **`ai_handles`** uses the learner's own words where you can.
- **`targets`** holds only companies the learner names. Never guess these.
- Keep the free text that is already there, and update it rather than replacing it.

## 3. Check

Run `bin/whetstone doctor`. It reports whether the profile header parses. Then tell the learner what changed in one or two lines, and suggest a first step with the `whetstone-curate` skill.

## Refresh

When the learner asks, or about once a month when the curator notices the profile is old, repeat steps 1 to 3 for the last 3 months only. Show the differences, for example "Your AI now writes most of your SQL". Never overwrite the profile without the learner seeing the changes first.

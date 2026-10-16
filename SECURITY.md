# Security policy

## Report a vulnerability

Please report security problems privately. Do not open a public issue.

Use GitHub's private vulnerability reporting: open the repository's **Security** tab, then click **Report a vulnerability**. Include what you found, how to reproduce it, and the impact you expect.

You should get a reply within 7 days. We fix confirmed issues on `main` and credit reporters who want it. Only the latest `main` is supported.

## What Whetstone is, from a security point of view

Whetstone is a local tool that **runs code by design**. When you press Run tests or Submit, it runs your `solution.py` and the question's tests with pytest. Keep that in mind:

- **It only answers your own machine.** The server binds to `127.0.0.1`. Every request must also have a local `Host` header and, if present, a local `Origin`, so a web page on another site cannot reach it through DNS rebinding or a cross-site request. To allow another name on purpose, for example a dev container, set `WHETSTONE_ALLOWED_HOSTS`. Do not expose Whetstone to a network.
- **Docker adds a sandbox.** With `docker compose`, submissions run inside the container as a non-root user. Without Docker, they run as you.
- **Questions are code your AI wrote.** The questions in `my/` are written by your own AI agent and run on your machine. Read what an agent writes before you run it, as you would with any generated code.
- **System designs are text, not code.** A design question's `design.md` and its whiteboard drawing are stored and shown, never run.
- **Some libraries come from public CDNs.** Your browser loads the code editor (Monaco) and the diagram renderer (Mermaid) from cdn.jsdelivr.net, and the whiteboard (Excalidraw, with React) from esm.sh, each at a fixed version. Whetstone itself sends nothing to them; they see only the request for the library file. Offline, those parts don't load, and a plain text editor stands in for Monaco.
- **Shared content is data.** `content/` is YAML and Markdown that the app reads; nothing in it is executed. The exception is `examples/`, which holds a reference question with Python code. Review changes to `examples/` and `scripts/` carefully.
- **`my/` is private.** It holds your profile, your questions and your progress, which may describe your job. It is git-ignored, and CI fails any change that tracks files under `my/` or `data/`, a `.db` file, or a `.env` file.

## Supply chain

- Python dependencies are pinned with hashes in `uv.lock`. CI and the Docker image install with `uv sync --locked`, which rejects a stale lock or a changed package.
- Docker base images are pinned by digest.
- GitHub Actions are pinned to full commit SHAs. Workflows run with a read-only or empty token, never use `pull_request_target`, and do not keep checkout credentials. `zizmor` audits them in CI.
- Dependabot proposes updates weekly, after a 7-day cooldown.
- CodeQL, dependency review, and OpenSSF Scorecard run on the repository.

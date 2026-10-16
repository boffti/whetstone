# Base images are pinned by digest so a re-tagged image cannot slip in; Dependabot proposes updates.
FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1
COPY --from=ghcr.io/astral-sh/uv:0.13.1@sha256:4a1f3666816dafadd20ceb71eac9a7d56d7ef30279f7d64048519ab901ada336 /uv /usr/local/bin/uv

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/usr/local UV_LINK_MODE=copy UV_NO_CACHE=1
WORKDIR /app

# Install exactly what uv.lock pins; uv checks every package hash and fails if the lock is stale.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

COPY . .

# Run as a normal user: submitted code runs inside this container.
RUN useradd --create-home dojo && mkdir -p /app/my && chown -R dojo /app
USER dojo

EXPOSE 8000
CMD ["python", "-m", "whetstone", "serve", "--host", "0.0.0.0", "--port", "8000"]

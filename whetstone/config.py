from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / "examples" / "memoize"  # the reference question authors and agents copy the format from


@dataclass(frozen=True)
class Settings:
    """Two roots, so `git pull` never touches what the learner's AI built for them:
    content_dir is shared and committed (catalog, paths); user_dir (my/) is personal and
    git-ignored (profile, built questions, own paths, progress). Writes only go to user_dir."""

    content_dir: Path
    user_dir: Path
    redis_url: str
    anthropic_api_key: str | None
    model: str
    run_timeout: int

    @property
    def tracks_dir(self) -> Path:
        return self.user_dir / "tracks"

    @property
    def paths_dir(self) -> Path:
        """Where new and edited paths are saved. Shared paths stay read-only."""
        return self.user_dir / "paths"

    @property
    def shared_paths_dir(self) -> Path:
        return self.content_dir / "paths"

    @property
    def staging_dir(self) -> Path:
        return self.user_dir / ".staging"

    @property
    def db_path(self) -> Path:
        return self.user_dir / "whetstone.db"

    @property
    def profile_path(self) -> Path:
        mine = self.user_dir / "profile.md"
        return mine if mine.exists() else self.content_dir / "profile.example.md"

    @property
    def generator_enabled(self) -> bool:
        return bool(self.anthropic_api_key)


def load_settings() -> Settings:
    _load_dotenv(ROOT / ".env")
    user_dir = Path(os.environ.get("WHETSTONE_HOME", ROOT / "my"))
    user_dir.mkdir(parents=True, exist_ok=True)
    return Settings(
        content_dir=Path(os.environ.get("WHETSTONE_CONTENT", ROOT / "content")),
        user_dir=user_dir,
        redis_url=os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY") or None,
        model=os.environ.get("WHETSTONE_MODEL", "claude-sonnet-5-5"),
        run_timeout=int(os.environ.get("WHETSTONE_RUN_TIMEOUT", "60")),
    )


def _load_dotenv(path: Path) -> None:
    """Read KEY=VALUE lines from .env. Real environment variables win."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

"""Tool packs: the command-line tools terminal questions use, listed in content/tools.yaml."""

from __future__ import annotations

import shutil
import subprocess

import yaml

from .config import ROOT

REGISTRY = ROOT / "content" / "tools.yaml"


def packs() -> dict[str, dict]:
    data = yaml.safe_load(REGISTRY.read_text(encoding="utf-8")) if REGISTRY.exists() else {}
    return {str(k): v for k, v in (data or {}).items() if isinstance(v, dict)}


def installed(spec: dict) -> bool:
    command = str(spec.get("check", "")).split()
    return bool(command) and shutil.which(command[0]) is not None


def missing(names: list[str]) -> list[str]:
    """What stops a question that uses these packs from running here, one line each, with the fix."""
    known, out = packs(), []
    for name in names:
        if name not in known:
            out.append(f"no tool pack named {name}: content/tools.yaml lists {', '.join(known)}")
        elif not installed(known[name]):
            out.append(f"needs {name}: add it to WHETSTONE_TOOLS in .env, then rebuild with `docker compose up -d --build`")
    return out


def version(spec: dict) -> str:
    """The first line the pack's check command prints, or "" when it is not installed."""
    if not installed(spec):
        return ""
    try:
        done = subprocess.run(str(spec["check"]).split(), capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    lines = (done.stdout or done.stderr).strip().splitlines()
    return lines[0] if lines else ""

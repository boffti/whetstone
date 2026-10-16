"""Check shared content before it is committed: catalog modules, learning paths, and privacy.

Usage: python scripts/check_content.py
Prints each problem and exits with 1 if there are any. CI runs it on every pull request.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from merge_catalog import merged  # noqa: E402

SLUG = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
ROUNDS = {"practical-coding", "system-design", "low-level-design", "concurrency", "debugging", "api-integration", "data-modeling"}
# Files that must never be committed: a learner's own folder, research caches, progress, secrets.
PERSONAL = re.compile(r"(^|/)(my|data)/|\.db$|(^|/)\.env$")


def check_catalog(catalog: dict) -> list[str]:
    out: list[str] = []
    problems = catalog.get("problems", [])
    ids = [p.get("id") for p in problems]
    out += [f"catalog: duplicate module id {i!r}" for i in sorted({i for i in ids if ids.count(i) > 1})]
    for p in problems:
        pid = p.get("id") or "?"
        where = f"catalog: {pid}"
        if not SLUG.match(pid):
            out.append(f"{where}: id must be kebab-case")
        if not p.get("title") or len(p["title"]) > 60:
            out.append(f"{where}: needs a title of 60 characters or fewer")
        if not p.get("summary"):
            out.append(f"{where}: needs a summary of what the learner builds")
        if p.get("format", "hands-on") not in ("hands-on", "design"):
            out.append(f"{where}: format must be hands-on or design")
        if p.get("track"):
            out.append(f"{where}: shared modules must not link a learner's track (set track: null)")
        reports = p.get("reports", [])
        if p.get("report_count", 0) != len(reports):
            out.append(f"{where}: report_count is out of date (run scripts/merge_catalog.py)")
        for n, r in enumerate(reports, 1):
            rw = f"{where} report {n}"
            if not r.get("company") or not r.get("question"):
                out.append(f"{rw}: needs company and question")
            if r.get("round") not in ROUNDS:
                out.append(f"{rw}: round must be one of {', '.join(sorted(ROUNDS))}")
            if r.get("confidence") not in ("high", "medium", "low"):
                out.append(f"{rw}: confidence must be high, medium or low")
            sources = r.get("sources") or []
            if not sources or any(urlsplit(s).scheme not in ("http", "https") for s in sources):
                out.append(f"{rw}: needs at least one http(s) source link")
    return out


def check_paths(paths_dir: Path, module_ids: set[str]) -> list[str]:
    out: list[str] = []
    for f in sorted(paths_dir.glob("*.yaml")):
        where = f"paths/{f.name}"
        meta = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        if not SLUG.match(f.stem):
            out.append(f"{where}: file name must be kebab-case")
        out += [f"{where}: needs {k}" for k in ("title", "goal", "domain") if not meta.get(k)]
        modules = meta.get("modules") or []
        if not modules:
            out.append(f"{where}: needs at least one module")
        out += [f"{where}: unknown module {m!r} (add it to catalog.yaml first)" for m in modules if m not in module_ids]
        out += [f"{where}: module {m!r} is listed twice" for m in sorted({m for m in modules if modules.count(m) > 1})]
        if not all(isinstance(c, str) for c in meta.get("companies", [])):
            out.append(f"{where}: companies must be a list of names")
    return out


def check_tracked_files() -> list[str]:
    try:
        files = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
    except (OSError, subprocess.CalledProcessError):
        return []  # not a git checkout: nothing is tracked
    return [f"privacy: {f} must never be committed (personal data, research cache or secrets)" for f in files if PERSONAL.search(f)]


def all_problems(root: Path = ROOT) -> list[str]:
    catalog = yaml.safe_load((root / "content/catalog.yaml").read_text(encoding="utf-8")) or {}
    out = check_catalog(catalog)
    out += check_paths(root / "content/paths", {p["id"] for p in catalog.get("problems", [])})
    if merged(catalog, []) != catalog:
        out.append("catalog: not in merged form; run `uv run --no-project --with pyyaml python scripts/merge_catalog.py`")
    return out + check_tracked_files()


if __name__ == "__main__":
    found = all_problems()
    for line in found:
        print(line)
    print(f"{len(found)} problem(s)" if found else "Content looks good.")
    sys.exit(1 if found else 0)

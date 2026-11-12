"""Builds the courier-fees repo the way it was after the accidental reset. Each test calls build()
on a fresh folder; the learner's sandbox/ is the "visible" one. build() returns what the tests
check against: the lost commits, oldest first, and the subjects of the work done since."""

from pathlib import Path

from tools import git

README = "# courier-fees\n\nPrices deliveries.\n\n## Install\n\npip install -r requirements.txt\n"
FEES = '''"""Delivery fees, in cents."""

BASE_CENTS = 199


def fee(km: float) -> int:
    return BASE_CENTS
'''
DISTANCE = FEES.replace("    return BASE_CENTS\n", "    return BASE_CENTS + round(45 * km)\n")


def _surcharge(name: str, cents: int, cap: int | None) -> list[tuple[str, dict]]:
    """The commits that add a surcharge to fees.py, then cap it."""
    added = DISTANCE + f"\n\ndef {name}_surcharge(fee_cents: int) -> int:\n    return fee_cents * {cents} // 100\n"
    out = [(f"Add {name} surcharge", {"fees.py": added})]
    if cap is not None:
        capped = added.replace(f"    return fee_cents * {cents} // 100\n", f"    return min(fee_cents * {cents} // 100, {cap})\n")
        out.append((f"Cap {name} surcharge at {cap // 100}.{cap % 100:02d}", {"fees.py": capped}))
    return out


LOST = {
    "visible": _surcharge("night", 20, 400),
    "merge": _surcharge("holiday", 15, 300),
    "three": [
        *_surcharge("rain", 10, None),
        (
            "Show surcharges on receipts",
            {"receipts.py": "def line(name: str, cents: int) -> str:\n    return f'{name}: {cents / 100:.2f}'\n"},
        ),
        ("Log every surcharge", {"audit.py": "import logging\n\nlog = logging.getLogger('surcharges')\n"}),
    ],
}


def build(path: Path, variant: str = "visible") -> dict:
    repo = git.init(path)
    git.commit(repo, "Start courier-fees", {"README.md": README, "fees.py": FEES})
    git.commit(repo, "Add distance pricing", {"fees.py": DISTANCE})
    lost = [git.commit(repo, message, files) for message, files in LOST[variant]]
    git.git(repo, "reset", "-q", "--hard", f"HEAD~{len(lost)}")  # the accident
    since = []
    if variant == "visible":
        git.commit(repo, "Fix the README's install steps", {"README.md": README.replace("pip install", "uv pip install")})
        since = ["Fix the README's install steps"]
    elif variant == "merge":  # a teammate's branch, merged as a fast-forward: it moves ORIG_HEAD
        git.git(repo, "checkout", "-q", "-b", "airport-zone")
        git.commit(repo, "Add the airport zone", {"zones.py": "ZONES = {'airport': 1.5}\n"})
        git.git(repo, "checkout", "-q", "main")
        git.git(repo, "merge", "-q", "--ff-only", "airport-zone")
        since = ["Add the airport zone"]
    else:  # work on main, then a side branch and back: HEAD moves more often than main
        git.commit(repo, "Bump the version to 1.4.1", {"VERSION": "1.4.1\n"})
        git.git(repo, "checkout", "-q", "-b", "zone-cache")
        git.commit(repo, "Try caching zones", {"cache.py": "CACHE = {}\n"})
        git.git(repo, "checkout", "-q", "main")
        git.commit(repo, "Pin requests", {"requirements.txt": "requests==2.32.3\n"})
        since = ["Pin requests", "Bump the version to 1.4.1"]
    return {"lost": lost, "lost_subjects": [m for m, _ in LOST[variant]], "since": since}

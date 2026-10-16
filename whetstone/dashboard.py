"""The personal dashboard: how sharp each skill is, honest numbers, and the game layer.

Everything here is computed from progress rows (store.progress_rows) and run facts
(Store.facts), so it is pure and easy to test. See docs/PEDAGOGY.md for why the game
rewards mastery and never volume.
"""

from __future__ import annotations

import statistics
from datetime import date, timedelta

from .content import slugify

# Sharpness: a skill's best state, dulled by time since it was last practised. The
# half-life grows with mastery, as forgetting slows for well-learned skills.
STATES = ("mastered", "clean", "assisted", "attempted")
WEIGHT = {"mastered": 1.0, "clean": 0.8, "assisted": 0.5, "attempted": 0.25}
HALF_LIFE = {"mastered": 60, "clean": 21, "assisted": 7, "attempted": 7}

# Grit ranks follow real whetstones, coarse to fine. A rank is earned once and kept;
# sharpness shows whether it is still true today.
GRITS = (
    (8000, "kept sharp through a long review"),
    (6000, "mastered"),
    (3000, "solved on your own"),
    (1000, "solved"),
    (220, "started"),
)


def row_state(r: dict) -> str | None:
    if r["mastered"]:
        return "mastered"
    if r["solve"]:
        return r["solve"]
    return "attempted" if r["status"] == "attempted" else None


def sharpness(state: str | None, last_day: str | None, today: date) -> float:
    if not state or not last_day:
        return 0.0
    days = max(0, (today - date.fromisoformat(last_day)).days)
    return round(WEIGHT[state] * 0.5 ** (days / HALF_LIFE[state]), 3)


def label(value: float, state: str | None) -> str:
    if not state:
        return "not started"
    return "sharp" if value >= 0.7 else "holding" if value >= 0.4 else "dulling" if value >= 0.15 else "dull"


def grit(rows: list[dict]) -> int | None:
    if any(r["clean_reviews"] >= 2 for r in rows):
        return 8000
    if any(r["mastered"] for r in rows):
        return 6000
    if any(r["solve"] == "clean" for r in rows):
        return 3000
    if any(r["solve"] for r in rows):
        return 1000
    return 220 if any(r["status"] == "attempted" for r in rows) else None


def _handed_to_ai(text: str, ai_handles: list[str]) -> bool:
    # Match word stems, so "concurrency code" marks "Concurrent queues" too.
    stems = {w[:6] for term in ai_handles for w in term.lower().split() if len(w) >= 4}
    return any(stem in text.lower() for stem in stems)


def edges(rows: list[dict], facts: dict, titles: dict[str, str], profile: dict, catalog: list[dict], today: date) -> list[dict]:
    """One line per skill area: modules with questions, then focus modules from the profile."""
    by_module: dict[str, list[dict]] = {}
    for r in rows:
        by_module.setdefault(r["module"], []).append(r)
    names = {slugify(p["id"]): p["title"] for p in catalog}
    ai = profile.get("ai_handles", [])
    out = []
    for module in list(by_module) + [m for m in map(slugify, profile.get("focus", [])) if m not in by_module]:
        group = by_module.get(module, [])
        states = [s for s in map(row_state, group) if s]
        best = min(states, key=STATES.index) if states else None
        last = max((facts.get(r["key"], {}).get("last_day") for r in group if facts.get(r["key"], {}).get("last_day")), default=None)
        value = sharpness(best, last, today)
        title = titles.get(module) or names.get(module) or module.replace("-", " ").capitalize()
        due = min((r["review_due"] for r in group if r["review_due"]), default=None)
        out.append(
            {
                "module": module,
                "title": title,
                "built": bool(group),
                "questions": len(group),
                "solved": sum(r["status"] == "solved" for r in group),
                "state": best,
                "sharpness": value,
                "label": label(value, best),
                "grit": grit(group),
                "last_day": last,
                "review_due": due,
                "focus": module in map(slugify, profile.get("focus", [])),
                "ai_handled": _handed_to_ai(f"{title} {module} {' '.join(t for r in group for t in r['tags'])}", ai),
            }
        )
    started = sorted((e for e in out if e["state"]), key=lambda e: -e["sharpness"])
    return started + [e for e in out if not e["state"]]


def numbers(rows: list[dict], facts: dict, today: date) -> dict:
    solved = [r for r in rows if r["solve"]]
    runs = [facts[r["key"]]["runs_to_solve"] for r in solved if facts.get(r["key"], {}).get("runs_to_solve")]
    hints = {r["key"]: facts.get(r["key"], {}).get("hints_before_solve", 0) for r in solved}
    firsts = [f["first_submit"] for f in facts.values() if f.get("first_submit")]

    def hints_per_solve(start: date, end: date) -> float | None:
        keys = [r["key"] for r in solved if start <= date.fromisoformat(r["solved_at"][:10]) < end]
        return round(sum(hints[k] for k in keys) / len(keys), 1) if len(keys) >= 2 else None

    month = timedelta(days=30)
    return {
        "solved": len(solved),
        "clean": sum(r["solve"] == "clean" for r in solved),
        "assisted": sum(r["solve"] == "assisted" for r in solved),
        "mastered": sum(r["mastered"] for r in rows),
        "median_runs": statistics.median(runs) if runs else None,
        "hints_per_solve": round(sum(hints.values()) / len(solved), 1) if solved else None,
        "hints_now": hints_per_solve(today - month, today + timedelta(days=1)),
        "hints_before": hints_per_solve(today - 2 * month, today - month),
        "first_submit_rate": round(100 * firsts.count("passed") / len(firsts)) if firsts else None,
        "first_submits": len(firsts),
    }


def predictions(store, today: date) -> dict:
    """Share of test results guessed right before runs: this month, and the month before."""
    month = timedelta(days=30)
    end = today + timedelta(days=1)
    now = store.prediction_rate(end - month, end)
    before = store.prediction_rate(end - 2 * month, end - month)
    rate = lambda r: round(100 * r[0] / r[1]) if r[1] else None  # noqa: E731
    return {"predict_now": rate(now), "predict_before": rate(before), "predicted": now[1]}


def milestones(rows: list[dict], facts: dict, week: dict) -> list[dict]:
    """Earned for habits that predict learning, each saying what the learner can now do."""
    out = []
    by_time = sorted((r for r in rows if r["solved_at"]), key=lambda r: r["solved_at"])

    def first(test, title, detail):
        r = next((r for r in by_time if test(r)), None)
        if r:
            out.append({"title": title, "detail": detail(r), "at": r["solved_at"][:10]})

    hints = lambda r: facts.get(r["key"], {}).get("hints_before_solve", 0)  # noqa: E731
    first(lambda r: r["solve"] == "clean", "Solved one on your own", lambda r: r["title"])
    first(
        lambda r: r["solve"] == "clean" and not hints(r) and facts.get(r["key"], {}).get("first_submit") == "passed",
        "First Submit, no hints",
        lambda r: f"{r['title']} passed every hidden test on the first try",
    )
    first(
        lambda r: r["type"] == "fix" and r["solve"] == "clean" and not hints(r), "Fixed a bug from the report alone", lambda r: r["title"]
    )
    first(lambda r: r["clean_reviews"] >= 1, "Passed a spaced review", lambda r: f"{r['title']} came back as a variant, and it stuck")
    first(lambda r: r["mastered"], "Mastered a skill", lambda r: r["title"])
    first(
        lambda r: r["solve"] == "clean" and r["key"].split("/")[1].startswith("05-"),
        "Beat a boss",
        lambda r: f"{r['title']}: the adversary question of its module",
    )
    if week.get("repaired"):
        out.append({"title": "Came back after a missed week", "detail": "Your weekly streak kept going", "at": None})
    return out


def records(rows: list[dict], facts: dict, days: list[str], target: int) -> dict:
    run, best_run = 0, 0
    for r in sorted((r for r in rows if r["solved_at"]), key=lambda r: r["solved_at"]):
        run = run + 1 if r["solve"] == "clean" else 0
        best_run = max(best_run, run)
    fastest = min(
        (
            (facts[r["key"]]["runs_to_solve"], r["title"])
            for r in rows
            if r["solve"] == "clean" and facts.get(r["key"], {}).get("runs_to_solve")
        ),
        default=None,
    )
    weeks: dict[date, int] = {}
    for d in map(date.fromisoformat, days):
        monday = d - timedelta(days=d.weekday())
        weeks[monday] = weeks.get(monday, 0) + 1
    best_weeks, streak, prev = 0, 0, None
    for monday in sorted(w for w, n in weeks.items() if n >= target):
        streak = streak + 1 if prev and monday - prev == timedelta(days=7) else 1
        best_weeks, prev = max(best_weeks, streak), monday
    return {
        "clean_in_a_row": best_run,
        "fewest_runs": {"runs": fastest[0], "title": fastest[1]} if fastest else None,
        "best_weekly_streak": best_weeks,
    }


def targets(profile: dict, catalog: list[dict], built: set[str]) -> list[dict]:
    """For each company the learner cares about: what it asks, and how much is ready to practise."""
    out = []
    for company in profile.get("targets", []):
        asked = [p for p in catalog if any(r.get("company", "").lower() == company.lower() for r in p.get("reports", []))]
        ready = [p for p in asked if slugify(p["id"]) in built or (p.get("track") or "").split("/")[0] in built]
        out.append({"company": company, "problems": len(asked), "ready": len(ready)})
    return out

from datetime import date

from whetstone import dashboard as dash

TODAY = date(2026, 10, 30)


def row(key, status="new", solve=None, solved_at=None, mastered=False, clean_reviews=0, kind="build", title=None):
    return {
        "key": key,
        "module": key.split("/")[0],
        "title": title or key,
        "type": kind,
        "tags": [],
        "status": status,
        "solve": solve,
        "solved_at": solved_at,
        "mastered": mastered,
        "clean_reviews": clean_reviews,
        "review_due": None,
    }


def test_sharpness_dulls_with_time_and_lasts_longer_when_mastered():
    assert dash.sharpness("clean", "2026-10-30", TODAY) == 0.8
    assert dash.sharpness("clean", "2026-10-09", TODAY) == 0.4, "a clean solve halves in 3 weeks"
    assert dash.sharpness("mastered", "2026-10-09", TODAY) > 0.75, "mastery fades slowly"
    assert dash.sharpness(None, None, TODAY) == 0
    assert [dash.label(v, "clean") for v in (0.8, 0.5, 0.2, 0.05)] == ["sharp", "holding", "dulling", "dull"]


def test_grit_is_earned_by_mastery_not_volume():
    assert dash.grit([row("m/01", "attempted")] * 20) == 220, "many attempts stay at the coarsest grit"
    assert dash.grit([row("m/01", "solved", "assisted", "2026-10-01T10:00:00")]) == 1000
    assert dash.grit([row("m/01", "solved", "clean", "2026-10-01T10:00:00")]) == 3000
    assert dash.grit([row("m/01", "solved", "clean", "2026-10-01T10:00:00", mastered=True)]) == 6000
    assert dash.grit([row("m/01", "solved", "clean", "2026-10-01T10:00:00", mastered=True, clean_reviews=2)]) == 8000


def test_edges_put_practiced_skills_first_and_add_focus_modules():
    rows = [row("caching/01", "solved", "clean", "2026-10-29T10:00:00"), row("queues/01", "attempted")]
    facts = {"caching/01": {"last_day": "2026-10-29"}, "queues/01": {"last_day": "2026-10-01"}}
    profile = {"focus": ["rate-limiter"], "ai_handles": ["concurrency code"]}
    catalog = [{"id": "rate-limiter", "title": "Rate limiter", "reports": []}]
    lines = dash.edges(rows, facts, {"caching": "Caching", "queues": "Concurrent queues"}, profile, catalog, TODAY)
    assert [e["module"] for e in lines] == ["caching", "queues", "rate-limiter"]
    assert (lines[2]["title"], lines[2]["label"], lines[2]["built"]) == ("Rate limiter", "not started", False)
    assert lines[1]["ai_handled"], "skills the learner's AI writes at work are marked"


def test_milestones_and_records_reward_learning_habits():
    rows = [
        row("m/01", "solved", "clean", "2026-10-01T10:00:00", title="Cache"),
        row("m/02", "solved", "assisted", "2026-10-02T10:00:00", title="Mutex"),
        row("m/04", "solved", "clean", "2026-10-03T10:00:00", kind="fix", title="Lost ack"),
        row("m/05-boss", "solved", "clean", "2026-10-04T10:00:00", title="Retry storm"),
    ]
    facts = {
        "m/01": {"runs_to_solve": 4, "first_submit": "failed", "hints_before_solve": 1},
        "m/04": {"runs_to_solve": 2, "first_submit": "passed"},
        "m/05-boss": {"runs_to_solve": 3, "first_submit": "passed"},
    }
    titles = [m["title"] for m in dash.milestones(rows, facts, {"repaired": True})]
    assert titles == [
        "Solved one on your own",
        "First Submit, no hints",
        "Fixed a bug from the report alone",
        "Beat a boss",
        "Came back after a missed week",
    ]

    days = ["2026-09-28", "2026-09-29", "2026-09-30", "2026-10-05", "2026-10-06", "2026-10-07", "2026-10-19", "2026-10-20", "2026-10-21"]
    rec = dash.records(rows, facts, days, target=3)
    assert rec == {"clean_in_a_row": 2, "fewest_runs": {"runs": 2, "title": "Lost ack"}, "best_weekly_streak": 2}

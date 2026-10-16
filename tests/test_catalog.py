from pathlib import Path

from whetstone.catalog import build_notes, catalog_links
from whetstone.content import Challenge, Track


def _track(track_id: str, *dirs: str) -> Track:
    t = Track(id=track_id, title=track_id.title(), description="", path=Path("."))
    t.challenges = [Challenge(track_id, d, Path("."), f"Title {d}", "medium", 20, [], [], [], None, "") for d in dirs]
    return t


def test_links_curated_challenge_then_own_track():
    tracks = {t.id: t for t in [_track("cc", "01-a", "05-lru"), _track("lru-ttl-cache", "01-x", "02-y")]}
    links = catalog_links({"id": "lru-ttl-cache", "track": "cc/05-lru"}, tracks, solved={"lru-ttl-cache/01-x"})
    assert [(lk["track"], lk["challenge"], lk["own"]) for lk in links] == [("cc", "05-lru", False), ("lru-ttl-cache", "02-y", True)]
    assert links[0]["title"] == "Title 05-lru" and links[1]["solved"] == 1


def test_links_skip_missing_and_dedupe():
    tracks = {"rate-limiter": _track("rate-limiter", "01-a")}
    assert catalog_links({"id": "nothing-built"}, tracks, set()) == []
    links = catalog_links({"id": "rate-limiter", "track": "rate-limiter"}, tracks, set())
    assert len(links) == 1 and links[0]["own"]


def test_build_notes_lists_reports():
    notes = build_notes({"reports": [{"company": "Stripe", "round": "practical-coding", "question": "Q1", "follow_ups": ["F1"]}]})
    assert "Stripe (practical-coding): Q1 Follow-ups: F1" in notes

"""Merge research JSON files into content/catalog.yaml.

Usage: python scripts/merge_catalog.py data/research/*.json

Each JSON file is a list of reports: {company, round, level, year, question,
follow_ups, tags, archetype, sources, confidence}. Reports are grouped into
problems by archetype. Re-running keeps each problem's hand-written title,
summary and track, and only recomputes its reports, companies and counts.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

import yaml

CATALOG = Path(__file__).resolve().parent.parent / "content" / "catalog.yaml"
RANK = {"high": 0, "medium": 1, "low": 2}
COMPUTED = ("report_count", "companies", "rounds", "tags", "reports")

# Folds narrow archetype slugs into the broader problems the catalog shows.
ALIASES = {
    "rules-engine": ["rule-engine-parser", "record-validator-rules", "pricing-rules-engine", "coupon-pricing-engine"],
    "access-control": [
        "permission-graph-reachability",
        "hierarchical-access-check",
        "acl-inheritance",
        "rbac-access-control",
        "ip-cidr-firewall",
    ],
    "coupon-redemption": ["promotion-redemption"],
    "ledger": ["double-entry-ledger", "expiring-credit-ledger", "deposit-settlement-ledger"],
    "inventory-reservation": ["reservation-booking", "quota-service", "fractional-share-inventory"],
    "order-state-machine": ["order-lifecycle-manager"],
    "ood-modeling": ["ood-parking-elevator", "todo-list-ood", "music-player-ood", "browser-history", "fare-calculator"],
    "ood-games": [
        "card-game-ood",
        "game-ood-2048",
        "jigsaw-puzzle-ood",
        "tic-tac-toe-engine",
        "chess-engine",
        "card-purchase-simulator",
        "grid-simulation-rover",
    ],
    "editor-undo": ["text-editor-undo", "undoable-rectangle-board", "design-document-model", "ascii-canvas", "design-editor-model"],
    "payroll-time-tracking": ["employee-time-tracker", "driver-payroll-tracker"],
    "interval-scheduling": ["interval-window-scheduler", "interval-gaps-over-api", "schedule-availability-query", "calendar-scheduling"],
    "query-engine": ["mini-sql-engine", "cursor-pagination-query", "boolean-document-search"],
    "url-router": ["url-router-trie"],
    "concurrent-writer": ["concurrent-file-logger", "wal-batch-writer", "buffered-writer", "logging-library"],
    "distributed-algorithms": ["distributed-tree-count", "distributed-aggregate"],
    "log-csv-aggregation": ["csv-reconciliation", "payment-invoice-matcher", "recurring-transaction-detector"],
    "event-stream-processing": ["streaming-query-matcher", "event-stream-fraud-state", "trace-span-tree", "stack-samples-to-trace-events"],
    "graph-relationships": ["referral-leaderboard", "referral-revenue-tracker", "org-hierarchy-lca", "snapshot-follow-graph"],
    "task-manager-quotas": ["task-management-ttl"],
    "parsers-codecs": [
        "header-parsing",
        "json-parser",
        "tokenizer-longest-match",
        "function-signature-matcher",
        "rle-bitpack-codec",
        "tail-n-file",
        "range-file-cache-client",
    ],
    "ai-assisted-build": ["repo-feature-extension", "text-rendering-cli"],
    "geo-matching": ["dispatch-matching", "food-delivery-backend"],
    "decomposition": ["data-product-decomposition", "dispatch-decomposition"],
    "ratings-reviews": ["rating-aggregator", "review-voting-system"],
    "data-structure-design": ["lazy-array", "random-queue", "mempool-block-assembly"],
    "api-integration": ["fanout-price-aggregator"],
    "task-queue-workers": ["workflow-engine-dag", "parallel-batch-processor"],
    "time-window-metrics": ["device-fleet-monitor", "log-collection-pipeline", "observability-pipeline-design"],
    "file-sync-dedup": ["resumable-upload"],
    "in-memory-file-system": ["fs-tree-cost-optimization"],
    "url-shortener": ["temp-email-service"],
    "versioned-kv-store": ["encrypted-kv-store"],
    "top-k-streaming": ["scored-playlist-rotation"],
    "retry-backoff": ["circuit-breaker"],
    "thread-safe-memo-cache": ["distributed-lock"],
    # Learning-path modules (2026-10-15): one module per idea across domains.
    "inverted-index": ["inverted-index-search", "keyword-search"],
    "experiment-assignment": ["experiment-bucketing"],
    "position-keeping": ["position-tracking"],
    "durable-workflow": ["workflow-dag"],
    "dependency-dag": ["incremental-build"],
    "failure-detector": ["health-checking"],
    "windowing-watermarks": ["windowed-aggregation"],
}
ALIAS_OF = {old: new for new, olds in ALIASES.items() for old in olds}


def norm_report(r: dict) -> dict:
    slug = (r.get("archetype") or "uncategorized").strip().lower()
    slug = slug.removeprefix("new:").strip()
    slug = ALIAS_OF.get(slug, slug)
    return {
        "company": (r.get("company") or "Unknown").strip(),
        "round": (r.get("round") or "practical-coding").strip(),
        "level": r.get("level") or None,
        "year": r.get("year") or None,
        "question": " ".join((r.get("question") or "").split()),
        "follow_ups": [f for f in (r.get("follow_ups") or []) if f],
        "tags": sorted({t.strip().lower() for t in (r.get("tags") or []) if t}),
        "archetype": slug,
        "sources": sorted({s for s in (r.get("sources") or []) if s}),
        "confidence": r.get("confidence") if r.get("confidence") in RANK else "low",
    }


def same(a: dict, b: dict) -> bool:
    if a["company"].lower() != b["company"].lower() or a["archetype"] != b["archetype"]:
        return False
    ratio = SequenceMatcher(None, a["question"].lower(), b["question"].lower()).ratio()
    # A shared URL alone is not enough: aggregator pages list many questions.
    shared = set(a["sources"]) & set(b["sources"])
    return ratio > 0.75 or (bool(shared) and ratio > 0.5)


def merge_into(keep: dict, dup: dict) -> None:
    keep["sources"] = sorted(set(keep["sources"]) | set(dup["sources"]))
    keep["tags"] = sorted(set(keep["tags"]) | set(dup["tags"]))
    keep["follow_ups"] += [f for f in dup["follow_ups"] if f not in keep["follow_ups"]]
    keep["confidence"] = min(keep["confidence"], dup["confidence"], key=RANK.get)
    if len(keep["sources"]) >= 2 and keep["confidence"] == "medium":
        keep["confidence"] = "high"
    keep["year"] = keep["year"] or dup["year"]
    keep["level"] = keep["level"] or dup["level"]


def dedupe(reports: list[dict]) -> list[dict]:
    # ponytail: O(n^2) pairwise compare, fine below a few thousand reports
    out: list[dict] = []
    for r in reports:
        match = next((k for k in out if same(k, r)), None)
        if match:
            merge_into(match, r)
        else:
            out.append(r)
    return out


def build(reports: list[dict], existing: dict) -> dict:
    old = {p["id"]: p for p in existing.get("problems", [])}
    groups: dict[str, list[dict]] = {}
    for r in reports:
        groups.setdefault(r["archetype"], []).append(r)
    problems = []
    for slug, rs in groups.items():
        rs.sort(key=lambda r: (RANK[r["confidence"]], -(r["year"] or 0), r["company"]))
        # Hand-written fields (title, summary, track, ...) survive a re-run.
        kept = {k: v for k, v in old.get(slug, {}).items() if k not in COMPUTED and k != "id"}
        companies = Counter(r["company"] for r in rs)
        tags = Counter(t for r in rs for t in r["tags"])
        problems.append(
            {
                "id": slug,
                "title": slug.replace("-", " ").capitalize(),
                "summary": "",
                "track": None,
                **kept,
                "report_count": len(rs),
                "companies": [c for c, _ in companies.most_common()],
                "rounds": sorted({r["round"] for r in rs}),
                "tags": [t for t, _ in tags.most_common(8)],
                "reports": [{k: v for k, v in r.items() if k != "archetype"} for r in rs],
            }
        )
    # Placeholder modules (no reports yet) stay: learning paths are built from them.
    for pid, prev in old.items():
        if pid not in groups:
            problems.append({**prev, "report_count": 0, "companies": [], "rounds": [], "reports": []})
    problems.sort(key=lambda p: (-p["report_count"], p["id"]))
    return {"problems": problems}


def merged(existing: dict, new_reports: list[dict]) -> dict:
    """The catalog after merging new reports into an existing one. Pure: writes nothing."""
    reports = [{**r, "archetype": p["id"]} for p in existing.get("problems", []) for r in p.get("reports", [])]
    reports = dedupe([norm_report(r) for r in reports + new_reports if r.get("question")])
    return build(reports, existing)


def main(paths: list[str]) -> None:
    existing = (yaml.safe_load(CATALOG.read_text()) if CATALOG.exists() else {}) or {}
    new_reports = [r for path in paths for r in json.loads(Path(path).read_text())]
    catalog = merged(existing, new_reports)
    CATALOG.write_text(yaml.safe_dump(catalog, sort_keys=False, allow_unicode=True, width=100))
    n = sum(p["report_count"] for p in catalog["problems"])
    print(f"{n} reports in {len(catalog['problems'])} problems -> {CATALOG}")


def _check() -> None:
    a = norm_report(
        {
            "company": "Stripe",
            "archetype": "new:Rate-Limiter",
            "question": "Build a rate limiter for an API",
            "sources": ["u1"],
            "confidence": "medium",
        }
    )
    b = norm_report(
        {
            "company": "stripe",
            "archetype": "rate-limiter",
            "question": "Build a rate limiter for an API.",
            "sources": ["u2"],
            "confidence": "medium",
        }
    )
    c = norm_report({"company": "Uber", "archetype": "rate-limiter", "question": "Build a rate limiter for an API", "sources": ["u3"]})
    assert a["archetype"] == "rate-limiter"
    assert norm_report({"archetype": "new:ip-cidr-firewall", "question": "q"})["archetype"] == "access-control"
    out = dedupe([a, b, c])
    assert len(out) == 2 and out[0]["sources"] == ["u1", "u2"] and out[0]["confidence"] == "high"
    d = norm_report(
        {"company": "Uber", "archetype": "rate-limiter", "question": "Design a sliding window log for per-user quotas", "sources": ["u3"]}
    )
    assert len(dedupe([c, d])) == 2, "same listing page, different questions"
    cat = build(
        out,
        {
            "problems": [
                {"id": "rate-limiter", "title": "Kept title", "track": "t/1"},
                {"id": "order-book", "title": "Order book", "tags": ["matching"]},
            ]
        },
    )
    p = cat["problems"][0]
    assert p["title"] == "Kept title" and p["track"] == "t/1" and p["report_count"] == 2
    stub = next(p for p in cat["problems"] if p["id"] == "order-book")
    assert (stub["report_count"], stub["tags"]) == (0, ["matching"]), "placeholder modules survive a merge"


if __name__ == "__main__":
    _check()
    main(sys.argv[1:])

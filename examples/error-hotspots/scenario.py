"""Builds one quotes-api server's nginx log folder, as on-call copied it. Each test calls build() on a
fresh folder; the learner's sandbox/ is the "visible" one, and "today" is its access.log alone.
build() returns what the tests compare against, worked out from the requests it wrote: the three
paths with the most 5xx responses across every access log in the folder, as the script prints them."""

from __future__ import annotations

import gzip
import random
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import NamedTuple

TODAY = datetime(2026, 11, 7, tzinfo=UTC)
GATEWAY = ["10.20.0.4", "10.20.0.7"]  # the partner gateway: X-Forwarded-For then holds two addresses
FAILURES = [500, 502, 503, 504]
PAGE = {400: 157, 401: 179, 404: 153, 429: 169, 500: 177, 502: 157, 503: 197, 504: 167}  # nginx's error pages, in bytes
TLS_HELLO = r"\x16\x03\x01\x02\x00\x01\x00\x01\xFC\x03\x03"  # a TLS handshake sent to the HTTP port, as nginx logs it

# path: (method, query parameter or None, share of healthy traffic)
ROUTES = {
    "/v1/quotes": ("GET", "zip", 30),
    "/v1/quotes/compare": ("POST", None, 8),
    "/v1/rates": ("GET", "state", 14),
    "/v1/policies": ("GET", "id", 10),
    "/v1/payments": ("POST", None, 6),
    "/v1/auth/token": ("POST", None, 8),
    "/v1/documents": ("POST", None, 4),
    "/healthz": ("GET", None, 10),
}
QUERY = {  # a value for each query parameter
    "zip": lambda rng: f"{rng.randint(1000, 99950):05d}",
    "state": lambda rng: rng.choice(["NY", "TX", "CA", "FL", "OH"]),
    "id": lambda rng: f"pol_{rng.randint(10000, 99999)}",
}
AGENTS = [
    "Larkmoor-iOS/5.12.1 (iPhone15,3; iOS 18.1)",
    "Larkmoor-Android/5.12.0 okhttp/4.12.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "PartnerHub/2.4 (+https://partners.example/bot)",
]


class Hit(NamedTuple):
    addr: str
    request: str
    status: int
    size: int
    agent: str


def _client(rng: random.Random) -> str:
    return f"{rng.choice(['198.51.100', '203.0.113', '192.0.2'])}.{rng.randint(2, 254)}"


def _hit(rng: random.Random, path: str, status: int, *, via_gateway: float = 0.0, size: int | None = None) -> Hit:
    method, key, _ = ROUTES[path]
    target = path
    if key and rng.random() < 0.8:
        target += f"?{key}={QUERY[key](rng)}"
    addr = _client(rng)
    if rng.random() < via_gateway:
        addr += f", {rng.choice(GATEWAY)}"
    if size is None:
        size = PAGE.get(status) or (2 if path == "/healthz" else 0 if status == 304 else rng.randint(600, 4800))
    agent = "kube-probe/1.30" if path == "/healthz" else rng.choice(AGENTS)
    return Hit(addr, f"{method} {target} HTTP/1.1", status, size, agent)


def _healthy(rng: random.Random, n: int) -> list[Hit]:
    """Ordinary traffic: no 5xx, some 4xx, and some of it through the partner gateway."""
    paths = rng.choices(list(ROUTES), [w for _, _, w in ROUTES.values()], k=n)
    statuses = rng.choices([200, 201, 304, 400, 401, 404, 429], [70, 6, 6, 3, 4, 7, 4], k=n)
    hits = []
    for p, s in zip(paths, statuses, strict=True):
        method = ROUTES[p][0]
        if p == "/healthz" or (s == 201 and method == "GET") or (s == 304 and method == "POST"):
            s = 200
        hits.append(_hit(rng, p, s, via_gateway=0.15))
    hits += [Hit(_client(rng), "-", 400, 0, "-") for _ in range(2)]  # connected, then sent nothing
    hits.append(Hit(_client(rng), TLS_HELLO, 400, PAGE[400], "-"))
    return hits


def _not_found(rng: random.Random) -> list[Hit]:
    """A broken link in an email sends people to the 571-byte 404 page; rates answers are about 550 bytes."""
    hits = [_hit(rng, "/v1/policies", 404, size=571) for _ in range(12)]
    hits += [_hit(rng, "/v1/auth/token", 429) for _ in range(8)]
    return hits + [_hit(rng, "/v1/rates", 200, size=rng.randint(500, 599)) for _ in range(10)]


def _probes(rng: random.Random) -> list[Hit]:
    """Scanners and a broken client: requests that are not a method, a path and a protocol."""
    hits = [Hit(_client(rng), "-", 400, 0, "-") for _ in range(8)]
    hits += [Hit(_client(rng), TLS_HELLO, 400, PAGE[400], "-") for _ in range(4)]
    hits += [Hit(_client(rng), "GET /v1/payments", 502, PAGE[502], "-") for _ in range(4)]  # HTTP/0.9: no protocol
    return hits + [Hit(_client(rng), "GET /v1/documents?name=q3 report.pdf HTTP/1.1", 500, PAGE[500], rng.choice(AGENTS)) for _ in range(4)]


QUIRKS = {"not-found": _not_found, "probes": _probes}


def _day(rng: random.Random, fails: dict[str, int], *, gateway: dict | None = None, quirk: str = "", healthy: int = 220) -> list[Hit]:
    """One day's requests, in a random order: `fails` 5xx responses per path, on top of healthy traffic."""
    hits = [_hit(rng, path, rng.choice(FAILURES)) for path, n in fails.items() for _ in range(n)]
    hits += [_hit(rng, path, rng.choice(FAILURES), via_gateway=1.0) for path, n in (gateway or {}).items() for _ in range(n)]
    hits += _healthy(rng, healthy) + (QUIRKS[quirk](rng) if quirk else [])
    rng.shuffle(hits)
    return hits


# variant: {file name: the day it holds, or None for an empty file}. Stage 1's variants have
# access.log only; stage 2's have rotated days too: access.log.1 is plain, older ones are gzipped.
DAYS: dict[str, dict[str, dict | None]] = {
    "visible": {
        "access.log": {"fails": {"/v1/quotes": 13, "/v1/payments": 8, "/v1/rates": 6, "/v1/quotes/compare": 3, "/v1/auth/token": 2}},
        "access.log.1": {"fails": {"/v1/payments": 9, "/v1/quotes": 2, "/v1/policies": 1}},
        "access.log.2.gz": {"fails": {"/v1/documents": 12, "/v1/payments": 1}},
        "access.log.3.gz": {"fails": {"/v1/documents": 7, "/v1/rates": 1}},
    },
    "ties": {"access.log": {"fails": {"/v1/rates": 8, "/v1/quotes": 8, "/v1/policies": 5, "/v1/payments": 5, "/v1/auth/token": 5}}},
    "busy": {"access.log": {"fails": {"/v1/payments": 23, "/v1/policies": 11, "/v1/quotes": 9, "/v1/rates": 4, "/v1/documents": 3}}},
    "gateway": {"access.log": {"fails": {"/v1/quotes": 7, "/v1/rates": 5, "/v1/payments": 4}, "gateway": {"/v1/quotes/compare": 16}}},
    "not-found": {"access.log": {"fails": {"/v1/quotes": 6, "/v1/payments": 4, "/v1/documents": 2, "/v1/rates": 1}, "quirk": "not-found"}},
    "probes": {"access.log": {"fails": {"/v1/quotes": 6, "/v1/rates": 5, "/v1/payments": 3, "/v1/documents": 2}, "quirk": "probes"}},
    "few": {"access.log": {"fails": {"/v1/payments": 3, "/v1/quotes": 1}}},
    "calm": {"access.log": {"fails": {}}},
    "week": {
        "access.log": {"fails": {"/v1/quotes": 4, "/v1/rates": 2}, "healthy": 120},
        "access.log.1": {"fails": {"/v1/quotes": 3}, "healthy": 120},
        "access.log.2.gz": {"fails": {"/v1/rates": 2}, "healthy": 120},
        "access.log.3.gz": {"fails": {"/v1/payments": 1}, "healthy": 120},
        "access.log.4.gz": {"fails": {"/v1/policies": 6}, "healthy": 120},
        "access.log.5.gz": {"fails": {"/v1/policies": 5, "/v1/payments": 2}, "healthy": 120},
        "access.log.6.gz": {"fails": {"/v1/auth/token": 9}, "healthy": 120},
        "access.log.7.gz": {"fails": {"/v1/auth/token": 4, "/v1/quotes": 1}, "healthy": 120},
    },
    "fresh": {  # up for two days, just after midnight: today's log is still empty, nothing gzipped yet
        "access.log": None,
        "access.log.1": {"fails": {"/v1/payments": 5, "/v1/rates": 2, "/v1/quotes": 2, "/v1/policies": 1}},
    },
}


def _line(hit: Hit, when: datetime) -> str:
    referer = "https://www.larkmoor.example/quote" if hit.agent.startswith("Mozilla") else "-"
    stamp = when.strftime("%d/%b/%Y:%H:%M:%S +0000")
    return f'{hit.addr} - - [{stamp}] "{hit.request}" {hit.status} {hit.size} "{referer}" "{hit.agent}"\n'


def _top(hits: list[Hit]) -> list[str]:
    """What the script should print: 5xx responses per path, query cut, most first, ties by path in byte order."""
    failed = Counter()
    for hit in hits:
        words = hit.request.split()
        if len(words) == 3 and 500 <= hit.status <= 599:
            failed[words[1].split("?")[0]] += 1
    ranked = sorted(failed.items(), key=lambda item: (-item[1], item[0].encode()))
    return [f"{n} {path}" for path, n in ranked[:3]]


def build(path: Path, variant: str = "visible") -> dict:
    path.mkdir(parents=True, exist_ok=True)
    days = {"access.log": DAYS["visible"]["access.log"]} if variant == "today" else DAYS[variant]
    source = "visible" if variant == "today" else variant
    written: list[Hit] = []
    for age, (name, spec) in enumerate(days.items()):
        rng = random.Random(f"{source}/{name}")
        hits = _day(rng, **spec) if spec is not None else []
        start = TODAY - timedelta(days=age)
        times = sorted(start + timedelta(seconds=rng.randrange(86400)) for _ in hits)
        text = "".join(_line(hit, when) for hit, when in zip(hits, times, strict=True)).encode()
        if name.endswith(".gz"):  # mtime=0 and no file name: the same bytes on every run
            with open(path / name, "wb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as gz:
                gz.write(text)
        else:
            (path / name).write_bytes(text)
        written += hits
    return {"top": _top(written)}

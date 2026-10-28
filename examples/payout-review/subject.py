"""Nightly merchant payouts: one bank transfer per merchant for what they earned on
a day, their captured payments minus their refunds. Amounts are integer cents in
USD, and a refund is stored as a payment with a negative amount."""

import logging
import uuid
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from time import sleep
from typing import Protocol

import requests

log = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
BACKOFF_SECONDS = 2.0


@dataclass(frozen=True)
class Payment:
    id: str
    merchant_id: str
    amount_cents: int  # negative for a refund
    captured_at: datetime  # timezone-aware, UTC


class PaymentStore(Protocol):
    def unsettled_payments(self) -> Iterable[Payment]: ...
    def mark_settled(self, payment_ids: list[str], transfer_id: str) -> None: ...


class GatewayClient:
    """Client for the bank gateway's transfer API."""

    def __init__(self, session: requests.Session, base_url: str) -> None:
        self.session = session
        self.base_url = base_url.rstrip("/")

    def create_transfer(self, merchant_id: str, amount_cents: int, reference: str) -> str:
        """Send one transfer and return its id. Retries connection errors and 5xx
        responses with backoff; the Idempotency-Key header makes that safe, because
        the gateway returns the first transfer instead of making a second one."""
        body = {"merchant_id": merchant_id, "amount": amount_cents, "currency": "usd", "reference": reference}
        for attempt in range(MAX_ATTEMPTS):
            if attempt:
                sleep(BACKOFF_SECONDS * 2**attempt)
            headers = {"Idempotency-Key": str(uuid.uuid4())}
            try:
                resp = self.session.post(f"{self.base_url}/transfers", json=body, headers=headers)
            except requests.ConnectionError:
                log.warning("gateway unreachable (attempt %d of %d)", attempt + 1, MAX_ATTEMPTS)
                continue
            if resp.status_code < 500:
                resp.raise_for_status()
                return resp.json()["id"]
            log.warning("gateway returned %d (attempt %d of %d)", resp.status_code, attempt + 1, MAX_ATTEMPTS)
        raise RuntimeError(f"transfer to {merchant_id} failed after {MAX_ATTEMPTS} attempts")


def group_by_merchant(payments: Iterable[Payment], day: date) -> dict[str, list[Payment]]:
    """The payments captured on `day` (UTC), grouped by merchant."""
    groups: dict[str, list[Payment]] = defaultdict(list)
    start = datetime(day.year, day.month, day.day, tzinfo=UTC)
    end = start + timedelta(days=1)
    for payment in payments:
        if start < payment.captured_at < end:
            groups[payment.merchant_id].append(payment)
    return groups


def run_payouts(store: PaymentStore, gateway: GatewayClient, day: date) -> dict[str, str]:
    """Pay every merchant their net earnings for `day`; return merchant id -> transfer id.
    Safe to run again after a crash: settled payments drop out, and the gateway
    will not repeat a transfer it has already made."""
    transfers: dict[str, str] = {}
    for merchant_id, payments in sorted(group_by_merchant(store.unsettled_payments(), day).items()):
        net = sum(p.amount_cents for p in payments)
        if net <= 0:
            log.info("no payout for %s: net %d cents; finance collects negatives", merchant_id, net)
            continue
        transfer_id = gateway.create_transfer(merchant_id, net, reference=f"payout {day.isoformat()}")
        store.mark_settled([p.id for p in payments], transfer_id)
        transfers[merchant_id] = transfer_id
    return transfers

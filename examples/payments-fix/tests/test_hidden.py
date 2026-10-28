import time

import solution
from gateway import FakeGateway
from solution import Payment, PaymentRunner


def test_a_lost_reply_is_charged_once_for_any_customer_and_day():
    # Not the reported case: another day, another customer in the middle of the queue, two lost replies in a row.
    gateway = FakeGateway(faults={7: ["lost-ack", "lost-ack"]})
    due = [
        Payment("pay-0401-5", 5, 2500, "2026-04-01"),
        Payment("pay-0401-7", 7, 1200, "2026-04-01"),
        Payment("pay-0401-9", 9, 800, "2026-04-01"),
    ]
    report = PaymentRunner(gateway).run(due)
    ok = gateway.charged(7) == [1200] and set(report.values()) == {"paid"}
    assert ok, (
        "Customer 7 lost two replies on 2026-04-01 and was not charged exactly once, as paid. "
        "A fix must hold for every payment, not only the one in the report."
    )


def test_a_request_that_never_arrived_is_tried_again():
    gateway = FakeGateway(faults={42: ["lost-request"]})
    report = PaymentRunner(gateway).run([Payment("pay-0301-42", 42, 4999, "2026-03-01")])
    ok = report == {"pay-0301-42": "paid"} and gateway.charged(42) == [4999]
    assert ok, (
        "The first request never reached the gateway, and the payment was not collected in this run. "
        "Giving up after a timeout is not safe either. What would make another try safe?"
    )


def test_two_payments_for_one_customer_on_one_day_are_both_collected():
    # Two seats on the same plan: same customer, same amount, same day, two payments.
    gateway = FakeGateway()
    due = [
        Payment("pay-0301-42", 42, 4999, "2026-03-01"),
        Payment("pay-0301-42-seat2", 42, 4999, "2026-03-01"),
    ]
    report = PaymentRunner(gateway).run(due)
    ok = gateway.charged(42) == [4999, 4999] and set(report.values()) == {"paid"}
    assert ok, (
        "Customer 42 had two payments due on one day, and the gateway does not hold one charge for each. "
        "What tells one payment apart from another?"
    )


def test_a_payment_tried_again_in_the_next_run_is_not_charged_again():
    # Run 1: the charge goes through but its reply is lost; then the gateway stops answering.
    gateway = FakeGateway(faults={42: ["lost-ack", "lost-request", "lost-request"]})
    payment = Payment("pay-0301-42", 42, 4999, "2026-03-01")
    first = PaymentRunner(gateway, max_attempts=3).run([payment])
    assert first == {"pay-0301-42": "failed"}, "No try got a reply, so the first run must report the payment as failed."
    # Run 2 is a new process the next day; the scheduler queues the same payment again.
    second = PaymentRunner(gateway, max_attempts=3).run([payment])
    ok = second == {"pay-0301-42": "paid"} and gateway.charged(42) == [4999]
    assert ok, (
        "The next run charged customer 42 again for a payment the first run had already collected. "
        "What does the second run send that lets the gateway recognise the first charge?"
    )


def test_a_declined_card_is_reported_and_not_tried_again():
    gateway = FakeGateway(faults={42: ["declined"]})
    report = PaymentRunner(gateway).run([Payment("pay-0301-42", 42, 4999, "2026-03-01")])
    ok = report == {"pay-0301-42": "declined"} and gateway.requests == 1 and gateway.charged(42) == []
    assert ok, "The issuer declined the card, and the run asked again or reported something other than declined. A decline is an answer."


def test_a_gateway_that_never_replies_gets_max_attempts_tries():
    gateway = FakeGateway(faults={42: ["lost-request"] * 5})
    report = PaymentRunner(gateway, max_attempts=4).run([Payment("pay-0301-42", 42, 4999, "2026-03-01")])
    ok = report == {"pay-0301-42": "failed"} and gateway.requests == 4 and gateway.charged(42) == []
    assert ok, "With no reply at all, the run must try max_attempts times, then report failed so a later run can try again."


def test_waiting_does_not_bring_a_lost_reply_back(monkeypatch):
    waits: list[float] = []
    monkeypatch.setattr(time, "sleep", waits.append)
    monkeypatch.setattr(solution, "sleep", waits.append, raising=False)  # in case of `from time import sleep`
    gateway = FakeGateway(faults={42: ["lost-ack"]})
    PaymentRunner(gateway).run([Payment("pay-0301-42", 42, 4999, "2026-03-01")])
    assert not waits, (
        "The run waited between tries. A lost reply does not come back with time, and the scheduler already spaces out the runs."
    )
    assert gateway.charged(42) == [4999], "Customer 42 was charged more than once after a lost reply."

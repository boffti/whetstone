from gateway import FakeGateway
from solution import Payment, PaymentRunner


def due_on_march_1() -> list[Payment]:
    """The run from the bug report."""
    return [
        Payment("pay-0301-41", 41, 1999, "2026-03-01"),
        Payment("pay-0301-42", 42, 4999, "2026-03-01"),
        Payment("pay-0301-43", 43, 999, "2026-03-01"),
    ]


def test_every_due_payment_is_charged_once_when_nothing_goes_wrong():
    gateway = FakeGateway()
    report = PaymentRunner(gateway).run(due_on_march_1())
    assert report == {"pay-0301-41": "paid", "pay-0301-42": "paid", "pay-0301-43": "paid"}
    assert [gateway.charged(c) for c in (41, 42, 43)] == [[1999], [4999], [999]]


def test_customer_42_is_charged_once_when_the_reply_is_lost():
    # The report: the gateway charged customer 42, but its reply to the first request never came back.
    gateway = FakeGateway(faults={42: ["lost-ack"]})
    report = PaymentRunner(gateway).run(due_on_march_1())
    assert gateway.charged(42) == [4999], (
        f"Customer 42 was charged {len(gateway.charged(42))} times for one payment. "
        "When the first request timed out, what did the runner know about the money?"
    )
    assert report["pay-0301-42"] == "paid", "The money moved, but the run did not report the payment as paid."
    assert [gateway.charged(41), gateway.charged(43)] == [[1999], [999]], "The other customers must still be charged once each."

import pytest
from django.dispatch import Signal

from django_mpesa.signals import (
    balance_received,
    c2b_validation_received,
    payment_confirmed,
    payment_failed,
    payout_completed,
    payout_failed,
    reversal_completed,
)


def test_all_signals_are_signal_instances():
    assert isinstance(payment_confirmed, Signal)
    assert isinstance(payment_failed, Signal)
    assert isinstance(c2b_validation_received, Signal)
    assert isinstance(payout_completed, Signal)
    assert isinstance(payout_failed, Signal)
    assert isinstance(reversal_completed, Signal)
    assert isinstance(balance_received, Signal)


def test_payment_confirmed_fires_with_transaction():
    received = []

    def receiver(sender, transaction, **kwargs):
        received.append(transaction)

    payment_confirmed.connect(receiver)
    try:
        payment_confirmed.send(sender=object, transaction="fake_txn")
        assert received == ["fake_txn"]
    finally:
        payment_confirmed.disconnect(receiver)


def test_payment_failed_fires_with_result_code():
    received = []

    def receiver(sender, transaction, result_code, result_desc, **kwargs):
        received.append((transaction, result_code, result_desc))

    payment_failed.connect(receiver)
    try:
        payment_failed.send(
            sender=object,
            transaction="fake_txn",
            result_code=1032,
            result_desc="Cancelled by user",
        )
        assert received == [("fake_txn", 1032, "Cancelled by user")]
    finally:
        payment_failed.disconnect(receiver)


def test_payout_completed_fires():
    received = []

    def receiver(sender, transaction, **kwargs):
        received.append(transaction)

    payout_completed.connect(receiver)
    try:
        payout_completed.send(sender=object, transaction="fake_b2c_txn")
        assert received == ["fake_b2c_txn"]
    finally:
        payout_completed.disconnect(receiver)

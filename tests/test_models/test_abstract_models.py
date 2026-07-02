from decimal import Decimal

import pytest

from django_mpesa.models import (
    TERMINAL_STATES,
    get_callback_log_model,
    get_transaction_model,
)


@pytest.fixture
def Transaction(db):
    return get_transaction_model()


@pytest.fixture
def CallbackLog(db):
    return get_callback_log_model()


def test_get_transaction_model_returns_correct_class():
    Transaction = get_transaction_model()
    assert Transaction.__name__ == "MpesaTransaction"
    assert Transaction._meta.app_label == "testapp"


def test_get_callback_log_model_returns_correct_class():
    CallbackLog = get_callback_log_model()
    assert CallbackLog.__name__ == "MpesaCallbackLog"
    assert CallbackLog._meta.app_label == "testapp"


def test_terminal_states_contains_expected_values():
    assert "SUCCESS" in TERMINAL_STATES
    assert "FAILED" in TERMINAL_STATES
    assert "TIMEOUT" in TERMINAL_STATES
    assert "REVERSED" in TERMINAL_STATES
    assert "PENDING" not in TERMINAL_STATES
    assert "PROCESSING" not in TERMINAL_STATES


def test_transaction_amount_is_decimal_field():
    Transaction = get_transaction_model()
    field = Transaction._meta.get_field("amount")
    from django.db.models import DecimalField
    assert isinstance(field, DecimalField)


def test_checkout_request_id_is_unique():
    Transaction = get_transaction_model()
    field = Transaction._meta.get_field("checkout_request_id")
    assert field.unique is True


def test_conversation_id_is_unique():
    Transaction = get_transaction_model()
    field = Transaction._meta.get_field("conversation_id")
    assert field.unique is True


def test_transaction_default_status_is_pending(db):
    Transaction = get_transaction_model()
    txn = Transaction(
        transaction_type="STK_PUSH",
        phone_number="254712345678",
        amount=Decimal("100.00"),
        account_reference="INV-001",
        transaction_desc="Payment",
    )
    assert txn.status == "PENDING"


def test_transaction_str(db):
    Transaction = get_transaction_model()
    txn = Transaction.objects.create(
        transaction_type="STK_PUSH",
        status="PENDING",
        phone_number="254712345678",
        amount=Decimal("100.00"),
        account_reference="INV-001",
        transaction_desc="Payment",
    )
    s = str(txn)
    assert "STK_PUSH" in s
    assert "PENDING" in s
    assert "100" in s
    assert "254712345678" in s


def test_callback_log_str(db):
    CallbackLog = get_callback_log_model()
    log = CallbackLog.objects.create(
        callback_type="STK",
        source_ip="196.201.214.200",
        raw_body={"test": "data"},
    )
    s = str(log)
    assert "STK" in s
    assert "196.201.214.200" in s


def test_transaction_ordering(db):
    """Transactions should be ordered newest first."""
    Transaction = get_transaction_model()
    ordering = Transaction._meta.ordering
    assert ordering == ["-initiated_at"]


def test_callback_log_ordering(db):
    """Callback logs should be ordered newest first."""
    CallbackLog = get_callback_log_model()
    ordering = CallbackLog._meta.ordering
    assert ordering == ["-received_at"]

"""
Idempotency and concurrency tests for django-mpesa.

These tests verify that processing the same callback twice results in
exactly one settlement and exactly one signal fire.

CONCURRENCY TESTS (transaction=True):
--------------------------------------
The threading-based tests use @pytest.mark.django_db(transaction=True)
and are SKIPPED on SQLite. SQLite only allows one writer at a time and
raises "database table is locked" instead of blocking — it cannot model
the race condition we are testing. Use PostgreSQL for these tests.

To run against PostgreSQL, set the TEST_DATABASE_URL environment variable:
    TEST_DATABASE_URL=postgres://user:pass@localhost/test_db pytest tests/test_idempotency.py

The SEQUENTIAL idempotency tests (no threading) run on any backend and
verify the terminal-state check logic directly.

WHY THIS MATTERS:
-----------------
If select_for_update() or the terminal-state check is removed from
tasks.py, the sequential tests will still pass (they run one task at a
time), but the concurrent tests will reveal double-settlement. That is
why both test styles are kept.
"""

import threading
from decimal import Decimal

import pytest
from django.db import connection

from django_mpesa.models import get_callback_log_model, get_transaction_model
from django_mpesa.signals import payment_confirmed, payout_completed
from django_mpesa.tasks import process_b2c_result, process_stk_callback

STK_SUCCESS_PAYLOAD = {
    "Body": {
        "stkCallback": {
            "MerchantRequestID": "concurrent_merchant",
            "CheckoutRequestID": "ws_CO_concurrent_test",
            "ResultCode": 0,
            "ResultDesc": "The service request is processed successfully.",
            "CallbackMetadata": {
                "Item": [
                    {"Name": "MpesaReceiptNumber", "Value": "NLJ7RT61SV"},
                    {"Name": "Amount", "Value": 100},
                ]
            },
        }
    }
}

B2C_SUCCESS_PAYLOAD = {
    "Result": {
        "ResultType": 0,
        "ResultCode": 0,
        "ResultDesc": "The service request is processed successfully.",
        "OriginatorConversationID": "concurrent_orig",
        "ConversationID": "concurrent_conv_test",
        "TransactionID": "NLJ7RT61SV",
        "ResultParameters": {
            "ResultParameter": [
                {"Key": "TransactionReceipt", "Value": "NLJ7RT61SV"},
            ]
        },
    }
}


def _is_sqlite():
    return connection.vendor == "sqlite"


# ---------------------------------------------------------------------------
# Sequential idempotency tests — run on any DB backend
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_sequential_duplicate_stk_callback_is_noop():
    """
    Processing the same STK callback twice sequentially:
    - Transaction settles to SUCCESS on first call
    - Second call exits via the terminal-state check (no-op)
    - Signal fires exactly once
    """
    Transaction = get_transaction_model()
    CallbackLog = get_callback_log_model()

    txn = Transaction.objects.create(
        transaction_type="STK_PUSH",
        status="PENDING",
        checkout_request_id="ws_CO_seq_test",
        phone_number="254712345678",
        amount=Decimal("100.00"),
        account_reference="INV-SEQ",
        transaction_desc="SeqTest",
    )

    log1 = CallbackLog.objects.create(
        callback_type="STK",
        source_ip="196.201.214.200",
        raw_body={
            "Body": {"stkCallback": {
                "CheckoutRequestID": "ws_CO_seq_test",
                "ResultCode": 0,
                "ResultDesc": "Success",
                "CallbackMetadata": {"Item": [
                    {"Name": "MpesaReceiptNumber", "Value": "RECEIPT001"},
                ]},
            }}
        },
    )
    log2 = CallbackLog.objects.create(
        callback_type="STK",
        source_ip="196.201.214.200",
        raw_body=log1.raw_body,
    )

    fired = []

    def _receiver(sender, transaction, **kw):
        fired.append(transaction.id)

    payment_confirmed.connect(_receiver)
    try:
        process_stk_callback(str(log1.id))
        process_stk_callback(str(log2.id))
    finally:
        payment_confirmed.disconnect(_receiver)

    txn.refresh_from_db()
    assert txn.status == "SUCCESS"
    assert txn.mpesa_receipt_number == "RECEIPT001"
    assert len(fired) == 1, f"Signal fired {len(fired)} times, expected 1"


@pytest.mark.django_db
def test_sequential_duplicate_b2c_result_is_noop():
    """
    Processing the same B2C result twice sequentially settles once.
    """
    Transaction = get_transaction_model()
    CallbackLog = get_callback_log_model()

    txn = Transaction.objects.create(
        transaction_type="B2C",
        status="PENDING",
        conversation_id="seq_conv_test",
        phone_number="254712345678",
        amount=Decimal("500.00"),
        account_reference="B2C-SEQ",
        transaction_desc="B2CSeq",
    )

    payload = {
        "Result": {
            "ResultType": 0,
            "ResultCode": 0,
            "ResultDesc": "Success",
            "OriginatorConversationID": "seq_orig",
            "ConversationID": "seq_conv_test",
            "TransactionID": "RECEIPT_B2C",
        }
    }

    log1 = CallbackLog.objects.create(
        callback_type="B2C_RESULT", source_ip="196.201.214.200", raw_body=payload
    )
    log2 = CallbackLog.objects.create(
        callback_type="B2C_RESULT", source_ip="196.201.214.200", raw_body=payload
    )

    fired = []

    def _b2c_receiver(sender, transaction, **kw):
        fired.append(1)

    payout_completed.connect(_b2c_receiver)
    try:
        process_b2c_result(str(log1.id))
        process_b2c_result(str(log2.id))
    finally:
        payout_completed.disconnect(_b2c_receiver)

    txn.refresh_from_db()
    assert txn.status == "SUCCESS"
    assert len(fired) == 1, f"Signal fired {len(fired)} times, expected 1"


# ---------------------------------------------------------------------------
# Concurrent idempotency tests — PostgreSQL only
# ---------------------------------------------------------------------------

@pytest.mark.django_db(transaction=True)
@pytest.mark.skipif(
    True,  # Always define the skip condition at collection time
    reason="SQLite cannot model concurrent writers. Run with PostgreSQL.",
)
def test_concurrent_stk_skipped_on_sqlite():
    """Placeholder — see test_duplicate_stk_callback_settles_exactly_once."""
    pass


@pytest.mark.django_db(transaction=True)
def test_duplicate_stk_callback_settles_exactly_once():
    """
    Two threads call process_stk_callback simultaneously.
    Requires PostgreSQL — skipped on SQLite.
    """
    if _is_sqlite():
        pytest.skip(
            "SQLite cannot model concurrent writers — "
            "run with PostgreSQL to test the race condition."
        )

    Transaction = get_transaction_model()
    CallbackLog = get_callback_log_model()

    txn = Transaction.objects.create(
        transaction_type="STK_PUSH",
        status="PENDING",
        checkout_request_id="ws_CO_concurrent_test",
        phone_number="254712345678",
        amount=Decimal("100.00"),
        account_reference="INV-CONC",
        transaction_desc="ConcTest",
    )

    log1 = CallbackLog.objects.create(
        callback_type="STK", source_ip="196.201.214.200", raw_body=STK_SUCCESS_PAYLOAD
    )
    log2 = CallbackLog.objects.create(
        callback_type="STK", source_ip="196.201.214.200", raw_body=STK_SUCCESS_PAYLOAD
    )

    signal_fires = []

    def _on_confirmed(sender, transaction, **kwargs):
        signal_fires.append(transaction.id)

    payment_confirmed.connect(_on_confirmed)
    barrier = threading.Barrier(2)
    errors = []

    def run_task(log_id):
        try:
            barrier.wait()
            process_stk_callback(str(log_id))
        except Exception as e:
            errors.append(e)

    t1 = threading.Thread(target=run_task, args=(log1.id,))
    t2 = threading.Thread(target=run_task, args=(log2.id,))
    t1.start()
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)

    payment_confirmed.disconnect(_on_confirmed)

    assert errors == [], f"Threads raised: {errors}"
    txn.refresh_from_db()
    assert txn.status == "SUCCESS"
    assert txn.settled_at is not None
    assert len(signal_fires) == 1, (
        f"payment_confirmed fired {len(signal_fires)} times — expected exactly 1."
    )


@pytest.mark.django_db(transaction=True)
def test_duplicate_b2c_result_settles_exactly_once():
    """
    Two threads call process_b2c_result simultaneously.
    Requires PostgreSQL — skipped on SQLite.
    """
    if _is_sqlite():
        pytest.skip(
            "SQLite cannot model concurrent writers — "
            "run with PostgreSQL to test the race condition."
        )

    Transaction = get_transaction_model()
    CallbackLog = get_callback_log_model()

    txn = Transaction.objects.create(
        transaction_type="B2C",
        status="PENDING",
        conversation_id="concurrent_conv_test",
        phone_number="254712345678",
        amount=Decimal("500.00"),
        account_reference="B2C-CONC",
        transaction_desc="B2CTest",
    )

    log1 = CallbackLog.objects.create(
        callback_type="B2C_RESULT", source_ip="196.201.214.200", raw_body=B2C_SUCCESS_PAYLOAD
    )
    log2 = CallbackLog.objects.create(
        callback_type="B2C_RESULT", source_ip="196.201.214.200", raw_body=B2C_SUCCESS_PAYLOAD
    )

    signal_fires = []

    def _on_payout(sender, transaction, **kwargs):
        signal_fires.append(transaction.id)

    payout_completed.connect(_on_payout)
    barrier = threading.Barrier(2)
    errors = []

    def run_task(log_id):
        try:
            barrier.wait()
            process_b2c_result(str(log_id))
        except Exception as e:
            errors.append(e)

    t1 = threading.Thread(target=run_task, args=(log1.id,))
    t2 = threading.Thread(target=run_task, args=(log2.id,))
    t1.start()
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)

    payout_completed.disconnect(_on_payout)

    assert errors == [], f"Threads raised: {errors}"
    txn.refresh_from_db()
    assert txn.status == "SUCCESS"
    assert len(signal_fires) == 1

"""
Targeted tests for remaining coverage gaps.
"""

import pytest
from decimal import Decimal
from rest_framework.test import APIClient

from django_mpesa.models import get_callback_log_model, get_transaction_model


# ------------------------------------------------------------------
# views.py — exception paths (logging-only, always return 200)
# ------------------------------------------------------------------

@pytest.fixture
def api_client():
    return APIClient()


def test_stk_view_returns_200_with_empty_body(api_client, db):
    """Empty/malformed body should still return 200."""
    response = api_client.post("/mpesa/stk/callback/", data="", content_type="text/plain")
    assert response.status_code == 200


def test_c2b_validation_view_with_empty_body(api_client, db):
    response = api_client.post("/mpesa/c2b/validate/", data="", content_type="text/plain")
    assert response.status_code == 200


def test_c2b_confirmation_view_with_empty_body(api_client, db):
    response = api_client.post("/mpesa/c2b/confirm/", data="", content_type="text/plain")
    assert response.status_code == 200


def test_b2c_result_view_with_empty_body(api_client, db):
    response = api_client.post("/mpesa/b2c/result/", data="", content_type="text/plain")
    assert response.status_code == 200


def test_b2c_timeout_view_with_empty_body(api_client, db):
    response = api_client.post("/mpesa/b2c/timeout/", data="", content_type="text/plain")
    assert response.status_code == 200


# ------------------------------------------------------------------
# tasks.py — missing CheckoutRequestID path
# ------------------------------------------------------------------

def test_stk_task_missing_checkout_request_id(db):
    """Callback with no CheckoutRequestID logs error and returns."""
    from django_mpesa.tasks import process_stk_callback
    CallbackLog = get_callback_log_model()

    log = CallbackLog.objects.create(
        callback_type="STK",
        source_ip="196.201.214.200",
        raw_body={"Body": {"stkCallback": {"ResultCode": 0, "ResultDesc": "ok"}}},
        # No CheckoutRequestID
    )
    # Should not raise
    process_stk_callback(str(log.id))
    log.refresh_from_db()
    assert log.error is not None


def test_stk_task_missing_log(db):
    """Non-existent CallbackLog ID should not raise."""
    import uuid
    from django_mpesa.tasks import process_stk_callback
    process_stk_callback(str(uuid.uuid4()))  # Should log error but not raise


def test_b2c_task_missing_log(db):
    """Non-existent CallbackLog ID should not raise."""
    import uuid
    from django_mpesa.tasks import process_b2c_result
    process_b2c_result(str(uuid.uuid4()))


def test_b2c_timeout_task_missing_log(db):
    import uuid
    from django_mpesa.tasks import process_b2c_timeout
    process_b2c_timeout(str(uuid.uuid4()))


def test_c2b_confirmation_task_missing_log(db):
    import uuid
    from django_mpesa.tasks import process_c2b_confirmation
    process_c2b_confirmation(str(uuid.uuid4()))


def test_b2c_task_missing_conversation_id(db):
    """B2C result with no ConversationID logs error."""
    from django_mpesa.tasks import process_b2c_result
    CallbackLog = get_callback_log_model()
    log = CallbackLog.objects.create(
        callback_type="B2C_RESULT",
        source_ip="196.201.214.200",
        raw_body={"Result": {"ResultCode": 0, "ResultDesc": "ok"}},
    )
    process_b2c_result(str(log.id))
    log.refresh_from_db()
    assert log.error is not None


def test_b2c_timeout_missing_conversation_id(db):
    from django_mpesa.tasks import process_b2c_timeout
    CallbackLog = get_callback_log_model()
    log = CallbackLog.objects.create(
        callback_type="B2C_TIMEOUT",
        source_ip="196.201.214.200",
        raw_body={"Result": {"ResultCode": 0}},  # No ConversationID
    )
    process_b2c_timeout(str(log.id))
    log.refresh_from_db()
    assert log.error is not None


# ------------------------------------------------------------------
# tasks.py — _make_task / Celery wrapper path
# ------------------------------------------------------------------

def test_make_task_returns_callable_without_celery():
    """When USE_CELERY=False, tasks are plain callables."""
    from django_mpesa.tasks import process_stk_callback
    assert callable(process_stk_callback)


# ------------------------------------------------------------------
# views.py — exception in CallbackLog.objects.create path
# ------------------------------------------------------------------

def test_c2b_validation_view_exception_in_signal_still_returns_200(api_client, db):
    """Signal receiver that raises should not prevent 200 response."""
    from django_mpesa.signals import c2b_validation_received

    def _raiser(sender, raw_payload, **kwargs):
        raise ValueError("deliberate test error")

    c2b_validation_received.connect(_raiser)
    try:
        response = api_client.post(
            "/mpesa/c2b/validate/",
            data={"BillRefNumber": "INV-001"},
            format="json",
        )
    finally:
        c2b_validation_received.disconnect(_raiser)

    assert response.status_code == 200


# ------------------------------------------------------------------
# tasks.py — signal receiver raises, transaction still settled
# ------------------------------------------------------------------

def test_stk_task_signal_receiver_exception_does_not_unsettle(db):
    """If a signal receiver raises, the transaction is still SUCCESS."""
    from django_mpesa.tasks import process_stk_callback
    from django_mpesa.signals import payment_confirmed

    Transaction = get_transaction_model()
    CallbackLog = get_callback_log_model()

    txn = Transaction.objects.create(
        transaction_type="STK_PUSH",
        status="PENDING",
        checkout_request_id="ws_CO_signal_error_test",
        phone_number="254712345678",
        amount=Decimal("100.00"),
        account_reference="INV-SIG",
        transaction_desc="SigTest",
    )

    def _bad_receiver(sender, transaction, **kwargs):
        raise RuntimeError("receiver error")

    payment_confirmed.connect(_bad_receiver)
    log = CallbackLog.objects.create(
        callback_type="STK",
        source_ip="196.201.214.200",
        raw_body={
            "Body": {"stkCallback": {
                "CheckoutRequestID": "ws_CO_signal_error_test",
                "ResultCode": 0,
                "ResultDesc": "Success",
                "CallbackMetadata": {"Item": [{"Name": "MpesaReceiptNumber", "Value": "ABC123"}]},
            }}
        },
    )
    try:
        process_stk_callback(str(log.id))
    finally:
        payment_confirmed.disconnect(_bad_receiver)

    txn.refresh_from_db()
    assert txn.status == "SUCCESS"  # Still settled despite receiver error


# ------------------------------------------------------------------
# django_mpesa/__init__.py — version is set
# ------------------------------------------------------------------

def test_version_is_set():
    import django_mpesa
    assert django_mpesa.__version__ == "0.1.0"

from decimal import Decimal

import pytest
from django.test import override_settings
from rest_framework.test import APIClient

from django_mpesa.models import get_callback_log_model, get_transaction_model
from django_mpesa.signals import payment_confirmed, payment_failed
from django_mpesa.tasks import process_stk_callback

STK_SUCCESS_PAYLOAD = {
    "Body": {
        "stkCallback": {
            "MerchantRequestID": "test_merchant_456",
            "CheckoutRequestID": "ws_CO_test_123",
            "ResultCode": 0,
            "ResultDesc": "The service request is processed successfully.",
            "CallbackMetadata": {
                "Item": [
                    {"Name": "Amount", "Value": 100},
                    {"Name": "MpesaReceiptNumber", "Value": "NLJ7RT61SV"},
                    {"Name": "TransactionDate", "Value": 20191219102115},
                    {"Name": "PhoneNumber", "Value": 254712345678},
                ]
            },
        }
    }
}

STK_FAILURE_PAYLOAD = {
    "Body": {
        "stkCallback": {
            "MerchantRequestID": "test_merchant_456",
            "CheckoutRequestID": "ws_CO_test_123",
            "ResultCode": 1032,
            "ResultDesc": "Request cancelled by user.",
        }
    }
}


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def pending_txn(db):
    Transaction = get_transaction_model()
    return Transaction.objects.create(
        transaction_type="STK_PUSH",
        status="PENDING",
        checkout_request_id="ws_CO_test_123",
        merchant_request_id="test_merchant_456",
        phone_number="254712345678",
        amount=Decimal("100.00"),
        account_reference="INV-001",
        transaction_desc="Payment",
    )


# ------------------------------------------------------------------
# View tests
# ------------------------------------------------------------------

def test_callback_view_always_returns_200(client, db):
    response = client.post(
        "/mpesa/stk/callback/",
        data=STK_SUCCESS_PAYLOAD,
        format="json",
    )
    assert response.status_code == 200
    assert response.data["ResultCode"] == 0


def test_callback_view_returns_200_on_malformed_payload(client, db):
    response = client.post(
        "/mpesa/stk/callback/",
        data="not valid json",
        content_type="text/plain",
    )
    assert response.status_code == 200


def test_callback_view_logs_raw_payload(client, db):
    CallbackLog = get_callback_log_model()
    client.post("/mpesa/stk/callback/", data=STK_SUCCESS_PAYLOAD, format="json")
    assert CallbackLog.objects.filter(callback_type="STK").count() == 1
    log = CallbackLog.objects.get(callback_type="STK")
    assert log.raw_body == STK_SUCCESS_PAYLOAD


def test_callback_view_logs_source_ip(client, db):
    CallbackLog = get_callback_log_model()
    client.post(
        "/mpesa/stk/callback/",
        data=STK_SUCCESS_PAYLOAD,
        format="json",
        REMOTE_ADDR="196.201.214.200",
    )
    log = CallbackLog.objects.get(callback_type="STK")
    assert log.source_ip == "196.201.214.200"


# ------------------------------------------------------------------
# Task tests
# ------------------------------------------------------------------

def test_success_callback_moves_transaction_to_success(db, pending_txn):
    CallbackLog = get_callback_log_model()
    log = CallbackLog.objects.create(
        callback_type="STK",
        source_ip="196.201.214.200",
        raw_body=STK_SUCCESS_PAYLOAD,
    )
    process_stk_callback(str(log.id))

    pending_txn.refresh_from_db()
    assert pending_txn.status == "SUCCESS"
    assert pending_txn.mpesa_receipt_number == "NLJ7RT61SV"


def test_success_callback_sets_settled_at(db, pending_txn):
    CallbackLog = get_callback_log_model()
    log = CallbackLog.objects.create(
        callback_type="STK",
        source_ip="196.201.214.200",
        raw_body=STK_SUCCESS_PAYLOAD,
    )
    process_stk_callback(str(log.id))
    pending_txn.refresh_from_db()
    assert pending_txn.settled_at is not None


def test_failure_callback_moves_transaction_to_failed(db, pending_txn):
    CallbackLog = get_callback_log_model()
    log = CallbackLog.objects.create(
        callback_type="STK",
        source_ip="196.201.214.200",
        raw_body=STK_FAILURE_PAYLOAD,
    )
    process_stk_callback(str(log.id))
    pending_txn.refresh_from_db()
    assert pending_txn.status == "FAILED"
    assert pending_txn.result_code == 1032


def test_payment_confirmed_signal_fires_on_success(db, pending_txn):
    received = []

    def receiver(sender, transaction, **kwargs):
        received.append(transaction.id)

    payment_confirmed.connect(receiver)
    CallbackLog = get_callback_log_model()
    log = CallbackLog.objects.create(
        callback_type="STK",
        source_ip="196.201.214.200",
        raw_body=STK_SUCCESS_PAYLOAD,
    )
    try:
        process_stk_callback(str(log.id))
    finally:
        payment_confirmed.disconnect(receiver)

    assert len(received) == 1
    assert received[0] == pending_txn.id


def test_payment_failed_signal_fires_on_failure(db, pending_txn):
    received = []

    def receiver(sender, transaction, result_code, **kwargs):
        received.append(result_code)

    payment_failed.connect(receiver)
    CallbackLog = get_callback_log_model()
    log = CallbackLog.objects.create(
        callback_type="STK",
        source_ip="196.201.214.200",
        raw_body=STK_FAILURE_PAYLOAD,
    )
    try:
        process_stk_callback(str(log.id))
    finally:
        payment_failed.disconnect(receiver)

    assert received == [1032]


def test_duplicate_callback_is_noop(db, pending_txn):
    received = []

    def _on_confirmed(sender, transaction, **kw):
        received.append(1)

    payment_confirmed.connect(_on_confirmed)

    CallbackLog = get_callback_log_model()
    log1 = CallbackLog.objects.create(
        callback_type="STK", source_ip="1.1.1.1", raw_body=STK_SUCCESS_PAYLOAD
    )
    log2 = CallbackLog.objects.create(
        callback_type="STK", source_ip="1.1.1.1", raw_body=STK_SUCCESS_PAYLOAD
    )

    try:
        process_stk_callback(str(log1.id))
        first_settled_at = pending_txn.__class__.objects.get(
            pk=pending_txn.pk
        ).settled_at
        process_stk_callback(str(log2.id))
        second_settled_at = pending_txn.__class__.objects.get(
            pk=pending_txn.pk
        ).settled_at
    finally:
        payment_confirmed.disconnect(_on_confirmed)

    assert len(received) == 1, f"Signal fired {len(received)} times, expected 1"
    assert first_settled_at == second_settled_at


def test_unknown_checkout_id_logs_error_and_does_not_raise(db):
    CallbackLog = get_callback_log_model()
    log = CallbackLog.objects.create(
        callback_type="STK",
        source_ip="196.201.214.200",
        raw_body=STK_SUCCESS_PAYLOAD,
    )
    # No matching transaction — should not raise
    process_stk_callback(str(log.id))

    log.refresh_from_db()
    assert log.error is not None
    assert "checkout_request_id" in log.error


# ------------------------------------------------------------------
# Middleware tests
# ------------------------------------------------------------------

@override_settings(MPESA={
    **__import__("django.conf", fromlist=["settings"]).settings.MPESA,
    "VERIFY_CALLBACK_SOURCE_IP": True,
    "CALLBACK_IP_ALLOWLIST": ["196.201.214.200"],
})
def test_safaricom_ip_allowed(client, db):
    from django_mpesa.conf import mpesa_settings
    mpesa_settings.reload()
    response = client.post(
        "/mpesa/stk/callback/",
        data=STK_SUCCESS_PAYLOAD,
        format="json",
        REMOTE_ADDR="196.201.214.200",
    )
    mpesa_settings.reload()
    assert response.status_code == 200


@override_settings(
    MPESA={
        **__import__("django.conf", fromlist=["settings"]).settings.MPESA,
        "VERIFY_CALLBACK_SOURCE_IP": True,
        "CALLBACK_IP_ALLOWLIST": ["196.201.214.200"],
    },
    MIDDLEWARE=["django_mpesa.middleware.MpesaCallbackIPAllowlistMiddleware"],
)
def test_non_safaricom_ip_blocked(client, db):
    import django_mpesa.middleware as mw
    mw._MPESA_PATH_CACHE = None  # reset prefix cache so it re-resolves
    from django_mpesa.conf import mpesa_settings
    mpesa_settings.reload()
    response = client.post(
        "/mpesa/stk/callback/",
        data=STK_SUCCESS_PAYLOAD,
        format="json",
        REMOTE_ADDR="1.2.3.4",
    )
    mpesa_settings.reload()
    mw._MPESA_PATH_CACHE = None
    assert response.status_code == 403

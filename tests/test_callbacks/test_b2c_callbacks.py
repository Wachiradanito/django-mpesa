from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from django_mpesa.models import get_callback_log_model, get_transaction_model
from django_mpesa.signals import payout_completed, payout_failed
from django_mpesa.tasks import process_b2c_result, process_b2c_timeout

B2C_SUCCESS_PAYLOAD = {
    "Result": {
        "ResultType": 0,
        "ResultCode": 0,
        "ResultDesc": "The service request is processed successfully.",
        "OriginatorConversationID": "test_orig_123",
        "ConversationID": "test_conv_b2c",
        "TransactionID": "NLJ7RT61SV",
        "ResultParameters": {
            "ResultParameter": [
                {"Key": "TransactionReceipt", "Value": "NLJ7RT61SV"},
                {"Key": "TransactionAmount", "Value": 500},
            ]
        },
    }
}

B2C_FAILURE_PAYLOAD = {
    "Result": {
        "ResultType": 0,
        "ResultCode": 2001,
        "ResultDesc": "The initiator information is invalid.",
        "OriginatorConversationID": "test_orig_123",
        "ConversationID": "test_conv_b2c",
        "TransactionID": "",
    }
}

B2C_TIMEOUT_PAYLOAD = {
    "Result": {
        "ResultType": 0,
        "ResultCode": 0,
        "ResultDesc": "Request cancelled by the user.",
        "OriginatorConversationID": "test_orig_123",
        "ConversationID": "test_conv_b2c",
        "TransactionID": "",
    }
}


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def pending_b2c(db):
    Transaction = get_transaction_model()
    return Transaction.objects.create(
        transaction_type="B2C",
        status="PENDING",
        conversation_id="test_conv_b2c",
        originator_conversation_id="test_orig_123",
        phone_number="254712345678",
        amount=Decimal("500.00"),
        account_reference="254712345678",
        transaction_desc="Payout",
    )


# ------------------------------------------------------------------
# View tests
# ------------------------------------------------------------------

def test_b2c_result_view_always_returns_200(api_client, db):
    response = api_client.post(
        "/mpesa/b2c/result/",
        data=B2C_SUCCESS_PAYLOAD,
        format="json",
    )
    assert response.status_code == 200
    assert response.data["ResultCode"] == 0


def test_b2c_result_view_logs_payload(api_client, db):
    CallbackLog = get_callback_log_model()
    api_client.post("/mpesa/b2c/result/", data=B2C_SUCCESS_PAYLOAD, format="json")
    assert CallbackLog.objects.filter(callback_type="B2C_RESULT").count() == 1


def test_b2c_timeout_view_always_returns_200(api_client, db):
    response = api_client.post(
        "/mpesa/b2c/timeout/",
        data=B2C_TIMEOUT_PAYLOAD,
        format="json",
    )
    assert response.status_code == 200


def test_b2c_timeout_view_logs_payload(api_client, db):
    CallbackLog = get_callback_log_model()
    api_client.post("/mpesa/b2c/timeout/", data=B2C_TIMEOUT_PAYLOAD, format="json")
    assert CallbackLog.objects.filter(callback_type="B2C_TIMEOUT").count() == 1


# ------------------------------------------------------------------
# Task tests
# ------------------------------------------------------------------

def test_b2c_success_result_moves_to_success(db, pending_b2c):
    CallbackLog = get_callback_log_model()
    log = CallbackLog.objects.create(
        callback_type="B2C_RESULT",
        source_ip="196.201.214.200",
        raw_body=B2C_SUCCESS_PAYLOAD,
    )
    process_b2c_result(str(log.id))
    pending_b2c.refresh_from_db()
    assert pending_b2c.status == "SUCCESS"


def test_b2c_success_sets_receipt_number(db, pending_b2c):
    CallbackLog = get_callback_log_model()
    log = CallbackLog.objects.create(
        callback_type="B2C_RESULT",
        source_ip="196.201.214.200",
        raw_body=B2C_SUCCESS_PAYLOAD,
    )
    process_b2c_result(str(log.id))
    pending_b2c.refresh_from_db()
    assert pending_b2c.mpesa_receipt_number == "NLJ7RT61SV"


def test_b2c_failure_result_moves_to_failed(db, pending_b2c):
    CallbackLog = get_callback_log_model()
    log = CallbackLog.objects.create(
        callback_type="B2C_RESULT",
        source_ip="196.201.214.200",
        raw_body=B2C_FAILURE_PAYLOAD,
    )
    process_b2c_result(str(log.id))
    pending_b2c.refresh_from_db()
    assert pending_b2c.status == "FAILED"
    assert pending_b2c.result_code == 2001


def test_payout_completed_signal_fires_on_success(db, pending_b2c):
    fired = []

    def _receiver(sender, transaction, **kwargs):
        fired.append(transaction.id)

    payout_completed.connect(_receiver)
    CallbackLog = get_callback_log_model()
    log = CallbackLog.objects.create(
        callback_type="B2C_RESULT",
        source_ip="196.201.214.200",
        raw_body=B2C_SUCCESS_PAYLOAD,
    )
    try:
        process_b2c_result(str(log.id))
    finally:
        payout_completed.disconnect(_receiver)

    assert len(fired) == 1
    assert fired[0] == pending_b2c.id


def test_payout_failed_signal_fires_on_failure(db, pending_b2c):
    fired = []

    def _receiver(sender, transaction, result_code, **kwargs):
        fired.append(result_code)

    payout_failed.connect(_receiver)
    CallbackLog = get_callback_log_model()
    log = CallbackLog.objects.create(
        callback_type="B2C_RESULT",
        source_ip="196.201.214.200",
        raw_body=B2C_FAILURE_PAYLOAD,
    )
    try:
        process_b2c_result(str(log.id))
    finally:
        payout_failed.disconnect(_receiver)

    assert fired == [2001]


def test_b2c_timeout_moves_to_timeout(db, pending_b2c):
    CallbackLog = get_callback_log_model()
    log = CallbackLog.objects.create(
        callback_type="B2C_TIMEOUT",
        source_ip="196.201.214.200",
        raw_body=B2C_TIMEOUT_PAYLOAD,
    )
    process_b2c_timeout(str(log.id))
    pending_b2c.refresh_from_db()
    assert pending_b2c.status == "TIMEOUT"
    assert pending_b2c.settled_at is not None


def test_payout_failed_signal_fires_on_timeout(db, pending_b2c):
    fired = []

    def _receiver(sender, transaction, result_code, **kwargs):
        fired.append(result_code)

    payout_failed.connect(_receiver)
    CallbackLog = get_callback_log_model()
    log = CallbackLog.objects.create(
        callback_type="B2C_TIMEOUT",
        source_ip="196.201.214.200",
        raw_body=B2C_TIMEOUT_PAYLOAD,
    )
    try:
        process_b2c_timeout(str(log.id))
    finally:
        payout_failed.disconnect(_receiver)

    assert fired == [None]


def test_duplicate_b2c_result_is_noop(db, pending_b2c):
    fired = []

    def _receiver(sender, transaction, **kwargs):
        fired.append(1)

    payout_completed.connect(_receiver)
    CallbackLog = get_callback_log_model()
    log1 = CallbackLog.objects.create(
        callback_type="B2C_RESULT", source_ip="1.1.1.1", raw_body=B2C_SUCCESS_PAYLOAD
    )
    log2 = CallbackLog.objects.create(
        callback_type="B2C_RESULT", source_ip="1.1.1.1", raw_body=B2C_SUCCESS_PAYLOAD
    )
    try:
        process_b2c_result(str(log1.id))
        process_b2c_result(str(log2.id))
    finally:
        payout_completed.disconnect(_receiver)

    assert len(fired) == 1, f"Signal fired {len(fired)} times"
    pending_b2c.refresh_from_db()
    assert pending_b2c.status == "SUCCESS"

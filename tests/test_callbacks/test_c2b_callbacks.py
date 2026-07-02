from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from django_mpesa.models import get_callback_log_model, get_transaction_model
from django_mpesa.signals import c2b_validation_received, payment_confirmed
from django_mpesa.tasks import process_c2b_confirmation

C2B_CONFIRMATION_PAYLOAD = {
    "TransactionType": "Pay Bill",
    "TransID": "NLJ7RT61SV",
    "TransTime": "20191219102116",
    "TransAmount": "100.00",
    "BusinessShortCode": "174379",
    "BillRefNumber": "INV-001",
    "MSISDN": "254712345678",
    "FirstName": "John",
}

C2B_VALIDATION_PAYLOAD = {
    "TransactionType": "Pay Bill",
    "TransID": "NLJ7RT61SV",
    "TransAmount": "100.00",
    "BusinessShortCode": "174379",
    "BillRefNumber": "INV-001",
    "MSISDN": "254712345678",
}


@pytest.fixture
def api_client():
    return APIClient()


# ------------------------------------------------------------------
# Validation view tests
# ------------------------------------------------------------------

def test_validation_view_returns_200_by_default(api_client, db):
    response = api_client.post(
        "/mpesa/c2b/validate/",
        data=C2B_VALIDATION_PAYLOAD,
        format="json",
    )
    assert response.status_code == 200
    assert response.data["ResultCode"] == 0


def test_validation_view_fires_signal(api_client, db):
    received_payloads = []

    def _receiver(sender, raw_payload, **kwargs):
        received_payloads.append(raw_payload)
        return None

    c2b_validation_received.connect(_receiver)
    try:
        api_client.post("/mpesa/c2b/validate/", data=C2B_VALIDATION_PAYLOAD, format="json")
    finally:
        c2b_validation_received.disconnect(_receiver)

    assert len(received_payloads) == 1
    assert received_payloads[0]["BillRefNumber"] == "INV-001"


def test_validation_view_receiver_can_reject(api_client, db):
    def _rejector(sender, raw_payload, **kwargs):
        return {"ResultCode": "C2B00012", "ResultDesc": "Invalid bill reference"}

    c2b_validation_received.connect(_rejector)
    try:
        response = api_client.post(
            "/mpesa/c2b/validate/",
            data=C2B_VALIDATION_PAYLOAD,
            format="json",
        )
    finally:
        c2b_validation_received.disconnect(_rejector)

    assert response.data["ResultCode"] == "C2B00012"


def test_validation_view_logs_raw_payload(api_client, db):
    CallbackLog = get_callback_log_model()
    api_client.post("/mpesa/c2b/validate/", data=C2B_VALIDATION_PAYLOAD, format="json")
    assert CallbackLog.objects.filter(callback_type="C2B_VALIDATION").count() == 1


# ------------------------------------------------------------------
# Confirmation view tests
# ------------------------------------------------------------------

def test_confirmation_view_always_returns_200(api_client, db):
    response = api_client.post(
        "/mpesa/c2b/confirm/",
        data=C2B_CONFIRMATION_PAYLOAD,
        format="json",
    )
    assert response.status_code == 200
    assert response.data["ResultCode"] == 0


def test_confirmation_view_logs_payload(api_client, db):
    CallbackLog = get_callback_log_model()
    api_client.post("/mpesa/c2b/confirm/", data=C2B_CONFIRMATION_PAYLOAD, format="json")
    assert CallbackLog.objects.filter(callback_type="C2B_CONFIRMATION").count() == 1


# ------------------------------------------------------------------
# Confirmation task tests
# ------------------------------------------------------------------

def test_confirmation_creates_new_transaction_if_none_exists(db):
    """C2B payment arrives without a prior initiation — should create a new SUCCESS row."""
    CallbackLog = get_callback_log_model()
    Transaction = get_transaction_model()

    log = CallbackLog.objects.create(
        callback_type="C2B_CONFIRMATION",
        source_ip="196.201.214.200",
        raw_body=C2B_CONFIRMATION_PAYLOAD,
    )
    process_c2b_confirmation(str(log.id))

    assert Transaction.objects.filter(
        mpesa_receipt_number="NLJ7RT61SV", status="SUCCESS"
    ).exists()


def test_confirmation_updates_existing_pending_transaction(db):
    """If a PENDING C2B transaction exists, it should be updated to SUCCESS."""
    Transaction = get_transaction_model()
    CallbackLog = get_callback_log_model()

    txn = Transaction.objects.create(
        transaction_type="C2B",
        status="PENDING",
        phone_number="254712345678",
        amount=Decimal("100.00"),
        account_reference="INV-001",
        transaction_desc="C2B Payment",
    )

    log = CallbackLog.objects.create(
        callback_type="C2B_CONFIRMATION",
        source_ip="196.201.214.200",
        raw_body=C2B_CONFIRMATION_PAYLOAD,
    )
    process_c2b_confirmation(str(log.id))

    txn.refresh_from_db()
    assert txn.status == "SUCCESS"
    assert txn.mpesa_receipt_number == "NLJ7RT61SV"


def test_confirmation_is_noop_for_already_settled_transaction(db):
    """Duplicate confirmation callback must not re-settle."""
    Transaction = get_transaction_model()
    CallbackLog = get_callback_log_model()

    log1 = CallbackLog.objects.create(
        callback_type="C2B_CONFIRMATION",
        source_ip="196.201.214.200",
        raw_body=C2B_CONFIRMATION_PAYLOAD,
    )
    log2 = CallbackLog.objects.create(
        callback_type="C2B_CONFIRMATION",
        source_ip="196.201.214.200",
        raw_body=C2B_CONFIRMATION_PAYLOAD,
    )

    process_c2b_confirmation(str(log1.id))
    count_before = Transaction.objects.count()
    process_c2b_confirmation(str(log2.id))
    count_after = Transaction.objects.count()

    # Second call should not create a new transaction
    assert count_before == count_after


def test_payment_confirmed_fires_on_c2b_confirmation(db):
    CallbackLog = get_callback_log_model()
    fired = []

    def _receiver(sender, transaction, **kwargs):
        fired.append(transaction)

    payment_confirmed.connect(_receiver)
    log = CallbackLog.objects.create(
        callback_type="C2B_CONFIRMATION",
        source_ip="196.201.214.200",
        raw_body=C2B_CONFIRMATION_PAYLOAD,
    )
    try:
        process_c2b_confirmation(str(log.id))
    finally:
        payment_confirmed.disconnect(_receiver)

    assert len(fired) == 1
    assert fired[0].status == "SUCCESS"

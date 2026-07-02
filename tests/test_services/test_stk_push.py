from decimal import Decimal

import pytest

from django_mpesa.exceptions import DarajaAPIError, DarajaValidationError
from django_mpesa.models import get_transaction_model
from django_mpesa.services.stk_push import STKPushService


class MockDarajaClient:
    """Minimal mock for STK Push tests."""

    def __init__(self, response=None, raise_exc=None):
        self.calls = []
        self._response = response or {
            "ResponseCode": "0",
            "CheckoutRequestID": "ws_CO_test_123",
            "MerchantRequestID": "test_merchant_456",
            "ResponseDescription": "Success",
        }
        self._raise = raise_exc

    def post(self, path, payload):
        self.calls.append({"path": path, "payload": payload})
        if self._raise:
            raise self._raise
        return self._response


@pytest.fixture
def mock_daraja():
    return MockDarajaClient()


@pytest.fixture
def mock_daraja_fail():
    return MockDarajaClient(raise_exc=DarajaAPIError("Daraja error", status_code=500))


def test_initiate_creates_pending_transaction(db, mock_daraja):
    service = STKPushService(client=mock_daraja)
    txn = service.initiate("254712345678", 100, "INV-001", "Payment")

    assert txn.status == "PENDING"
    assert txn.transaction_type == "STK_PUSH"
    assert txn.checkout_request_id == "ws_CO_test_123"


def test_initiate_stores_merchant_request_id(db, mock_daraja):
    service = STKPushService(client=mock_daraja)
    txn = service.initiate("254712345678", 100, "INV-001", "Payment")
    assert txn.merchant_request_id == "test_merchant_456"


def test_initiate_normalises_07_phone(db, mock_daraja):
    service = STKPushService(client=mock_daraja)
    txn = service.initiate("0712345678", 100, "INV-001", "Payment")
    assert txn.phone_number == "254712345678"


def test_initiate_saves_amount_as_decimal(db, mock_daraja):
    service = STKPushService(client=mock_daraja)
    txn = service.initiate("254712345678", 150, "INV-001", "Payment")
    assert txn.amount == Decimal("150")


def test_initiate_invalid_reference_too_long_raises_before_network(mock_daraja):
    service = STKPushService(client=mock_daraja)
    with pytest.raises(DarajaValidationError):
        service.initiate("254712345678", 100, "A" * 13, "Payment")
    assert mock_daraja.calls == []


def test_initiate_invalid_desc_too_long_raises_before_network(mock_daraja):
    service = STKPushService(client=mock_daraja)
    with pytest.raises(DarajaValidationError):
        service.initiate("254712345678", 100, "INV-001", "A" * 14)
    assert mock_daraja.calls == []


def test_initiate_negative_amount_raises_before_network(mock_daraja):
    service = STKPushService(client=mock_daraja)
    with pytest.raises(DarajaValidationError):
        service.initiate("254712345678", -100, "INV-001", "Payment")
    assert mock_daraja.calls == []


def test_initiate_api_failure_does_not_create_transaction(db, mock_daraja_fail):
    Transaction = get_transaction_model()
    service = STKPushService(client=mock_daraja_fail)
    with pytest.raises(DarajaAPIError):
        service.initiate("254712345678", 100, "INV-001", "Payment")
    assert Transaction.objects.count() == 0


def test_amount_sent_as_integer(db, mock_daraja):
    service = STKPushService(client=mock_daraja)
    service.initiate("254712345678", Decimal("100.00"), "INV-001", "Payment")
    payload = mock_daraja.calls[0]["payload"]
    assert payload["Amount"] == 100
    assert isinstance(payload["Amount"], int)


def test_query_returns_dict_without_db_mutation(db, mock_daraja):
    Transaction = get_transaction_model()
    service = STKPushService(client=mock_daraja)
    result = service.query("ws_CO_test_123")
    assert isinstance(result, dict)
    assert Transaction.objects.count() == 0

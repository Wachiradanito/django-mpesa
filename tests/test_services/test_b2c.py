from decimal import Decimal

import pytest

from django_mpesa.exceptions import DarajaAPIError, DarajaValidationError
from django_mpesa.models import get_transaction_model
from django_mpesa.services.b2c import B2CService


class MockClient:
    def __init__(self, response=None, raise_exc=None):
        self.calls = []
        self._response = response or {
            "ResponseCode": "0",
            "ConversationID": "test_conv_123",
            "OriginatorConversationID": "test_orig_123",
            "ResponseDescription": "Accept the service request successfully.",
        }
        self._raise = raise_exc

    def post(self, path, payload):
        self.calls.append({"path": path, "payload": payload})
        if self._raise:
            raise self._raise
        return self._response


@pytest.fixture
def mock():
    return MockClient()


@pytest.fixture
def mock_fail():
    return MockClient(raise_exc=DarajaAPIError("error", status_code=500))


def test_send_payment_creates_pending_transaction(db, mock):
    service = B2CService(client=mock)
    txn = service.send_payment("254712345678", 500, "Seller payout")
    assert txn.status == "PENDING"
    assert txn.transaction_type == "B2C"


def test_send_payment_stores_conversation_id(db, mock):
    service = B2CService(client=mock)
    txn = service.send_payment("254712345678", 500, "Payout")
    assert txn.conversation_id == "test_conv_123"
    assert txn.originator_conversation_id == "test_orig_123"


def test_send_payment_does_not_set_terminal_status(db, mock):
    """Terminal status must only be set by the B2C result callback."""
    service = B2CService(client=mock)
    txn = service.send_payment("254712345678", 500, "Payout")
    assert txn.status == "PENDING"
    assert txn.settled_at is None


def test_send_payment_invalid_command_id_raises_before_network(mock):
    service = B2CService(client=mock)
    with pytest.raises(DarajaValidationError):
        service.send_payment("254712345678", 500, "Payout", command_id="SendMoney")
    assert mock.calls == []


def test_send_payment_invalid_phone_raises_before_network(mock):
    service = B2CService(client=mock)
    with pytest.raises(DarajaValidationError):
        service.send_payment("not_a_phone", 500, "Payout")
    assert mock.calls == []


def test_send_payment_empty_remarks_raises_before_network(mock):
    service = B2CService(client=mock)
    with pytest.raises(DarajaValidationError):
        service.send_payment("254712345678", 500, "")
    assert mock.calls == []


def test_send_payment_api_failure_does_not_create_transaction(db, mock_fail):
    Transaction = get_transaction_model()
    service = B2CService(client=mock_fail)
    with pytest.raises(DarajaAPIError):
        service.send_payment("254712345678", 500, "Payout")
    assert Transaction.objects.count() == 0


def test_send_payment_salary_command_id(db, mock):
    service = B2CService(client=mock)
    txn = service.send_payment("254712345678", 5000, "Salary", command_id="SalaryPayment")
    assert txn.status == "PENDING"
    assert mock.calls[0]["payload"]["CommandID"] == "SalaryPayment"


def test_amount_sent_as_integer(db, mock):
    service = B2CService(client=mock)
    service.send_payment("254712345678", Decimal("500.00"), "Payout")
    assert mock.calls[0]["payload"]["Amount"] == 500
    assert isinstance(mock.calls[0]["payload"]["Amount"], int)

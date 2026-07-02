"""
Tests for TransactionStatusService, AccountBalanceService, ReversalService.
All three are query/action services that return raw dicts and never mutate DB.
"""

import pytest

from django_mpesa.exceptions import DarajaValidationError
from django_mpesa.models import get_transaction_model
from django_mpesa.services.account_balance import AccountBalanceService
from django_mpesa.services.reversal import ReversalService
from django_mpesa.services.transaction_status import TransactionStatusService


class MockClient:
    def __init__(self, response=None):
        self.calls = []
        self._response = response or {"ResponseCode": "0", "ResponseDescription": "Success"}

    def post(self, path, payload):
        self.calls.append({"path": path, "payload": payload})
        return self._response


@pytest.fixture
def mock():
    return MockClient()


# ------------------------------------------------------------------
# TransactionStatusService
# ------------------------------------------------------------------

def test_transaction_status_query_returns_dict(mock):
    service = TransactionStatusService(client=mock)
    result = service.query("NLJ7RT61SV")
    assert isinstance(result, dict)


def test_transaction_status_invalid_identifier_type_raises(mock):
    service = TransactionStatusService(client=mock)
    with pytest.raises(DarajaValidationError):
        service.query("NLJ7RT61SV", identifier_type="9")


def test_transaction_status_does_not_mutate_db(db, mock):
    Transaction = get_transaction_model()
    service = TransactionStatusService(client=mock)
    service.query("NLJ7RT61SV")
    assert Transaction.objects.count() == 0


def test_transaction_status_payload_has_correct_command_id(mock):
    service = TransactionStatusService(client=mock)
    service.query("NLJ7RT61SV")
    assert mock.calls[0]["payload"]["CommandID"] == "TransactionStatusQuery"


def test_transaction_status_valid_identifier_types(mock):
    service = TransactionStatusService(client=mock)
    for id_type in ("1", "2", "4"):
        service.query("NLJ7RT61SV", identifier_type=id_type)
    assert len(mock.calls) == 3


# ------------------------------------------------------------------
# AccountBalanceService
# ------------------------------------------------------------------

def test_account_balance_query_returns_dict(mock):
    service = AccountBalanceService(client=mock)
    result = service.query()
    assert isinstance(result, dict)


def test_account_balance_invalid_identifier_type_raises(mock):
    service = AccountBalanceService(client=mock)
    with pytest.raises(DarajaValidationError):
        service.query(identifier_type="5")


def test_account_balance_payload_has_correct_command_id(mock):
    service = AccountBalanceService(client=mock)
    service.query()
    assert mock.calls[0]["payload"]["CommandID"] == "AccountBalance"


def test_account_balance_default_identifier_type_is_4(mock):
    service = AccountBalanceService(client=mock)
    service.query()
    assert mock.calls[0]["payload"]["IdentifierType"] == "4"


# ------------------------------------------------------------------
# ReversalService
# ------------------------------------------------------------------

def test_reversal_returns_dict(mock):
    service = ReversalService(client=mock)
    result = service.reverse("NLJ7RT61SV", 100, "Error", "254712345678")
    assert isinstance(result, dict)


def test_reversal_does_not_mutate_db(db, mock):
    Transaction = get_transaction_model()
    service = ReversalService(client=mock)
    service.reverse("NLJ7RT61SV", 100, "Refund", "254712345678")
    assert Transaction.objects.count() == 0


def test_reversal_payload_has_transaction_reversal_command_id(mock):
    service = ReversalService(client=mock)
    service.reverse("NLJ7RT61SV", 100, "Refund", "254712345678")
    assert mock.calls[0]["payload"]["CommandID"] == "TransactionReversal"


def test_reversal_invalid_amount_raises_before_network(mock):
    service = ReversalService(client=mock)
    with pytest.raises(DarajaValidationError):
        service.reverse("NLJ7RT61SV", -100, "Refund", "254712345678")
    assert mock.calls == []


def test_reversal_amount_sent_as_integer(mock):
    service = ReversalService(client=mock)
    service.reverse("NLJ7RT61SV", 100, "Refund", "254712345678")
    assert mock.calls[0]["payload"]["Amount"] == 100
    assert isinstance(mock.calls[0]["payload"]["Amount"], int)

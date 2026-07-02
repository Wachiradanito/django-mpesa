"""
pytest fixtures for django-mpesa.

Import all fixtures in your host app's conftest.py:

    from django_mpesa.testing.fixtures import *  # noqa

Or import selectively:

    from django_mpesa.testing.fixtures import mock_daraja, pending_stk_transaction
"""

from decimal import Decimal

import pytest

from django_mpesa.testing.factories import MpesaCallbackLogFactory, MpesaTransactionFactory
from django_mpesa.testing.mock_client import MockDarajaClient


# ------------------------------------------------------------------
# Mock client fixture
# ------------------------------------------------------------------

@pytest.fixture
def mock_daraja():
    """
    A fresh MockDarajaClient for each test. Automatically reset after
    the test so call records never leak between tests.
    """
    client = MockDarajaClient()
    yield client
    client.reset()


# ------------------------------------------------------------------
# Callback payload fixtures — exact Safaricom schema
# ------------------------------------------------------------------

@pytest.fixture
def stk_success_callback():
    """Realistic STK Push success callback payload."""
    return {
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


@pytest.fixture
def stk_failure_callback():
    """Realistic STK Push failure callback (user cancelled)."""
    return {
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
def c2b_confirmation_payload():
    """Realistic C2B confirmation callback payload."""
    return {
        "TransactionType": "Pay Bill",
        "TransID": "NLJ7RT61SV",
        "TransTime": "20191219102116",
        "TransAmount": "100.00",
        "BusinessShortCode": "174379",
        "BillRefNumber": "INV-001",
        "InvoiceNumber": "",
        "OrgAccountBalance": "10000.00",
        "ThirdPartyTransID": "",
        "MSISDN": "254712345678",
        "FirstName": "John",
        "MiddleName": "",
        "LastName": "Doe",
    }


@pytest.fixture
def b2c_result_success_payload():
    """Realistic B2C result success callback payload."""
    return {
        "Result": {
            "ResultType": 0,
            "ResultCode": 0,
            "ResultDesc": "The service request is processed successfully.",
            "OriginatorConversationID": "test_orig_123",
            "ConversationID": "test_conv_123",
            "TransactionID": "NLJ7RT61SV",
            "ResultParameters": {
                "ResultParameter": [
                    {"Key": "TransactionReceipt", "Value": "NLJ7RT61SV"},
                    {"Key": "TransactionAmount", "Value": 500},
                    {"Key": "B2CWorkingAccountAvailableFunds", "Value": 100000.00},
                    {"Key": "B2CUtilityAccountAvailableFunds", "Value": 50000.00},
                    {"Key": "TransactionCompletedDateTime", "Value": "19.12.2019 10:21:18"},
                    {"Key": "ReceiverPartyPublicName", "Value": "254712345678 - John Doe"},
                    {"Key": "B2CChargesPaidAccountAvailableFunds", "Value": 0.00},
                    {"Key": "B2CRecipientIsRegisteredCustomer", "Value": "Y"},
                ]
            },
        }
    }


@pytest.fixture
def b2c_result_failure_payload():
    """Realistic B2C result failure callback payload."""
    return {
        "Result": {
            "ResultType": 0,
            "ResultCode": 2001,
            "ResultDesc": "The initiator information is invalid.",
            "OriginatorConversationID": "test_orig_123",
            "ConversationID": "test_conv_123",
            "TransactionID": "",
        }
    }


@pytest.fixture
def b2c_timeout_payload():
    """Realistic B2C timeout callback payload."""
    return {
        "Result": {
            "ResultType": 0,
            "ResultCode": 0,
            "ResultDesc": "Request cancelled by the user.",
            "OriginatorConversationID": "test_orig_123",
            "ConversationID": "test_conv_123",
            "TransactionID": "",
        }
    }


# ------------------------------------------------------------------
# Transaction fixtures
# ------------------------------------------------------------------

@pytest.fixture
def pending_stk_transaction(db):
    """A PENDING STK Push transaction ready to receive a success callback."""
    return MpesaTransactionFactory(
        transaction_type="STK_PUSH",
        status="PENDING",
        checkout_request_id="ws_CO_test_123",
        merchant_request_id="test_merchant_456",
        phone_number="254712345678",
        amount=Decimal("100.00"),
        account_reference="INV-001",
        transaction_desc="Payment",
    )


@pytest.fixture
def pending_b2c_transaction(db):
    """A PENDING B2C transaction ready to receive a result callback."""
    return MpesaTransactionFactory(
        transaction_type="B2C",
        status="PENDING",
        checkout_request_id=None,
        conversation_id="test_conv_123",
        originator_conversation_id="test_orig_123",
        phone_number="254712345678",
        amount=Decimal("500.00"),
        account_reference="254712345678",
        transaction_desc="Payout",
    )

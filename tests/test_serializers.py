import pytest

from django_mpesa.serializers import (
    B2CResultSerializer,
    C2BConfirmationSerializer,
    STKCallbackSerializer,
)


# ------------------------------------------------------------------
# STK callback serializer
# ------------------------------------------------------------------

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


def test_stk_success_payload_valid():
    s = STKCallbackSerializer(data=STK_SUCCESS_PAYLOAD)
    assert s.is_valid(), s.errors


def test_stk_failure_payload_valid():
    s = STKCallbackSerializer(data=STK_FAILURE_PAYLOAD)
    assert s.is_valid(), s.errors


def test_stk_missing_checkout_id_invalid():
    payload = {
        "Body": {
            "stkCallback": {
                "MerchantRequestID": "merchant_123",
                # CheckoutRequestID missing
                "ResultCode": 0,
                "ResultDesc": "Success",
            }
        }
    }
    s = STKCallbackSerializer(data=payload)
    assert not s.is_valid()
    assert "CheckoutRequestID" in str(s.errors)


def test_stk_missing_body_invalid():
    s = STKCallbackSerializer(data={"wrong_key": {}})
    assert not s.is_valid()


# ------------------------------------------------------------------
# C2B confirmation serializer
# ------------------------------------------------------------------

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


def test_c2b_confirmation_payload_valid():
    s = C2BConfirmationSerializer(data=C2B_CONFIRMATION_PAYLOAD)
    assert s.is_valid(), s.errors


def test_c2b_confirmation_missing_msisdn_invalid():
    payload = {**C2B_CONFIRMATION_PAYLOAD}
    del payload["MSISDN"]
    s = C2BConfirmationSerializer(data=payload)
    assert not s.is_valid()


# ------------------------------------------------------------------
# B2C result serializer
# ------------------------------------------------------------------

B2C_SUCCESS_PAYLOAD = {
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
                {"Key": "TransactionAmount", "Value": 100},
            ]
        },
    }
}


def test_b2c_result_payload_valid():
    s = B2CResultSerializer(data=B2C_SUCCESS_PAYLOAD)
    assert s.is_valid(), s.errors


def test_b2c_result_missing_conversation_id_invalid():
    payload = {
        "Result": {
            "ResultType": 0,
            "ResultCode": 0,
            "ResultDesc": "Success",
            "OriginatorConversationID": "orig_123",
            # ConversationID missing
            "TransactionID": "NLJ7RT61SV",
        }
    }
    s = B2CResultSerializer(data=payload)
    assert not s.is_valid()
    assert "ConversationID" in str(s.errors)

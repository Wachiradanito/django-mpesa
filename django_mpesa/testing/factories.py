"""
factory_boy factories for django-mpesa test models.

These factories use Django's "app_label.ModelName" string format.
By default they point to the library's own test app models. Host apps
subclass and override the model string:

    class MyTransactionFactory(MpesaTransactionFactory):
        class Meta:
            model = "myapp.MpesaTransaction"

Import in tests:

    from django_mpesa.testing.factories import MpesaTransactionFactory

    def test_something(db):
        txn = MpesaTransactionFactory(status="PENDING")
        log = MpesaCallbackLogFactory(callback_type="STK")
"""

import uuid
from decimal import Decimal

import factory


class MpesaTransactionFactory(factory.django.DjangoModelFactory):
    """
    Factory for MpesaTransaction. Defaults to testapp.MpesaTransaction.

    Override any field by passing it as a kwarg:

        txn = MpesaTransactionFactory(
            status="SUCCESS",
            amount=Decimal("500.00"),
            checkout_request_id="ws_CO_custom",
        )
    """

    class Meta:
        # factory_boy resolves "app_label.ModelName" strings automatically
        model = "testapp.MpesaTransaction"

    id = factory.LazyFunction(uuid.uuid4)
    transaction_type = "STK_PUSH"
    status = "PENDING"
    checkout_request_id = factory.Sequence(lambda n: f"ws_CO_test_{n:04d}")
    merchant_request_id = factory.Sequence(lambda n: f"merchant_test_{n:04d}")
    conversation_id = None
    originator_conversation_id = None
    mpesa_receipt_number = None
    phone_number = "254712345678"
    amount = Decimal("100.00")
    account_reference = "TEST-ORDER"
    transaction_desc = "Test payment"
    result_code = None
    result_desc = None
    raw_callback_payload = None
    settled_at = None
    idempotency_locked = False


class MpesaCallbackLogFactory(factory.django.DjangoModelFactory):
    """
    Factory for MpesaCallbackLog. Defaults to testapp.MpesaCallbackLog.

        log = MpesaCallbackLogFactory(
            callback_type="B2C_RESULT",
            raw_body={"Result": {...}},
        )
    """

    class Meta:
        model = "testapp.MpesaCallbackLog"

    id = factory.LazyFunction(uuid.uuid4)
    callback_type = "STK"
    source_ip = "196.201.214.200"
    raw_body = factory.LazyFunction(dict)
    related_transaction_id = None
    processed = False
    error = None

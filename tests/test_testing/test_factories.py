from decimal import Decimal

import pytest

from django_mpesa.models import get_callback_log_model, get_transaction_model
from django_mpesa.testing.factories import MpesaCallbackLogFactory, MpesaTransactionFactory


def test_transaction_factory_creates_db_row(db):
    txn = MpesaTransactionFactory()
    Transaction = get_transaction_model()
    assert Transaction.objects.filter(id=txn.id).exists()


def test_transaction_factory_default_status_is_pending(db):
    txn = MpesaTransactionFactory()
    assert txn.status == "PENDING"


def test_transaction_factory_checkout_id_is_unique(db):
    t1 = MpesaTransactionFactory()
    t2 = MpesaTransactionFactory()
    assert t1.checkout_request_id != t2.checkout_request_id


def test_transaction_factory_override_status(db):
    txn = MpesaTransactionFactory(status="SUCCESS")
    assert txn.status == "SUCCESS"


def test_transaction_factory_override_amount(db):
    txn = MpesaTransactionFactory(amount=Decimal("999.00"))
    assert txn.amount == Decimal("999.00")


def test_callback_log_factory_creates_db_row(db):
    log = MpesaCallbackLogFactory()
    CallbackLog = get_callback_log_model()
    assert CallbackLog.objects.filter(id=log.id).exists()


def test_callback_log_factory_default_callback_type(db):
    log = MpesaCallbackLogFactory()
    assert log.callback_type == "STK"


def test_callback_log_factory_override_type(db):
    log = MpesaCallbackLogFactory(callback_type="B2C_RESULT")
    assert log.callback_type == "B2C_RESULT"


def test_transaction_factory_b2c_type(db):
    txn = MpesaTransactionFactory(
        transaction_type="B2C",
        checkout_request_id=None,
        conversation_id="test_conv_unique_999",
    )
    assert txn.transaction_type == "B2C"
    assert txn.conversation_id == "test_conv_unique_999"

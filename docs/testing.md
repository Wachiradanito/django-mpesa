# Testing

The library ships a `MockDarajaClient` and pytest fixtures so your test suite never needs Safaricom's sandbox to be reachable.

## Install test extras

```bash
pip install django-mpesa[test]
```

## MockDarajaClient

Drop-in replacement for `BaseDarajaClient`. Returns canned responses without any network calls.

```python
from django_mpesa.testing import MockDarajaClient
from django_mpesa.services import STKPushService

def test_stk_push_creates_pending_transaction(db):
    mock = MockDarajaClient()
    service = STKPushService(client=mock)
    txn = service.initiate(
        phone_number="254712345678",
        amount=100,
        account_reference="INV-001",
        transaction_desc="Payment",
    )
    assert txn.status == "PENDING"
    assert txn.checkout_request_id == "ws_CO_test_123"
    mock.assert_called_once_with_path("/mpesa/stkpush/v1/processrequest")
```

### Simulate errors

```python
from django_mpesa.exceptions import DarajaAPIError

def test_handles_daraja_error(db):
    mock = MockDarajaClient()
    mock.set_raise(
        "/mpesa/stkpush/v1/processrequest",
        DarajaAPIError("Daraja is down"),
    )
    service = STKPushService(client=mock)
    with pytest.raises(DarajaAPIError):
        service.initiate("254712345678", 100, "INV-001", "Payment")
```

### Custom responses

```python
mock = MockDarajaClient(responses={
    "/mpesa/stkpush/v1/processrequest": {
        "ResponseCode": "0",
        "CheckoutRequestID": "ws_CO_my_custom_id",
        "MerchantRequestID": "my_merchant",
        "ResponseDescription": "Success",
    }
})
```

## pytest fixtures

Import in your `conftest.py`:

```python
# conftest.py
from django_mpesa.testing.fixtures import *  # noqa
```

Available fixtures:

| Fixture | Description |
|---|---|
| `mock_daraja` | Fresh `MockDarajaClient`, reset after each test |
| `stk_success_callback` | Realistic STK success callback payload dict |
| `stk_failure_callback` | Realistic STK failure callback (result code 1032) |
| `c2b_confirmation_payload` | Realistic C2B confirmation payload |
| `b2c_result_success_payload` | Realistic B2C result success payload |
| `b2c_result_failure_payload` | Realistic B2C result failure payload |
| `b2c_timeout_payload` | Realistic B2C timeout payload |
| `pending_stk_transaction` | `PENDING` STK transaction ready for a callback |
| `pending_b2c_transaction` | `PENDING` B2C transaction ready for a callback |

## Testing callbacks directly

```python
from django_mpesa.tasks import process_stk_callback
from django_mpesa.models import get_callback_log_model

def test_callback_settles_transaction(db, pending_stk_transaction, stk_success_callback):
    CallbackLog = get_callback_log_model()
    log = CallbackLog.objects.create(
        callback_type="STK",
        source_ip="196.201.214.200",
        raw_body=stk_success_callback,
    )
    process_stk_callback(str(log.id))

    pending_stk_transaction.refresh_from_db()
    assert pending_stk_transaction.status == "SUCCESS"
    assert pending_stk_transaction.mpesa_receipt_number == "NLJ7RT61SV"
```

## Testing signal receivers

```python
from django_mpesa.signals import payment_confirmed

def test_signal_fires(db, pending_stk_transaction, stk_success_callback):
    received = []

    def _receiver(sender, transaction, **kwargs):
        received.append(transaction.id)

    payment_confirmed.connect(_receiver)
    # ... process callback ...
    payment_confirmed.disconnect(_receiver)

    assert len(received) == 1
```

## Idempotency testing

For the full concurrency test pattern (requires PostgreSQL), see `tests/test_idempotency.py` in the library source.

The sequential test (works on SQLite) verifies the terminal state check:

```python
def test_duplicate_callback_is_noop(db, pending_stk_transaction):
    # Process same callback twice
    process_stk_callback(str(log1.id))
    first_settled_at = pending_stk_transaction.settled_at

    process_stk_callback(str(log2.id))
    pending_stk_transaction.refresh_from_db()

    # settled_at must not be overwritten
    assert pending_stk_transaction.settled_at == first_settled_at
```

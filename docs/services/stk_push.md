# STK Push

Triggers the M-PESA PIN prompt on the customer's phone (Lipa Na M-PESA Online).

## Initiate a payment

```python
from django_mpesa.services import STKPushService

service = STKPushService()
txn = service.initiate(
    phone_number="254712345678",  # or "0712345678"
    amount=100,                   # KES, integer or Decimal
    account_reference="INV-001",  # max 12 chars
    transaction_desc="Payment",   # max 13 chars
)
# txn.status == "PENDING"
# txn.checkout_request_id == "ws_CO_..."
```

The transaction is `PENDING` until Safaricom delivers the callback.

## Query status

Use this when the callback hasn't arrived within a reasonable window:

```python
result = service.query(txn.checkout_request_id)
# Returns raw Daraja response dict. Does not update the transaction.
```

## Callback

Safaricom POSTs to `STK_CALLBACK_URL`. The library settles the transaction and fires `payment_confirmed` or `payment_failed`.

## Validation rules

- `phone_number`: normalised to `2547XXXXXXXX`. Accepts `0712345678`, `+254712345678`, etc.
- `amount`: must be positive, max 2 decimal places
- `account_reference`: max 12 characters
- `transaction_desc`: max 13 characters

All validation runs before any network call. Invalid inputs raise `DarajaValidationError`.

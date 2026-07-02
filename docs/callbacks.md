# Callbacks

Safaricom sends callbacks via HTTP POST to the URLs you register. The library handles them with a log-first, acknowledge-immediately, process-async pattern.

## Why this pattern

Safaricom's callback delivery has its own timeout. If your endpoint is slow (e.g. because you're sending an SMS or updating a wallet), Safaricom may consider the delivery failed and retry — causing duplicate callbacks.

The library solves this by:

1. **Logging** the raw payload immediately, unconditionally.
2. **Acknowledging** Safaricom with `{"ResultCode": 0}` before any business logic runs.
3. **Processing** in a Celery task (or synchronously if `USE_CELERY=False`).

## Idempotency

Safaricom may deliver the same callback multiple times. The library guarantees a transaction is settled exactly once through a combination of:

- `select_for_update()` — serialises concurrent deliveries of the same callback
- Terminal state check — if the transaction is already `SUCCESS`/`FAILED`/`TIMEOUT`/`REVERSED`, the second delivery is a silent no-op
- Database unique constraint on `checkout_request_id` / `conversation_id`

## URL setup

```python
# urls.py
urlpatterns = [
    path("mpesa/", include("django_mpesa.urls")),
]
```

This exposes:

| Path | Callback type |
|---|---|
| `/mpesa/stk/callback/` | STK Push |
| `/mpesa/c2b/validate/` | C2B validation |
| `/mpesa/c2b/confirm/` | C2B confirmation |
| `/mpesa/b2c/result/` | B2C result |
| `/mpesa/b2c/timeout/` | B2C timeout |

The paths in your `MPESA` settings must exactly match the URLs you expose.

## IP allowlist

By default, only requests from Safaricom's published IP ranges are accepted. Non-Safaricom IPs receive HTTP 403. Disable for local development:

```python
MPESA = {
    "VERIFY_CALLBACK_SOURCE_IP": False,  # local dev only
}
```

## C2B validation

The C2B validation callback is the only one that can reject a transaction. Connect a receiver to `c2b_validation_received` and return a rejection dict:

```python
from django_mpesa.signals import c2b_validation_received

@receiver(c2b_validation_received)
def validate_payment(sender, raw_payload, **kwargs):
    bill_ref = raw_payload.get("BillRefNumber", "")
    if not Order.objects.filter(reference=bill_ref, status="OPEN").exists():
        return {"ResultCode": "C2B00012", "ResultDesc": "Invalid reference"}
    # Return None or a success dict to accept
    return {"ResultCode": 0, "ResultDesc": "Accepted"}
```

# Models

The library ships abstract base models. You subclass them and run your own migrations.

## AbstractMpesaTransaction

| Field | Type | Description |
|---|---|---|
| `id` | UUID (PK) | Internal primary key. Never expose to Safaricom. |
| `transaction_type` | CharField | `STK_PUSH`, `C2B`, `B2C`, or `REVERSAL` |
| `status` | CharField | `PENDING`, `PROCESSING`, `SUCCESS`, `FAILED`, `TIMEOUT`, `REVERSED` |
| `checkout_request_id` | CharField (unique, null) | STK Push idempotency key |
| `merchant_request_id` | CharField (null) | STK Push cross-reference |
| `conversation_id` | CharField (unique, null) | B2C/Reversal idempotency key |
| `originator_conversation_id` | CharField (null) | B2C/Reversal reference |
| `mpesa_receipt_number` | CharField (null) | M-PESA receipt. Set only on `SUCCESS`. |
| `phone_number` | CharField | E.164 format: `2547XXXXXXXX` |
| `amount` | DecimalField(12,2) | Payment amount in KES. Never float. |
| `account_reference` | CharField (max 12) | Reference tied to order/invoice |
| `transaction_desc` | CharField (max 13) | Human-readable description |
| `result_code` | IntegerField (null) | Safaricom result code. `0` = success. |
| `result_desc` | TextField (null) | Safaricom result description |
| `raw_callback_payload` | JSONField (null) | Full callback body for audit/debug |
| `initiated_at` | DateTimeField | Auto-set at creation |
| `settled_at` | DateTimeField (null) | Set once when reaching a terminal state |
| `idempotency_locked` | BooleanField | Internal fencing token |

## AbstractMpesaCallbackLog

Every inbound callback — valid, invalid, malformed, duplicate — is logged here before any business logic runs.

| Field | Type | Description |
|---|---|---|
| `id` | UUID (PK) | |
| `callback_type` | CharField | `STK`, `C2B_VALIDATION`, `C2B_CONFIRMATION`, `B2C_RESULT`, `B2C_TIMEOUT` |
| `source_ip` | GenericIPAddressField | Source IP of the callback |
| `raw_body` | JSONField | Full request body, stored before any validation |
| `related_transaction_id` | UUID (null) | Linked after processing |
| `processed` | BooleanField | `True` after processing completes |
| `error` | TextField (null) | Error message if processing failed |
| `received_at` | DateTimeField | Auto-set at receipt |

## Example host-app implementation

```python
# myapp/models.py
from django.db import models
from django.conf import settings
from django_mpesa.models import AbstractMpesaTransaction, AbstractMpesaCallbackLog

class MpesaTransaction(AbstractMpesaTransaction):
    # Add your domain-specific fields here
    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.PROTECT,
        null=True, blank=True,
    )
    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
    )

    class Meta(AbstractMpesaTransaction.Meta):
        verbose_name = "M-PESA Transaction"

class MpesaCallbackLog(AbstractMpesaCallbackLog):
    class Meta(AbstractMpesaCallbackLog.Meta):
        verbose_name = "M-PESA Callback Log"
```

```python
# settings.py
MPESA = {
    "TRANSACTION_MODEL": "myapp.MpesaTransaction",
    "CALLBACK_LOG_MODEL": "myapp.MpesaCallbackLog",
}
```

The library **never** imports your concrete model directly. All model access goes through `django.apps.apps.get_model()` using the string you configure. This means you can change your model or app name without touching library code.

# Reversal

Reverse a completed M-PESA transaction.

```python
from django_mpesa.services import ReversalService

service = ReversalService()
result = service.reverse(
    transaction_id="NLJ7RT61SV",
    amount=100,
    remarks="Customer refund",
    receiver_party="174379",
)
```

The original transaction's status is updated to `REVERSED` **only** after the reversal result callback confirms success — never on the initiate response. The `reversal_completed` signal fires when confirmed.

```python
from django_mpesa.signals import reversal_completed

@receiver(reversal_completed)
def on_reversal(sender, transaction, **kwargs):
    transaction.order.mark_refunded()
```

Requires `INITIATOR_NAME` and `SECURITY_CREDENTIAL` in settings.

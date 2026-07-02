# Signals

Signals are the contract between the library and your application at settlement time. Connect receivers in your app to react to payments without modifying library code.

All signals fire **after** the database row lock is released, so slow receivers never cause lock contention.

## Signal catalog

| Signal | When it fires | kwargs |
|---|---|---|
| `payment_confirmed` | STK Push or C2B payment confirmed | `transaction` |
| `payment_failed` | STK Push or C2B payment failed | `transaction`, `result_code`, `result_desc` |
| `c2b_validation_received` | C2B validation callback received (pre-transaction) | `raw_payload` |
| `payout_completed` | B2C payout confirmed successful | `transaction` |
| `payout_failed` | B2C payout failed or timed out | `transaction`, `result_code`, `result_desc` |
| `reversal_completed` | Reversal confirmed by callback | `transaction` |
| `balance_received` | Account balance callback received | `raw_payload` |

## Example receivers

```python
# myapp/receivers.py
from django.dispatch import receiver
from django_mpesa.signals import (
    payment_confirmed, payment_failed,
    payout_completed, payout_failed,
)

@receiver(payment_confirmed)
def on_payment_confirmed(sender, transaction, **kwargs):
    """Credit the customer's order when payment is confirmed."""
    order = transaction.order
    order.mark_paid()

@receiver(payment_failed)
def on_payment_failed(sender, transaction, result_code, result_desc, **kwargs):
    """Notify the customer when payment fails."""
    send_sms.delay(
        transaction.phone_number,
        f"Payment failed: {result_desc}. Please try again.",
    )

@receiver(payout_completed)
def on_payout_completed(sender, transaction, **kwargs):
    """Update seller balance after payout."""
    seller = transaction.order.seller
    seller.record_payout(transaction.amount)

@receiver(payout_failed)
def on_payout_failed(sender, transaction, result_code, result_desc, **kwargs):
    """Alert finance team on failed payout."""
    notify_finance.delay(transaction.id, result_code, result_desc)
```

Make sure receivers are imported at startup. Put the import in your `AppConfig.ready()`:

```python
# myapp/apps.py
class MyAppConfig(AppConfig):
    def ready(self):
        import myapp.receivers  # noqa: F401
```

## Receiver exceptions

If a receiver raises an exception, it is logged and the transaction settlement is **not** rolled back. The transaction is already committed to the database before signals fire. A failing receiver is a notification problem, not a settlement problem.

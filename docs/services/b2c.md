# B2C (Business to Customer)

Send money from your business account to a customer's phone — payouts, salaries, refunds.

## Send a payout

```python
from django_mpesa.services import B2CService

service = B2CService()
txn = service.send_payment(
    phone_number="254712345678",
    amount=500,
    remarks="Seller payout",
    command_id="BusinessPayment",  # or "SalaryPayment", "PromotionPayment"
)
# txn.status == "PENDING"
# Terminal status arrives via B2C_RESULT_URL callback
```

## React to the result

```python
from django_mpesa.signals import payout_completed, payout_failed

@receiver(payout_completed)
def on_payout(sender, transaction, **kwargs):
    seller = transaction.order.seller
    seller.record_payout(transaction.amount)

@receiver(payout_failed)
def on_payout_failed(sender, transaction, result_code, result_desc, **kwargs):
    notify_finance(transaction.id, result_code)
```

## Security credential

B2C requires `INITIATOR_NAME` and `SECURITY_CREDENTIAL` in your settings. See the [Security guide](../security.md) for how to generate the credential.

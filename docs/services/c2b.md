# C2B (Customer to Business)

Receive payments from customers who pay via paybill or till.

## Register callback URLs

One-time setup. Run once during deployment:

```python
from django_mpesa.services import C2BService

service = C2BService()
service.register_urls()  # response_type="Completed" (default)
```

## Simulate a payment (sandbox only)

```python
service.simulate(
    phone_number="254712345678",
    amount=100,
    bill_ref="INV-001",
)
```

Raises `DarajaConfigError` if called in production.

## Validate and confirm

C2B payments arrive via callbacks, not initiated by you. Wire up the URLs and connect signal receivers:

```python
from django_mpesa.signals import c2b_validation_received, payment_confirmed

@receiver(c2b_validation_received)
def validate(sender, raw_payload, **kwargs):
    if not Order.objects.filter(reference=raw_payload["BillRefNumber"]).exists():
        return {"ResultCode": "C2B00012", "ResultDesc": "Invalid reference"}

@receiver(payment_confirmed)
def on_confirmed(sender, transaction, **kwargs):
    transaction.order.mark_paid()
```

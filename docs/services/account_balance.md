# Account Balance

Query your M-PESA business account balance. The actual balance arrives via a callback.

```python
from django_mpesa.services import AccountBalanceService

service = AccountBalanceService()
result = service.query(identifier_type="4")  # 4=shortcode (default)
```

The method returns a synchronous acknowledgement dict confirming the query was accepted. The balance is delivered via `B2C_RESULT_URL` callback and fires the `balance_received` signal:

```python
from django_mpesa.signals import balance_received

@receiver(balance_received)
def on_balance(sender, raw_payload, **kwargs):
    print(raw_payload)
```

# Transaction Status

Query the status of a transaction by its M-PESA transaction ID. Use this for reconciliation when a transaction is stuck `PENDING`.

```python
from django_mpesa.services import TransactionStatusService

service = TransactionStatusService()
result = service.query(
    transaction_id="NLJ7RT61SV",
    identifier_type="4",  # "1"=MSISDN, "2"=till, "4"=shortcode (default)
)
```

Returns the raw Daraja response dict. Does **not** update any transaction record — you decide what to do with the result.

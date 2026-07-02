# django-mpesa

A production-hardened Django app for Safaricom's Daraja M-PESA API.

Extracted from production use in [Zaruni](https://zaruni.com) and packaged for reuse across any Django project that needs to collect or send money via M-PESA.

---

## Features

| Feature | Description |
|---|---|
| STK Push | Trigger the M-PESA PIN prompt on a customer's phone |
| C2B | Receive paybill/till payments with validation and confirmation callbacks |
| B2C | Send payouts, salaries, or refunds to phone numbers |
| Transaction Status | Query stuck payments for reconciliation |
| Account Balance | Check your M-PESA business account balance |
| Reversal | Reverse a transaction programmatically |
| Idempotent callbacks | Safaricom retries are handled safely — a payment is settled exactly once |
| IP allowlist middleware | Rejects callbacks from non-Safaricom sources |
| Mock client | Full test suite runs with zero network access |
| Swappable models | Subclass the abstract models and add your own domain fields |
| Django signals | Hook into `payment_confirmed`, `payout_completed`, etc. |

## Compatibility

| | Supported versions |
|---|---|
| Python | 3.10, 3.11, 3.12 |
| Django | 4.2 LTS, 5.0 |
| djangorestframework | ≥ 3.14 |
| requests | ≥ 2.31 |
| Celery (optional) | ≥ 5.3 |

## Quick install

```bash
pip install mainfinity-django-mpesa

# With Celery support:
pip install mainfinity-django-mpesa[celery]
```

See the [quickstart guide](quickstart.md) to go from install to a working STK Push in under 10 minutes.

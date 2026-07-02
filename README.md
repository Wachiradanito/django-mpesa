# mainfinity-django-mpesa

[![PyPI version](https://img.shields.io/pypi/v/mainfinity-django-mpesa.svg)](https://pypi.org/project/mainfinity-django-mpesa/)
[![CI](https://github.com/Wachiradanito/django-mpesa/actions/workflows/test.yml/badge.svg)](https://github.com/Wachiradanito/django-mpesa/actions/workflows/test.yml)
[![Coverage](https://codecov.io/gh/Wachiradanito/django-mpesa/branch/main/graph/badge.svg)](https://codecov.io/gh/Wachiradanito/django-mpesa)
[![Python versions](https://img.shields.io/pypi/pyversions/mainfinity-django-mpesa.svg)](https://pypi.org/project/mainfinity-django-mpesa/)
[![Django versions](https://img.shields.io/badge/django-4.2%20%7C%205.1-blue)](https://pypi.org/project/mainfinity-django-mpesa/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)

A production-hardened Django app for Safaricom's Daraja M-PESA API.

Extracted from production use in [Zaruni](https://zaruni.com) and packaged for reuse across any Django project that needs to collect or send money via M-PESA.

---

## Features

- **STK Push** — trigger the M-PESA PIN prompt on a customer's phone
- **C2B** — receive paybill/till payments with validation and confirmation callbacks
- **B2C** — send payouts, salaries, or refunds to phone numbers
- **Transaction Status** — query stuck payments for reconciliation
- **Account Balance** — check your M-PESA business account balance
- **Reversal** — reverse a transaction programmatically
- **Idempotent callbacks** — Safaricom retries are handled safely; a payment is settled exactly once
- **IP allowlist middleware** — rejects callbacks from non-Safaricom sources
- **Mock client** — full test suite runs with zero network access; ships a `MockDarajaClient` for your own tests
- **Swappable models** — subclass the abstract models and add your own fields (orders, users, wallets)
- **Django signals** — hook into `payment_confirmed`, `payout_completed`, etc. without modifying library code

## Requirements

- Python 3.10, 3.11, or 3.12
- Django 4.2 or 5.1
- djangorestframework ≥ 3.14
- requests ≥ 2.31
- Celery ≥ 5.3 *(optional — set `USE_CELERY=False` for synchronous processing)*

## Installation

```bash
pip install mainfinity-django-mpesa

# With Celery support:
pip install mainfinity-django-mpesa[celery]
```

## Quick start

See the full [quickstart guide](https://mainfinity-django-mpesa.readthedocs.io/en/stable/quickstart/) to go from install to a working STK Push in under 10 minutes.

```python
# 1. Add to INSTALLED_APPS
INSTALLED_APPS = [
    ...
    "django_mpesa",
]

# 2. Configure
MPESA = {
    "ENV": "sandbox",
    "CONSUMER_KEY": lambda: os.environ["MPESA_CONSUMER_KEY"],
    "CONSUMER_SECRET": lambda: os.environ["MPESA_CONSUMER_SECRET"],
    "SHORTCODE": "174379",
    "PASSKEY": lambda: os.environ["MPESA_PASSKEY"],
    "STK_CALLBACK_URL": "https://yourapp.com/mpesa/stk/callback/",
    "TRANSACTION_MODEL": "myapp.MpesaTransaction",
    "CALLBACK_LOG_MODEL": "myapp.MpesaCallbackLog",
}

# 3. Include URLs
urlpatterns = [
    path("mpesa/", include("django_mpesa.urls")),
]

# 4. Initiate a payment
from django_mpesa.services import STKPushService

txn = STKPushService().initiate(
    phone_number="254712345678",
    amount=100,
    account_reference="INV-001",
    transaction_desc="Payment",
)

# 5. React to the callback
from django.dispatch import receiver
from django_mpesa.signals import payment_confirmed

@receiver(payment_confirmed)
def on_payment(sender, transaction, **kwargs):
    order = transaction.order
    order.mark_paid()
```

## Documentation

Full documentation at [mainfinity-django-mpesa.readthedocs.io](https://mainfinity-django-mpesa.readthedocs.io).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). All PRs touching `tasks.py` must include or update the idempotency concurrency test.

## License

MIT — see [LICENSE](LICENSE).

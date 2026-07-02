# Quickstart

From `pip install` to a working STK Push in under 10 minutes.

---

## 1. Install

```bash
pip install mainfinity-django-mpesa

# With Celery (recommended for production):
pip install mainfinity-django-mpesa[celery]
```

## 2. Add to INSTALLED_APPS

```python
INSTALLED_APPS = [
    ...
    "django_mpesa",
]
```

## 3. Subclass the abstract models

Create your concrete models by subclassing. Add any domain fields you need (order FK, user FK, etc.).

```python
# myapp/models.py
from django.db import models
from django.conf import settings
from django_mpesa.models import AbstractMpesaTransaction, AbstractMpesaCallbackLog

class MpesaTransaction(AbstractMpesaTransaction):
    # Add your own fields here
    order = models.ForeignKey("orders.Order", on_delete=models.PROTECT, null=True)

    class Meta(AbstractMpesaTransaction.Meta):
        pass

class MpesaCallbackLog(AbstractMpesaCallbackLog):
    class Meta(AbstractMpesaCallbackLog.Meta):
        pass
```

Then run migrations:

```bash
python manage.py makemigrations
python manage.py migrate
```

## 4. Configure settings

```python
# settings.py
import os

MPESA = {
    "ENV": "sandbox",  # "sandbox" or "production"

    # Use callables so secrets come from env vars, not source code
    "CONSUMER_KEY": lambda: os.environ["MPESA_CONSUMER_KEY"],
    "CONSUMER_SECRET": lambda: os.environ["MPESA_CONSUMER_SECRET"],
    "SHORTCODE": "174379",
    "PASSKEY": lambda: os.environ["MPESA_PASSKEY"],

    # Your callback URLs — must be publicly reachable HTTPS in production
    # Use ngrok for local development: ngrok http 8000
    "STK_CALLBACK_URL": "https://yourapp.com/mpesa/stk/callback/",

    # Point to your concrete models
    "TRANSACTION_MODEL": "myapp.MpesaTransaction",
    "CALLBACK_LOG_MODEL": "myapp.MpesaCallbackLog",

    # Set to False if not using Celery
    "USE_CELERY": True,
}
```

Get free sandbox credentials at [developer.safaricom.co.ke](https://developer.safaricom.co.ke).

## 5. Wire up URLs

```python
# urls.py
from django.urls import path, include

urlpatterns = [
    path("mpesa/", include("django_mpesa.urls")),
]
```

## 6. Validate your configuration

```bash
python manage.py mpesa_check_config
```

All checks should print `[OK]`. Fix any `[FAIL]` lines before going further.

## 7. Initiate an STK Push

```python
from django_mpesa.services import STKPushService

service = STKPushService()
txn = service.initiate(
    phone_number="254712345678",  # or "0712345678"
    amount=100,
    account_reference="INV-001",  # max 12 chars
    transaction_desc="Payment",   # max 13 chars
)
print(txn.status)           # "PENDING"
print(txn.checkout_request_id)  # "ws_CO_..."
```

## 8. React to the callback

Connect a receiver to the `payment_confirmed` signal. This fires after Safaricom delivers the callback and the payment is confirmed.

```python
# myapp/receivers.py
from django.dispatch import receiver
from django_mpesa.signals import payment_confirmed, payment_failed

@receiver(payment_confirmed)
def on_payment_confirmed(sender, transaction, **kwargs):
    # transaction.order is available if you added that FK
    order = transaction.order
    order.mark_paid()
    print(f"Payment confirmed: KES {transaction.amount} receipt {transaction.mpesa_receipt_number}")

@receiver(payment_failed)
def on_payment_failed(sender, transaction, result_code, result_desc, **kwargs):
    print(f"Payment failed: {result_code} — {result_desc}")
```

Make sure your receivers are imported at startup (e.g. in your `AppConfig.ready()`).

## 9. Run the config check one more time

```bash
python manage.py mpesa_check_config
```

You're done. For production, see the [Security guide](security.md).

"""
Django signals for django-mpesa.

Signals are the contract between the library and the host application
at settlement time. The library fires signals; host apps connect receivers.

All settlement signals fire AFTER the database transaction commits
(outside the select_for_update block) so slow receivers never hold
the row lock open.

Signal kwargs
-------------
payment_confirmed    : sender=Transaction class, transaction=<instance>
payment_failed       : sender=Transaction class, transaction=<instance>,
                       result_code=<int>, result_desc=<str>
c2b_validation_received : sender=C2BValidationView class, raw_payload=<dict>
payout_completed     : sender=Transaction class, transaction=<instance>
payout_failed        : sender=Transaction class, transaction=<instance>,
                       result_code=<int|None>, result_desc=<str>
reversal_completed   : sender=Transaction class, transaction=<instance>
balance_received     : sender=AccountBalanceService class, raw_payload=<dict>

Example usage in a host app
----------------------------
    from django.dispatch import receiver
    from django_mpesa.signals import payment_confirmed

    @receiver(payment_confirmed)
    def on_payment_confirmed(sender, transaction, **kwargs):
        transaction.order.mark_paid()
"""

from django.dispatch import Signal

# STK Push and C2B settlement signals
payment_confirmed = Signal()
payment_failed = Signal()

# C2B validation (pre-transaction, view layer)
c2b_validation_received = Signal()

# B2C payout signals
payout_completed = Signal()
payout_failed = Signal()

# Reversal signal
reversal_completed = Signal()

# Account balance signal (no transaction model involved)
balance_received = Signal()

__all__ = [
    "payment_confirmed",
    "payment_failed",
    "c2b_validation_received",
    "payout_completed",
    "payout_failed",
    "reversal_completed",
    "balance_received",
]

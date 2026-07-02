"""
Abstract base models for django-mpesa.

All models are abstract — the library ships no migrations. Host apps
subclass these, add their own domain fields, and run makemigrations
in their own app.

The library accesses concrete models exclusively through the helper
functions get_transaction_model() and get_callback_log_model(), never
via a direct import of a concrete class.
"""

import uuid

from django.db import models

from django_mpesa.conf import mpesa_settings

# ------------------------------------------------------------------
# Choices and constants — importable by host apps
# ------------------------------------------------------------------

TRANSACTION_TYPE_CHOICES = [
    ("STK_PUSH", "STK Push"),
    ("C2B", "C2B"),
    ("B2C", "B2C"),
    ("REVERSAL", "Reversal"),
]

STATUS_CHOICES = [
    ("PENDING", "Pending"),
    ("PROCESSING", "Processing"),
    ("SUCCESS", "Success"),
    ("FAILED", "Failed"),
    ("TIMEOUT", "Timeout"),
    ("REVERSED", "Reversed"),
]

# Terminal states — once a transaction reaches one of these, no further
# status transitions are allowed. This set is checked in tasks.py for
# idempotency.
TERMINAL_STATES = frozenset({"SUCCESS", "FAILED", "TIMEOUT", "REVERSED"})

CALLBACK_TYPE_CHOICES = [
    ("STK", "STK Push Callback"),
    ("C2B_VALIDATION", "C2B Validation"),
    ("C2B_CONFIRMATION", "C2B Confirmation"),
    ("B2C_RESULT", "B2C Result"),
    ("B2C_TIMEOUT", "B2C Timeout"),
]


# ------------------------------------------------------------------
# Model access helpers
# ------------------------------------------------------------------

def get_transaction_model():
    """
    Return the concrete transaction model class configured in settings.

    Called at use-time (not import-time) so it works even before the
    Django app registry is fully ready.
    """
    from django.apps import apps
    model_string = mpesa_settings.TRANSACTION_MODEL
    try:
        app_label, model_name = model_string.rsplit(".", 1)
        return apps.get_model(app_label, model_name)
    except (ValueError, LookupError) as exc:
        from django_mpesa.exceptions import DarajaConfigError
        raise DarajaConfigError(
            f"MPESA['TRANSACTION_MODEL'] = {model_string!r} could not be resolved. "
            f"Make sure the app is in INSTALLED_APPS and the model exists."
        ) from exc


def get_callback_log_model():
    """
    Return the concrete callback log model class configured in settings.
    """
    from django.apps import apps
    model_string = mpesa_settings.CALLBACK_LOG_MODEL
    try:
        app_label, model_name = model_string.rsplit(".", 1)
        return apps.get_model(app_label, model_name)
    except (ValueError, LookupError) as exc:
        from django_mpesa.exceptions import DarajaConfigError
        raise DarajaConfigError(
            f"MPESA['CALLBACK_LOG_MODEL'] = {model_string!r} could not be resolved. "
            f"Make sure the app is in INSTALLED_APPS and the model exists."
        ) from exc


# ------------------------------------------------------------------
# Abstract models
# ------------------------------------------------------------------

class AbstractMpesaTransaction(models.Model):
    """
    Abstract base model for M-PESA transactions.

    Host apps subclass this and add their own domain fields:

        class MpesaTransaction(AbstractMpesaTransaction):
            order = models.ForeignKey("orders.Order", ...)
            initiated_by = models.ForeignKey(settings.AUTH_USER_MODEL, ...)

    Register the concrete model in settings:
        MPESA = {
            "TRANSACTION_MODEL": "myapp.MpesaTransaction",
        }
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    transaction_type = models.CharField(
        max_length=20,
        choices=TRANSACTION_TYPE_CHOICES,
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="PENDING",
    )

    # Idempotency keys — unique=True is the DB-level deduplication guard.
    # null=True is required because only one key applies per transaction type.
    # Django allows multiple nulls for a unique field (SQL NULL != NULL).
    checkout_request_id = models.CharField(
        max_length=200,
        unique=True,
        null=True,
        blank=True,
        help_text="STK Push idempotency key (CheckoutRequestID from Daraja).",
    )
    merchant_request_id = models.CharField(
        max_length=200,
        null=True,
        blank=True,
        help_text="STK Push MerchantRequestID from Daraja.",
    )
    conversation_id = models.CharField(
        max_length=200,
        unique=True,
        null=True,
        blank=True,
        help_text="B2C / Reversal idempotency key (ConversationID from Daraja).",
    )
    originator_conversation_id = models.CharField(
        max_length=200,
        null=True,
        blank=True,
        help_text="B2C / Reversal OriginatorConversationID from Daraja.",
    )

    mpesa_receipt_number = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text="Safaricom M-PESA receipt number. Populated only on SUCCESS.",
    )

    phone_number = models.CharField(
        max_length=15,
        help_text="Phone number in E.164 format: 2547XXXXXXXX.",
    )
    # DecimalField, never FloatField — floating-point binary representation
    # of money is a well-known bug class.
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Payment amount in KES.",
    )
    account_reference = models.CharField(
        max_length=12,
        help_text="Account reference (max 12 chars per Daraja spec).",
    )
    transaction_desc = models.CharField(
        max_length=13,
        help_text="Transaction description (max 13 chars per Daraja spec).",
    )

    result_code = models.IntegerField(
        null=True,
        blank=True,
        help_text="Raw Safaricom result code from callback. 0 = success.",
    )
    result_desc = models.TextField(
        null=True,
        blank=True,
        help_text="Raw Safaricom result description from callback.",
    )
    raw_callback_payload = models.JSONField(
        null=True,
        blank=True,
        help_text="Full deserialized callback body for audit and debug.",
    )

    initiated_at = models.DateTimeField(auto_now_add=True)
    settled_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Set exactly once when the transaction reaches a terminal state.",
    )

    # Fencing token used inside select_for_update to signal mid-settlement state.
    idempotency_locked = models.BooleanField(default=False)

    class Meta:
        abstract = True
        ordering = ["-initiated_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["phone_number"]),
            models.Index(fields=["initiated_at"]),
        ]

    def __str__(self) -> str:
        return (
            f"{self.transaction_type} {self.status} "
            f"KES {self.amount} {self.phone_number}"
        )


class AbstractMpesaCallbackLog(models.Model):
    """
    Abstract base model for raw M-PESA callback logs.

    Every inbound callback — valid, invalid, malformed, duplicate — is
    persisted here before any business logic runs. This is the forensic
    audit trail for support queries and debugging.

    Host apps subclass this:

        class MpesaCallbackLog(AbstractMpesaCallbackLog):
            pass

    Register via:
        MPESA = {"CALLBACK_LOG_MODEL": "myapp.MpesaCallbackLog"}
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    callback_type = models.CharField(
        max_length=30,
        choices=CALLBACK_TYPE_CHOICES,
    )
    source_ip = models.GenericIPAddressField(
        help_text="IP address from which the callback was received.",
    )
    raw_body = models.JSONField(
        help_text="Full deserialized request body, stored before any validation.",
    )

    # Linked after processing — null if no matching transaction found
    # (FK is to the string model name to avoid importing a concrete model)
    related_transaction_id = models.UUIDField(
        null=True,
        blank=True,
        help_text="UUID of the related transaction, linked after processing.",
    )

    processed = models.BooleanField(
        default=False,
        help_text="True after the processing task completes successfully.",
    )
    error = models.TextField(
        null=True,
        blank=True,
        help_text="Error message if processing failed.",
    )
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True
        ordering = ["-received_at"]

    def __str__(self) -> str:
        return (
            f"{self.callback_type} from {self.source_ip} "
            f"at {self.received_at}"
        )

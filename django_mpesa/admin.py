"""
Optional admin mixins for django-mpesa.

Nothing is auto-registered. Host apps opt in:

    from django.contrib import admin
    from django_mpesa.admin import MpesaTransactionAdminMixin
    from myapp.models import MpesaTransaction

    @admin.register(MpesaTransaction)
    class MpesaTransactionAdmin(MpesaTransactionAdminMixin, admin.ModelAdmin):
        pass
"""

from django.contrib import admin
from django.utils.html import format_html

STATUS_BADGE_COLORS = {
    "PENDING": "#f59e0b",
    "PROCESSING": "#3b82f6",
    "SUCCESS": "#10b981",
    "FAILED": "#ef4444",
    "TIMEOUT": "#6b7280",
    "REVERSED": "#8b5cf6",
}


class MpesaTransactionAdminMixin:
    """
    Mixin for MpesaTransaction admin views.

    All fields are read-only — transactions are the system's source of
    financial truth and must not be edited via the admin UI.
    """

    list_display = [
        "id",
        "transaction_type",
        "status_badge",
        "phone_number",
        "amount",
        "mpesa_receipt_number",
        "account_reference",
        "initiated_at",
        "settled_at",
    ]
    list_filter = ["status", "transaction_type", "initiated_at"]
    search_fields = [
        "phone_number",
        "checkout_request_id",
        "conversation_id",
        "mpesa_receipt_number",
        "account_reference",
    ]
    ordering = ["-initiated_at"]
    date_hierarchy = "initiated_at"
    readonly_fields = [
        "id",
        "transaction_type",
        "status",
        "checkout_request_id",
        "merchant_request_id",
        "conversation_id",
        "originator_conversation_id",
        "mpesa_receipt_number",
        "phone_number",
        "amount",
        "account_reference",
        "transaction_desc",
        "result_code",
        "result_desc",
        "raw_callback_payload",
        "initiated_at",
        "settled_at",
        "idempotency_locked",
    ]

    def status_badge(self, obj):
        color = STATUS_BADGE_COLORS.get(obj.status, "#6b7280")
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;'
            'border-radius:4px;font-size:11px;font-weight:600">{}</span>',
            color,
            obj.status,
        )

    status_badge.short_description = "Status"
    status_badge.admin_order_field = "status"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class MpesaCallbackLogAdminMixin:
    """
    Mixin for MpesaCallbackLog admin views.

    All fields are read-only — the log is a forensic audit trail.
    """

    list_display = [
        "id",
        "callback_type",
        "source_ip",
        "processed",
        "received_at",
        "related_transaction_id",
    ]
    list_filter = ["callback_type", "processed", "received_at"]
    ordering = ["-received_at"]
    readonly_fields = [
        "id",
        "callback_type",
        "source_ip",
        "raw_body",
        "related_transaction_id",
        "processed",
        "error",
        "received_at",
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

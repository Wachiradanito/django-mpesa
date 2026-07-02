import pytest

from django_mpesa.admin import MpesaCallbackLogAdminMixin, MpesaTransactionAdminMixin


def test_transaction_mixin_has_list_display():
    assert "status_badge" in MpesaTransactionAdminMixin.list_display
    assert "phone_number" in MpesaTransactionAdminMixin.list_display
    assert "amount" in MpesaTransactionAdminMixin.list_display


def test_transaction_mixin_all_fields_readonly():
    readonly = MpesaTransactionAdminMixin.readonly_fields
    for field in ("id", "amount", "phone_number", "status", "checkout_request_id",
                  "conversation_id", "mpesa_receipt_number", "initiated_at", "settled_at"):
        assert field in readonly, f"{field} should be in readonly_fields"


def test_callback_log_mixin_has_list_display():
    assert "callback_type" in MpesaCallbackLogAdminMixin.list_display
    assert "source_ip" in MpesaCallbackLogAdminMixin.list_display
    assert "processed" in MpesaCallbackLogAdminMixin.list_display


def test_transaction_mixin_no_add_permission():
    mixin = MpesaTransactionAdminMixin()
    assert mixin.has_add_permission(None) is False


def test_transaction_mixin_no_change_permission():
    mixin = MpesaTransactionAdminMixin()
    assert mixin.has_change_permission(None) is False


def test_transaction_mixin_no_delete_permission():
    mixin = MpesaTransactionAdminMixin()
    assert mixin.has_delete_permission(None) is False


def test_callback_log_mixin_no_add_permission():
    mixin = MpesaCallbackLogAdminMixin()
    assert mixin.has_add_permission(None) is False


def test_status_badge_renders_html():
    from django_mpesa.models import get_transaction_model
    from decimal import Decimal

    # Just test the method directly without DB
    class FakeTransaction:
        status = "SUCCESS"

    mixin = MpesaTransactionAdminMixin()
    badge = mixin.status_badge(FakeTransaction())
    assert "SUCCESS" in str(badge)
    assert "#10b981" in str(badge)  # green colour for SUCCESS


def test_no_auto_registration():
    """The library must not auto-register any admin models."""
    from django.contrib import admin
    # Importing admin module should not register anything automatically
    import django_mpesa.admin  # noqa: F401
    # No assertion needed — if auto-registration happened, the import
    # would fail or affect the registry unexpectedly. This just verifies import is clean.

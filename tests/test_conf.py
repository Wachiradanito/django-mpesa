import pytest
from django.test import override_settings

from django_mpesa.conf import get_base_url, mpesa_settings
from django_mpesa.exceptions import DarajaConfigError


@pytest.fixture(autouse=True)
def reload_settings():
    """Ensure mpesa_settings cache is clean before and after each test."""
    mpesa_settings.reload()
    yield
    mpesa_settings.reload()


def test_default_env_is_sandbox():
    assert mpesa_settings.ENV == "sandbox"


def test_reads_consumer_key_from_settings():
    assert mpesa_settings.CONSUMER_KEY == "test_consumer_key"


def test_callable_setting_is_resolved():
    with override_settings(MPESA={
        **__import__("django.conf", fromlist=["settings"]).settings.MPESA,
        "CONSUMER_KEY": lambda: "resolved_from_callable",
    }):
        mpesa_settings.reload()
        assert mpesa_settings.CONSUMER_KEY == "resolved_from_callable"


def test_missing_required_key_raises_config_error():
    mpesa = {k: v for k, v in __import__("django.conf", fromlist=["settings"]).settings.MPESA.items()
             if k != "CONSUMER_KEY"}
    with override_settings(MPESA=mpesa):
        mpesa_settings.reload()
        with pytest.raises(DarajaConfigError, match="CONSUMER_KEY"):
            _ = mpesa_settings.CONSUMER_KEY


def test_invalid_attribute_raises_attribute_error():
    with pytest.raises(AttributeError):
        _ = mpesa_settings.NONEXISTENT_KEY_XYZ


def test_reload_clears_cache():
    # Access to populate cache
    _ = mpesa_settings.ENV
    with override_settings(MPESA={
        **__import__("django.conf", fromlist=["settings"]).settings.MPESA,
        "ENV": "production",
    }):
        mpesa_settings.reload()
        assert mpesa_settings.ENV == "production"


def test_get_base_url_sandbox():
    assert get_base_url() == "https://sandbox.safaricom.co.ke"


def test_get_base_url_production():
    with override_settings(MPESA={
        **__import__("django.conf", fromlist=["settings"]).settings.MPESA,
        "ENV": "production",
    }):
        mpesa_settings.reload()
        assert get_base_url() == "https://api.safaricom.co.ke"


def test_get_base_url_invalid_env_raises():
    with override_settings(MPESA={
        **__import__("django.conf", fromlist=["settings"]).settings.MPESA,
        "ENV": "staging",
    }):
        mpesa_settings.reload()
        with pytest.raises(DarajaConfigError):
            get_base_url()


def test_default_use_celery_is_false_in_test_settings():
    # Our test settings override USE_CELERY=False
    assert mpesa_settings.USE_CELERY is False


def test_default_verify_callback_source_ip_is_false_in_test_settings():
    assert mpesa_settings.VERIFY_CALLBACK_SOURCE_IP is False

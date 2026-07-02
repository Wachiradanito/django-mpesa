import pytest
from django.core.management import call_command
from django.test import override_settings
from io import StringIO


def _run_command(**kwargs):
    """Run mpesa_check_config and return (stdout, stderr, exit_code)."""
    stdout = StringIO()
    stderr = StringIO()
    exit_code = 0
    try:
        call_command("mpesa_check_config", stdout=stdout, stderr=stderr, **kwargs)
    except SystemExit as e:
        exit_code = e.code
    return stdout.getvalue(), stderr.getvalue(), exit_code


def test_all_checks_pass_with_valid_settings():
    stdout, stderr, code = _run_command()
    assert code == 0
    assert "All checks passed" in stdout
    assert "[FAIL]" not in stdout


def test_fails_on_missing_consumer_key():
    mpesa = {k: v for k, v in __import__("django.conf", fromlist=["settings"]).settings.MPESA.items()
             if k != "CONSUMER_KEY"}
    with override_settings(MPESA=mpesa):
        from django_mpesa.conf import mpesa_settings
        mpesa_settings.reload()
        stdout, stderr, code = _run_command()
        mpesa_settings.reload()

    assert code == 1
    assert "[FAIL]" in stdout


def test_fails_on_http_callback_url_in_production():
    mpesa = {
        **__import__("django.conf", fromlist=["settings"]).settings.MPESA,
        "ENV": "production",
        "STK_CALLBACK_URL": "http://example.com/mpesa/stk/callback/",
    }
    with override_settings(MPESA=mpesa):
        from django_mpesa.conf import mpesa_settings
        mpesa_settings.reload()
        stdout, stderr, code = _run_command()
        mpesa_settings.reload()

    assert code == 1
    assert "[FAIL]" in stdout
    assert "HTTPS" in stdout


def test_warns_on_localhost_callback_in_sandbox():
    mpesa = {
        **__import__("django.conf", fromlist=["settings"]).settings.MPESA,
        "STK_CALLBACK_URL": "http://localhost:8000/mpesa/stk/callback/",
    }
    with override_settings(MPESA=mpesa):
        from django_mpesa.conf import mpesa_settings
        mpesa_settings.reload()
        stdout, stderr, code = _run_command()
        mpesa_settings.reload()

    # Should pass (sandbox allows http) but warn about localhost
    assert "localhost" in stdout or "WARN" in stdout.upper()


def test_fail_fast_stops_at_first_failure():
    mpesa = {k: v for k, v in __import__("django.conf", fromlist=["settings"]).settings.MPESA.items()
             if k not in ("CONSUMER_KEY", "CONSUMER_SECRET")}
    with override_settings(MPESA=mpesa):
        from django_mpesa.conf import mpesa_settings
        mpesa_settings.reload()
        stdout, stderr, code = _run_command(fail_fast=True)
        mpesa_settings.reload()

    assert code == 1
    # With fail_fast, should stop after first failure
    fail_lines = [l for l in stdout.splitlines() if "[FAIL]" in l]
    assert len(fail_lines) == 1


def test_invalid_token_cache_ttl_buffer_fails():
    mpesa = {
        **__import__("django.conf", fromlist=["settings"]).settings.MPESA,
        "TOKEN_CACHE_TTL_BUFFER": 9999,
    }
    with override_settings(MPESA=mpesa):
        from django_mpesa.conf import mpesa_settings
        mpesa_settings.reload()
        stdout, stderr, code = _run_command()
        mpesa_settings.reload()

    assert code == 1
    assert "TOKEN_CACHE_TTL_BUFFER" in stdout

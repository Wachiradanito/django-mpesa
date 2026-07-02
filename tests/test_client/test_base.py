import logging

import pytest
import responses as rsps_lib

from django_mpesa.client.auth import TokenManager
from django_mpesa.client.base import BaseDarajaClient, _redact
from django_mpesa.exceptions import (
    DarajaAPIError,
    DarajaAuthError,
    DarajaRateLimitError,
    DarajaTimeoutError,
)

SANDBOX_BASE = "https://sandbox.safaricom.co.ke"
SANDBOX_OAUTH = SANDBOX_BASE + "/oauth/v1/generate?grant_type=client_credentials"
TEST_PATH = "/mpesa/stkpush/v1/processrequest"
TEST_URL = SANDBOX_BASE + TEST_PATH
FAKE_TOKEN = "test_bearer_token"

SUCCESS_RESPONSE = {
    "ResponseCode": "0",
    "CheckoutRequestID": "ws_CO_test_123",
    "MerchantRequestID": "test_merchant_456",
    "ResponseDescription": "Success",
}


class _FakeTokenManager(TokenManager):
    """TokenManager that returns a fake token without hitting OAuth."""

    def get_token(self):
        return FAKE_TOKEN

    def invalidate(self):
        pass


def _client():
    return BaseDarajaClient(token_manager=_FakeTokenManager())


@rsps_lib.activate
def test_successful_post_returns_dict():
    rsps_lib.add(rsps_lib.POST, TEST_URL, json=SUCCESS_RESPONSE, status=200)
    result = _client().post(TEST_PATH, {"Amount": 100})
    assert result["ResponseCode"] == "0"
    assert result["CheckoutRequestID"] == "ws_CO_test_123"


@rsps_lib.activate
def test_5xx_retries_and_then_raises(settings):
    settings.MPESA = {**settings.MPESA, "MAX_RETRIES": 2, "RETRY_BACKOFF_FACTOR": 0}
    from django_mpesa.conf import mpesa_settings
    mpesa_settings.reload()

    rsps_lib.add(rsps_lib.POST, TEST_URL, json={"error": "server error"}, status=500)
    rsps_lib.add(rsps_lib.POST, TEST_URL, json={"error": "server error"}, status=500)
    rsps_lib.add(rsps_lib.POST, TEST_URL, json={"error": "server error"}, status=500)

    with pytest.raises(DarajaAPIError) as exc_info:
        _client().post(TEST_PATH, {})

    # 3 calls total (1 initial + 2 retries)
    assert len(rsps_lib.calls) == 3
    assert exc_info.value.status_code == 500

    mpesa_settings.reload()


@rsps_lib.activate
def test_4xx_raises_immediately_no_retry():
    rsps_lib.add(rsps_lib.POST, TEST_URL, json={"errorCode": "400.002.02"}, status=400)

    with pytest.raises(DarajaAPIError) as exc_info:
        _client().post(TEST_PATH, {})

    assert len(rsps_lib.calls) == 1
    assert exc_info.value.status_code == 400


@rsps_lib.activate
def test_401_invalidates_and_retries_once():
    """First call returns 401, second returns 200 — should succeed."""
    rsps_lib.add(rsps_lib.POST, TEST_URL, json={"error": "unauthorized"}, status=401)
    rsps_lib.add(rsps_lib.POST, TEST_URL, json=SUCCESS_RESPONSE, status=200)

    invalidated = []

    class TrackingTokenManager(_FakeTokenManager):
        def invalidate(self):
            invalidated.append(True)

    client = BaseDarajaClient(token_manager=TrackingTokenManager())
    result = client.post(TEST_PATH, {})

    assert result["ResponseCode"] == "0"
    assert len(invalidated) == 1
    assert len(rsps_lib.calls) == 2


@rsps_lib.activate
def test_401_twice_raises_auth_error():
    rsps_lib.add(rsps_lib.POST, TEST_URL, json={"error": "unauthorized"}, status=401)
    rsps_lib.add(rsps_lib.POST, TEST_URL, json={"error": "unauthorized"}, status=401)

    with pytest.raises(DarajaAuthError):
        _client().post(TEST_PATH, {})


@rsps_lib.activate
def test_429_raises_rate_limit_error():
    rsps_lib.add(rsps_lib.POST, TEST_URL, json={"error": "too many requests"}, status=429)

    with pytest.raises(DarajaRateLimitError):
        _client().post(TEST_PATH, {})


@rsps_lib.activate
def test_timeout_raises_daraja_timeout_error():
    rsps_lib.add(rsps_lib.POST, TEST_URL, body=__import__("requests").Timeout())

    with pytest.raises(DarajaTimeoutError):
        _client().post(TEST_PATH, {})


@rsps_lib.activate
def test_2xx_with_error_code_raises_api_error():
    rsps_lib.add(
        rsps_lib.POST,
        TEST_URL,
        json={"errorCode": "400.002.02", "errorMessage": "Bad request"},
        status=200,
    )

    with pytest.raises(DarajaAPIError) as exc_info:
        _client().post(TEST_PATH, {})

    assert "400.002.02" in str(exc_info.value.result_code)


def test_sensitive_fields_redacted():
    payload = {
        "Password": "supersecret",
        "SecurityCredential": "encrypted_cred",
        "Amount": 100,
        "PhoneNumber": "254712345678",
    }
    redacted = _redact(payload)
    assert redacted["Password"] == "***"
    assert redacted["SecurityCredential"] == "***"
    assert redacted["Amount"] == 100
    assert redacted["PhoneNumber"] == "254712345678"


@rsps_lib.activate
def test_sensitive_fields_not_in_logs(caplog):
    rsps_lib.add(rsps_lib.POST, TEST_URL, json=SUCCESS_RESPONSE, status=200)

    with caplog.at_level(logging.DEBUG, logger="django_mpesa"):
        _client().post(TEST_PATH, {"Password": "topsecret", "Amount": 100})

    log_text = caplog.text
    assert "topsecret" not in log_text
    assert "***" in log_text

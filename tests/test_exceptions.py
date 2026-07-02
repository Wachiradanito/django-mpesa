import pytest

from django_mpesa.exceptions import (
    DarajaAPIError,
    DarajaAuthError,
    DarajaConfigError,
    DarajaRateLimitError,
    DarajaTimeoutError,
    DarajaValidationError,
    InvalidCallbackError,
    MpesaError,
)


def test_all_exceptions_inherit_mpesa_error():
    assert isinstance(DarajaConfigError(), MpesaError)
    assert isinstance(DarajaAuthError(), MpesaError)
    assert isinstance(DarajaValidationError(), MpesaError)
    assert isinstance(DarajaAPIError(), MpesaError)
    assert isinstance(DarajaRateLimitError(), MpesaError)
    assert isinstance(DarajaTimeoutError(), MpesaError)
    assert isinstance(InvalidCallbackError(), MpesaError)


def test_rate_limit_and_timeout_inherit_api_error():
    assert isinstance(DarajaRateLimitError(), DarajaAPIError)
    assert isinstance(DarajaTimeoutError(), DarajaAPIError)


def test_result_code_accessible():
    e = DarajaConfigError("bad config", result_code=400)
    assert e.result_code == 400


def test_result_desc_accessible():
    e = DarajaAuthError("auth failed", result_desc="Invalid credentials")
    assert e.result_desc == "Invalid credentials"


def test_result_code_none_by_default():
    e = MpesaError("something went wrong")
    assert e.result_code is None
    assert e.result_desc is None


def test_daraja_api_error_has_status_code():
    e = DarajaAPIError("server error", status_code=500)
    assert e.status_code == 500


def test_daraja_api_error_has_response_body():
    e = DarajaAPIError("error", response_body='{"errorCode": "500.001"}')
    assert "500.001" in e.response_body


def test_repr_contains_class_name():
    e = DarajaAuthError("failed")
    assert "DarajaAuthError" in repr(e)


def test_repr_contains_message():
    e = DarajaConfigError("missing key")
    assert "missing key" in repr(e)


def test_exception_message_accessible_via_str():
    e = DarajaValidationError("phone number invalid")
    assert str(e) == "phone number invalid"

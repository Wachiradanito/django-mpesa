import pytest

from django_mpesa.exceptions import DarajaAPIError
from django_mpesa.testing import MockDarajaClient


def test_returns_default_stk_response():
    mock = MockDarajaClient()
    result = mock.post("/mpesa/stkpush/v1/processrequest", {})
    assert result["ResponseCode"] == "0"
    assert result["CheckoutRequestID"] == "ws_CO_test_123"


def test_returns_default_b2c_response():
    mock = MockDarajaClient()
    result = mock.post("/mpesa/b2c/v1/paymentrequest", {})
    assert result["ConversationID"] == "test_conv_123"


def test_custom_response_overrides_default():
    mock = MockDarajaClient(responses={
        "/mpesa/stkpush/v1/processrequest": {
            "ResponseCode": "0",
            "CheckoutRequestID": "ws_CO_custom",
            "MerchantRequestID": "custom_merchant",
            "ResponseDescription": "Custom",
        }
    })
    result = mock.post("/mpesa/stkpush/v1/processrequest", {})
    assert result["CheckoutRequestID"] == "ws_CO_custom"


def test_set_response_overrides_mid_test():
    mock = MockDarajaClient()
    mock.set_response("/mpesa/stkpush/v1/processrequest", {
        "ResponseCode": "0",
        "CheckoutRequestID": "ws_CO_override",
        "MerchantRequestID": "override_merchant",
        "ResponseDescription": "Override",
    })
    result = mock.post("/mpesa/stkpush/v1/processrequest", {})
    assert result["CheckoutRequestID"] == "ws_CO_override"


def test_raise_on_path_raises_exception():
    mock = MockDarajaClient()
    mock.set_raise("/mpesa/stkpush/v1/processrequest", DarajaAPIError("Daraja down"))
    with pytest.raises(DarajaAPIError, match="Daraja down"):
        mock.post("/mpesa/stkpush/v1/processrequest", {})


def test_raise_on_constructor():
    mock = MockDarajaClient(raise_on={
        "/mpesa/b2c/v1/paymentrequest": DarajaAPIError("B2C failed"),
    })
    with pytest.raises(DarajaAPIError):
        mock.post("/mpesa/b2c/v1/paymentrequest", {})


def test_calls_recorded():
    mock = MockDarajaClient()
    mock.post("/mpesa/stkpush/v1/processrequest", {"Amount": 100})
    mock.post("/mpesa/stkpushquery/v1/query", {"CheckoutRequestID": "123"})
    assert len(mock.calls) == 2
    assert mock.calls[0]["path"] == "/mpesa/stkpush/v1/processrequest"
    assert mock.calls[0]["payload"] == {"Amount": 100}


def test_reset_clears_calls_and_custom_responses():
    mock = MockDarajaClient()
    mock.set_response("/mpesa/stkpush/v1/processrequest", {"ResponseCode": "1"})
    mock.post("/mpesa/stkpush/v1/processrequest", {})
    assert len(mock.calls) == 1

    mock.reset()

    assert mock.calls == []
    # After reset, default response should be restored
    result = mock.post("/mpesa/stkpush/v1/processrequest", {})
    assert result["ResponseCode"] == "0"


def test_unknown_path_raises_api_error():
    mock = MockDarajaClient()
    with pytest.raises(DarajaAPIError, match="no response configured"):
        mock.post("/mpesa/unknown/v1/endpoint", {})


def test_assert_called_once_passes_when_called_once():
    mock = MockDarajaClient()
    mock.post("/mpesa/stkpush/v1/processrequest", {})
    mock.assert_called_once_with_path("/mpesa/stkpush/v1/processrequest")


def test_assert_called_once_fails_when_called_twice():
    mock = MockDarajaClient()
    mock.post("/mpesa/stkpush/v1/processrequest", {})
    mock.post("/mpesa/stkpush/v1/processrequest", {})
    with pytest.raises(AssertionError, match="Expected exactly one call"):
        mock.assert_called_once_with_path("/mpesa/stkpush/v1/processrequest")


def test_assert_not_called_passes_when_no_calls():
    mock = MockDarajaClient()
    mock.assert_not_called()


def test_assert_not_called_fails_when_called():
    mock = MockDarajaClient()
    mock.post("/mpesa/stkpush/v1/processrequest", {})
    with pytest.raises(AssertionError):
        mock.assert_not_called()


def test_assert_called_with_payload_passes():
    mock = MockDarajaClient()
    mock.post("/mpesa/stkpush/v1/processrequest", {"Amount": 100, "PhoneNumber": "254712345678"})
    mock.assert_called_with_payload(
        "/mpesa/stkpush/v1/processrequest",
        Amount=100,
    )


def test_assert_called_with_payload_fails_on_wrong_value():
    mock = MockDarajaClient()
    mock.post("/mpesa/stkpush/v1/processrequest", {"Amount": 100})
    with pytest.raises(AssertionError):
        mock.assert_called_with_payload(
            "/mpesa/stkpush/v1/processrequest",
            Amount=999,
        )

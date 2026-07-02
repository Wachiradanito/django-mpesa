"""
MockDarajaClient — a drop-in replacement for BaseDarajaClient for testing.

Returns configurable canned responses without any network calls.
Records all calls for assertion in tests.

Usage:

    from django_mpesa.testing import MockDarajaClient
    from django_mpesa.services import STKPushService

    def test_stk_push(db):
        mock = MockDarajaClient()
        service = STKPushService(client=mock)
        txn = service.initiate("254712345678", 100, "INV-001", "Payment")

        assert txn.status == "PENDING"
        assert txn.checkout_request_id == "ws_CO_test_123"
        mock.assert_called_once_with_path("/mpesa/stkpush/v1/processrequest")

    def test_stk_push_failure(db):
        from django_mpesa.exceptions import DarajaAPIError
        mock = MockDarajaClient()
        mock.set_raise("/mpesa/stkpush/v1/processrequest", DarajaAPIError("Daraja down"))
        service = STKPushService(client=mock)
        with pytest.raises(DarajaAPIError):
            service.initiate("254712345678", 100, "INV-001", "Payment")
"""

from django_mpesa.exceptions import DarajaAPIError

# Default canned responses for every known Daraja path.
# These match the real Safaricom response schema so tests
# exercise the same parsing code that runs in production.
_DEFAULT_RESPONSES: dict[str, dict] = {
    "/mpesa/stkpush/v1/processrequest": {
        "ResponseCode": "0",
        "CheckoutRequestID": "ws_CO_test_123",
        "MerchantRequestID": "test_merchant_456",
        "ResponseDescription": "Success. Request accepted for processing",
        "CustomerMessage": "Success. Request accepted for processing",
    },
    "/mpesa/stkpushquery/v1/query": {
        "ResponseCode": "0",
        "ResultCode": "0",
        "ResultDesc": "The service request is processed successfully.",
    },
    "/mpesa/c2b/v1/registerurl": {
        "ResponseCode": "0",
        "ResponseDescription": "Success",
    },
    "/mpesa/c2b/v1/simulate": {
        "ResponseCode": "0",
        "ResponseDescription": "Accept the service request successfully.",
        "OriginatorConversationID": "test_sim_123",
    },
    "/mpesa/b2c/v1/paymentrequest": {
        "ResponseCode": "0",
        "ConversationID": "test_conv_123",
        "OriginatorConversationID": "test_orig_123",
        "ResponseDescription": "Accept the service request successfully.",
    },
    "/mpesa/transactionstatus/v1/query": {
        "ResponseCode": "0",
        "ResponseDescription": "Accept the service request successfully.",
    },
    "/mpesa/accountbalance/v1/query": {
        "ResponseCode": "0",
        "ResponseDescription": "Accept the service request successfully.",
    },
    "/mpesa/reversal/v1/request": {
        "ResponseCode": "0",
        "ResponseDescription": "Accept the service request successfully.",
    },
}


class MockDarajaClient:
    """
    Drop-in replacement for BaseDarajaClient in tests.

    Constructor args:
        responses: dict mapping path → response dict to return.
                   Overrides the defaults for those paths only.
        raise_on:  dict mapping path → exception to raise.
                   Overrides any response configured for that path.

    Example — override a single path and check it was called:

        mock = MockDarajaClient(responses={
            "/mpesa/stkpush/v1/processrequest": {
                "ResponseCode": "0",
                "CheckoutRequestID": "ws_CO_custom",
                "MerchantRequestID": "custom_merchant",
                "ResponseDescription": "Success",
            }
        })
        service = STKPushService(client=mock)
        txn = service.initiate(...)
        assert txn.checkout_request_id == "ws_CO_custom"

    Example — simulate an error:

        mock = MockDarajaClient()
        mock.set_raise("/mpesa/b2c/v1/paymentrequest", DarajaAPIError("down"))
    """

    def __init__(
        self,
        responses: dict[str, dict] | None = None,
        raise_on: dict[str, Exception] | None = None,
    ):
        self._responses: dict[str, dict] = {**_DEFAULT_RESPONSES, **(responses or {})}
        self._raise_on: dict[str, Exception] = dict(raise_on or {})
        self._calls: list[dict] = []

    def post(self, path: str, payload: dict) -> dict:
        """
        Return the configured response for path, or raise the configured exception.

        Raises DarajaAPIError if path is not in defaults or custom responses.
        Records all calls for assertion.
        """
        self._calls.append({"path": path, "payload": payload})

        if path in self._raise_on:
            raise self._raise_on[path]

        if path in self._responses:
            return self._responses[path]

        raise DarajaAPIError(
            f"MockDarajaClient: no response configured for {path!r}. "
            f"Add it via MockDarajaClient(responses={{...}}) or mock.set_response(...)."
        )

    def set_response(self, path: str, response: dict) -> None:
        """Override the response for a specific path."""
        self._responses[path] = response

    def set_raise(self, path: str, exception: Exception) -> None:
        """Configure an exception to be raised for a specific path."""
        self._raise_on[path] = exception

    def reset(self) -> None:
        """Clear all custom responses, exceptions, and call records."""
        self._responses = {**_DEFAULT_RESPONSES}
        self._raise_on = {}
        self._calls = []

    @property
    def calls(self) -> list[dict]:
        """List of all recorded calls: [{"path": ..., "payload": ...}, ...]"""
        return list(self._calls)

    def assert_called_once_with_path(self, path: str) -> None:
        """Assert that exactly one call was made to the given path."""
        matching = [c for c in self._calls if c["path"] == path]
        assert len(matching) == 1, (
            f"Expected exactly one call to {path!r}, "
            f"but got {len(matching)}. All calls: {[c['path'] for c in self._calls]}"
        )

    def assert_not_called(self) -> None:
        """Assert that no calls were made to this client."""
        assert self._calls == [], (
            f"Expected no calls but got {len(self._calls)}: "
            f"{[c['path'] for c in self._calls]}"
        )

    def assert_called_with_payload(self, path: str, **expected_fields) -> None:
        """
        Assert that a call to path included the given payload fields.

        Only checks the specified fields — extra fields in the actual payload
        are ignored.
        """
        matching = [c for c in self._calls if c["path"] == path]
        assert matching, f"No call found for path {path!r}"
        payload = matching[-1]["payload"]
        for key, value in expected_fields.items():
            assert payload.get(key) == value, (
                f"Expected payload[{key!r}] == {value!r}, "
                f"got {payload.get(key)!r}"
            )

"""
Exception hierarchy for django-mpesa.

All exceptions inherit from MpesaError so callers can catch the base
class to handle any library error, or catch a specific subclass to
handle a particular failure mode.

Every exception carries result_code and result_desc where applicable,
so callers can branch on Safaricom's own error taxonomy rather than
string-matching messages.
"""


class MpesaError(Exception):
    """Base class for all django-mpesa exceptions."""

    def __init__(self, message: str = "", result_code: int | None = None, result_desc: str | None = None):
        super().__init__(message)
        self.message = message
        self.result_code = result_code
        self.result_desc = result_desc

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"message={self.message!r}, "
            f"result_code={self.result_code!r})"
        )


class DarajaConfigError(MpesaError):
    """
    Raised when the library is misconfigured.

    Examples:
    - Required MPESA setting is missing
    - ENV is not 'sandbox' or 'production'
    - C2BService.simulate() called in production
    - TRANSACTION_MODEL does not resolve
    - USE_CELERY=True but Celery is not installed
    """


class DarajaAuthError(MpesaError):
    """
    Raised when OAuth token acquisition fails.

    Examples:
    - Daraja /oauth endpoint returns non-200
    - Credentials are invalid
    - Token fetch lock times out
    - 401 persists after token invalidation and retry
    """


class DarajaValidationError(MpesaError):
    """
    Raised when input validation fails before any network call.

    Examples:
    - Phone number in wrong format
    - Amount is zero or negative
    - account_reference exceeds 12 characters
    - transaction_desc exceeds 13 characters
    - Invalid B2C command_id
    """


class DarajaAPIError(MpesaError):
    """
    Raised when Safaricom returns an error response.

    Covers:
    - Non-2xx HTTP responses (except 401 and 429, which have their own subclasses)
    - 2xx responses that contain an errorCode field
    - Non-zero ResponseCode in the response body
    """

    def __init__(
        self,
        message: str = "",
        result_code: int | None = None,
        result_desc: str | None = None,
        status_code: int | None = None,
        response_body: str | None = None,
    ):
        super().__init__(message, result_code, result_desc)
        self.status_code = status_code        # HTTP status code from Daraja
        self.response_body = response_body    # Raw response body for debugging

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"message={self.message!r}, "
            f"result_code={self.result_code!r}, "
            f"status_code={self.status_code!r})"
        )


class DarajaRateLimitError(DarajaAPIError):
    """Raised when Daraja returns HTTP 429 Too Many Requests."""


class DarajaTimeoutError(DarajaAPIError):
    """Raised when an outbound request to Daraja times out."""


class InvalidCallbackError(MpesaError):
    """
    Raised when an inbound callback is invalid.

    Examples:
    - Source IP not in Safaricom allowlist
    - Callback body is missing required fields
    - JSON parse failure on callback body
    """

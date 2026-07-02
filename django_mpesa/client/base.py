"""
Base HTTP client for all Daraja API calls.

BaseDarajaClient wraps all outbound communication:
- Attaches the OAuth bearer token to every request
- Handles 401 token refresh with a single retry
- Retries on 5xx (server errors) with exponential backoff
- Raises typed exceptions for 4xx, 429, and timeouts
- Redacts sensitive fields from DEBUG logs

Services compose this class rather than inherit from it so they are
independently testable and the client can be swapped in tests.
"""

import logging
import time

import requests

from django_mpesa.client.auth import TokenManager
from django_mpesa.client.http import get_session
from django_mpesa.conf import get_base_url, mpesa_settings
from django_mpesa.exceptions import (
    DarajaAPIError,
    DarajaAuthError,
    DarajaRateLimitError,
    DarajaTimeoutError,
)

logger = logging.getLogger("django_mpesa")

# Fields whose values are redacted in log output
SENSITIVE_KEYS = frozenset({
    "Password",
    "SecurityCredential",
    "Passkey",
    "InitiatorPassword",
})


def _redact(payload: dict) -> dict:
    """Return a copy of payload with sensitive values replaced by '***'."""
    return {k: "***" if k in SENSITIVE_KEYS else v for k, v in payload.items()}


class BaseDarajaClient:
    """
    Executes authenticated HTTP POST requests to the Daraja API.

    Constructor parameters are injectable for testing:
        client = BaseDarajaClient(
            token_manager=MockTokenManager(),
            session=mock_session,
        )
    """

    def __init__(
        self,
        token_manager: TokenManager | None = None,
        session: requests.Session | None = None,
    ):
        self.token_manager = token_manager or TokenManager()
        self.session = session or get_session()

    def post(self, path: str, payload: dict) -> dict:
        """
        Execute an authenticated POST to a Daraja API path.

        Args:
            path: Daraja endpoint path, e.g. '/mpesa/stkpush/v1/processrequest'
            payload: Request body dict (will be JSON-serialised)

        Returns:
            Parsed response dict

        Raises:
            DarajaAuthError: On 401 that persists after token refresh
            DarajaRateLimitError: On HTTP 429
            DarajaTimeoutError: On request timeout
            DarajaAPIError: On 4xx (not 401/429), 5xx after retries, or
                            2xx with an errorCode field
        """
        return self._post_with_auth(path, payload, _retry_on_401=True)

    def _post_with_auth(self, path: str, payload: dict, _retry_on_401: bool) -> dict:
        token = self.token_manager.get_token()
        url = get_base_url() + path
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        logger.debug(
            "django_mpesa POST %s payload=%s", url, _redact(payload)
        )

        response = self._execute_with_retries(url, headers, payload)

        logger.debug(
            "django_mpesa response %s: %s", response.status_code, response.text[:500]
        )

        # 401 — token expired or invalid; refresh once then retry
        if response.status_code == 401:
            if _retry_on_401:
                self.token_manager.invalidate()
                return self._post_with_auth(path, payload, _retry_on_401=False)
            raise DarajaAuthError(
                "Daraja returned 401 after token refresh. "
                "Check your CONSUMER_KEY and CONSUMER_SECRET."
            )

        # 429 — rate limited
        if response.status_code == 429:
            raise DarajaRateLimitError(
                "Daraja rate limit exceeded (HTTP 429). Slow down requests.",
                status_code=429,
                response_body=response.text,
            )

        # 4xx (not 401/429) — bad request; never retry
        if 400 <= response.status_code < 500:
            self._raise_api_error(response)

        # 5xx — already retried in _execute_with_retries; raise now
        if response.status_code >= 500:
            self._raise_api_error(response)

        # 2xx — parse and check for Daraja's embedded error format
        try:
            data = response.json()
        except Exception as exc:
            raise DarajaAPIError(
                f"Could not parse Daraja response as JSON: {response.text[:200]}",
                status_code=response.status_code,
                response_body=response.text,
            ) from exc

        if "errorCode" in data:
            raise DarajaAPIError(
                f"Daraja error: {data.get('errorMessage', data['errorCode'])}",
                result_code=data.get("errorCode"),
                result_desc=data.get("errorMessage"),
                status_code=response.status_code,
                response_body=response.text,
            )

        return data

    def _execute_with_retries(
        self, url: str, headers: dict, payload: dict
    ) -> requests.Response:
        """
        Execute the HTTP request with application-level retry on 5xx.

        Transport-level retries (TCP/TLS failures) are handled by the
        urllib3.Retry adapter in http.py. This layer retries on Daraja
        server errors (5xx) with exponential backoff.
        """
        max_retries = mpesa_settings.MAX_RETRIES
        backoff_factor = mpesa_settings.RETRY_BACKOFF_FACTOR
        timeout = mpesa_settings.REQUEST_TIMEOUT

        last_response = None

        for attempt in range(max_retries + 1):
            try:
                response = self.session.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=timeout,
                )
            except requests.Timeout as exc:
                raise DarajaTimeoutError(
                    f"Request to Daraja timed out after {timeout}s",
                    status_code=None,
                ) from exc
            except requests.RequestException as exc:
                raise DarajaAPIError(
                    f"Request to Daraja failed: {exc}",
                    status_code=None,
                ) from exc

            # Success or client error — return immediately, no retry
            if response.status_code < 500:
                return response

            last_response = response

            if attempt < max_retries:
                wait = backoff_factor * (2 ** attempt)
                logger.warning(
                    "django_mpesa: Daraja returned %s, retrying in %.1fs "
                    "(attempt %s/%s)",
                    response.status_code, wait, attempt + 1, max_retries,
                )
                time.sleep(wait)

        return last_response

    def _raise_api_error(self, response: requests.Response) -> None:
        """Parse a Daraja error response and raise DarajaAPIError."""
        try:
            data = response.json()
            message = data.get("errorMessage") or data.get("ResponseDescription") or response.text[:200]
            result_code = data.get("errorCode") or data.get("ResponseCode")
            result_desc = data.get("errorMessage") or data.get("ResponseDescription")
        except Exception:
            message = response.text[:200]
            result_code = None
            result_desc = None

        raise DarajaAPIError(
            message=message or f"HTTP {response.status_code}",
            result_code=result_code,
            result_desc=result_desc,
            status_code=response.status_code,
            response_body=response.text,
        )

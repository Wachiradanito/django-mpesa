"""
OAuth token management for Daraja API.

TokenManager handles the full token lifecycle:
- Fetching a bearer token from Daraja's OAuth endpoint
- Caching it in Django's cache backend for reuse across requests
- Thread-safe stampede prevention via cache.add() as a distributed lock
- Invalidation on 401 responses
"""

import base64
import logging
import time

import requests
from django.core.cache import caches

from django_mpesa.conf import get_base_url, mpesa_settings
from django_mpesa.exceptions import DarajaAuthError

logger = logging.getLogger("django_mpesa")

OAUTH_PATH = "/oauth/v1/generate?grant_type=client_credentials"
LOCK_TIMEOUT_SECONDS = 10
LOCK_WAIT_RETRIES = 5
LOCK_WAIT_SLEEP = 0.1


class TokenManager:
    """
    Manages the Daraja OAuth 2.0 bearer token lifecycle.

    Thread-safe: concurrent cold-start token requests are serialised via
    a cache.add() lock so only one HTTP call is made regardless of how
    many concurrent requests arrive on a cold cache.
    """

    def get_token(self) -> str:
        """
        Return a valid bearer token.

        Checks the cache first. On a miss, acquires a lock, fetches a
        fresh token, caches it, and returns it. Other concurrent callers
        wait for the lock then get a cache hit.
        """
        cache = caches[mpesa_settings.TOKEN_CACHE_ALIAS]
        cache_key = self._cache_key()
        lock_key = self._lock_key()

        # Fast path — cache hit
        token = cache.get(cache_key)
        if token:
            return token

        # Slow path — acquire lock and fetch
        for attempt in range(LOCK_WAIT_RETRIES):
            acquired = cache.add(lock_key, "1", timeout=LOCK_TIMEOUT_SECONDS)
            if acquired:
                try:
                    # Double-check after acquiring lock in case another process
                    # fetched and cached while we were waiting
                    token = cache.get(cache_key)
                    if token:
                        return token

                    token, expires_in = self._fetch_new_token()
                    ttl = max(expires_in - mpesa_settings.TOKEN_CACHE_TTL_BUFFER, 1)
                    cache.set(cache_key, token, timeout=ttl)
                    return token
                finally:
                    cache.delete(lock_key)
            else:
                # Another process holds the lock — wait and retry
                time.sleep(LOCK_WAIT_SLEEP)
                token = cache.get(cache_key)
                if token:
                    return token

        raise DarajaAuthError(
            "Token fetch lock timeout: could not acquire the token cache lock "
            f"after {LOCK_WAIT_RETRIES} attempts."
        )

    def _fetch_new_token(self) -> tuple[str, int]:
        """
        Fetch a fresh bearer token from Daraja's OAuth endpoint.

        Returns:
            (access_token, expires_in) tuple

        Raises:
            DarajaAuthError: on non-200 response or network failure
        """
        consumer_key = mpesa_settings.CONSUMER_KEY
        consumer_secret = mpesa_settings.CONSUMER_SECRET

        credentials = base64.b64encode(
            f"{consumer_key}:{consumer_secret}".encode()
        ).decode()

        url = get_base_url() + OAUTH_PATH

        try:
            response = requests.get(
                url,
                headers={
                    "Authorization": f"Basic {credentials}",
                    "Accept": "application/json",
                },
                timeout=mpesa_settings.REQUEST_TIMEOUT,
            )
        except requests.Timeout as exc:
            raise DarajaAuthError(
                f"Token fetch timed out after {mpesa_settings.REQUEST_TIMEOUT}s"
            ) from exc
        except requests.RequestException as exc:
            raise DarajaAuthError(f"Token fetch failed: {exc}") from exc

        if response.status_code != 200:
            raise DarajaAuthError(
                f"Daraja OAuth returned HTTP {response.status_code}. "
                f"Check your CONSUMER_KEY and CONSUMER_SECRET."
            )

        data = response.json()
        access_token = data.get("access_token")
        expires_in = int(data.get("expires_in", 3599))

        if not access_token:
            raise DarajaAuthError(
                f"Daraja OAuth response missing access_token. Response: {data}"
            )

        logger.debug(
            "django_mpesa: fetched new OAuth token, expires_in=%s", expires_in
        )
        return access_token, expires_in

    def invalidate(self) -> None:
        """
        Remove the cached token.

        Called by BaseDarajaClient after receiving a 401, so the next
        request fetches a fresh token.
        """
        cache = caches[mpesa_settings.TOKEN_CACHE_ALIAS]
        cache.delete(self._cache_key())
        logger.debug("django_mpesa: OAuth token invalidated")

    def _cache_key(self) -> str:
        return f"django_mpesa:token:{mpesa_settings.ENV}"

    def _lock_key(self) -> str:
        return f"django_mpesa:token_lock:{mpesa_settings.ENV}"

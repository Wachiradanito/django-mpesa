import threading

import pytest
import responses as rsps_lib
from django.core.cache import cache

from django_mpesa.client.auth import TokenManager
from django_mpesa.exceptions import DarajaAuthError


SANDBOX_OAUTH_URL = (
    "https://sandbox.safaricom.co.ke/oauth/v1/generate"
    "?grant_type=client_credentials"
)
FAKE_TOKEN = "fake_bearer_token_abc123"
FAKE_EXPIRES = 3599


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear the token cache before and after every test."""
    cache.clear()
    yield
    cache.clear()


@rsps_lib.activate
def test_get_token_fetches_and_caches():
    rsps_lib.add(
        rsps_lib.GET,
        SANDBOX_OAUTH_URL,
        json={"access_token": FAKE_TOKEN, "expires_in": str(FAKE_EXPIRES)},
        status=200,
    )
    manager = TokenManager()
    token = manager.get_token()
    assert token == FAKE_TOKEN
    # Should be in cache now
    assert cache.get("django_mpesa:token:sandbox") == FAKE_TOKEN


@rsps_lib.activate
def test_get_token_returns_cached_on_second_call():
    rsps_lib.add(
        rsps_lib.GET,
        SANDBOX_OAUTH_URL,
        json={"access_token": FAKE_TOKEN, "expires_in": str(FAKE_EXPIRES)},
        status=200,
    )
    manager = TokenManager()
    manager.get_token()
    manager.get_token()
    # Only one HTTP call should have been made
    assert len(rsps_lib.calls) == 1


@rsps_lib.activate
def test_invalidate_clears_cache():
    rsps_lib.add(
        rsps_lib.GET,
        SANDBOX_OAUTH_URL,
        json={"access_token": FAKE_TOKEN, "expires_in": str(FAKE_EXPIRES)},
        status=200,
    )
    rsps_lib.add(
        rsps_lib.GET,
        SANDBOX_OAUTH_URL,
        json={"access_token": "new_token_xyz", "expires_in": str(FAKE_EXPIRES)},
        status=200,
    )
    manager = TokenManager()
    first = manager.get_token()
    manager.invalidate()
    second = manager.get_token()
    assert first == FAKE_TOKEN
    assert second == "new_token_xyz"
    assert len(rsps_lib.calls) == 2


@rsps_lib.activate
def test_fetch_raises_auth_error_on_non_200():
    rsps_lib.add(
        rsps_lib.GET,
        SANDBOX_OAUTH_URL,
        json={"error": "invalid_client"},
        status=401,
    )
    manager = TokenManager()
    with pytest.raises(DarajaAuthError):
        manager.get_token()


@rsps_lib.activate
def test_token_ttl_uses_buffer(settings):
    """Cached TTL should be expires_in - TOKEN_CACHE_TTL_BUFFER."""
    rsps_lib.add(
        rsps_lib.GET,
        SANDBOX_OAUTH_URL,
        json={"access_token": FAKE_TOKEN, "expires_in": "3599"},
        status=200,
    )
    # Use a custom buffer for this test
    settings.MPESA = {**settings.MPESA, "TOKEN_CACHE_TTL_BUFFER": 100}
    from django_mpesa.conf import mpesa_settings
    mpesa_settings.reload()

    manager = TokenManager()
    manager.get_token()
    # The token should still be in cache (TTL = 3599 - 100 = 3499s, well within test time)
    assert cache.get("django_mpesa:token:sandbox") == FAKE_TOKEN

    # Restore
    mpesa_settings.reload()


@rsps_lib.activate
def test_stampede_prevention():
    """Two concurrent threads should result in exactly one HTTP call."""
    rsps_lib.add(
        rsps_lib.GET,
        SANDBOX_OAUTH_URL,
        json={"access_token": FAKE_TOKEN, "expires_in": str(FAKE_EXPIRES)},
        status=200,
    )

    results = []
    errors = []
    barrier = threading.Barrier(2)

    def fetch():
        try:
            barrier.wait()
            token = TokenManager().get_token()
            results.append(token)
        except Exception as e:
            errors.append(e)

    t1 = threading.Thread(target=fetch)
    t2 = threading.Thread(target=fetch)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert errors == [], f"Threads raised: {errors}"
    assert len(results) == 2
    assert all(r == FAKE_TOKEN for r in results)
    # Exactly one HTTP call was made
    assert len(rsps_lib.calls) == 1

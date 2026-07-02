"""
HTTP session factory for django-mpesa.

Provides a pre-configured requests.Session with transport-level retries
for TCP/TLS failures only. Application-level retries (on Daraja 5xx
responses) are handled separately in BaseDarajaClient to avoid
compounding the two retry layers unpredictably.
"""

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from django_mpesa import __version__


def get_session() -> requests.Session:
    """
    Create and return a new configured requests.Session.

    Each call returns a new instance — there is no module-level singleton.
    This allows BaseDarajaClient to receive an injected session in tests.

    Transport-level retry config:
    - Retries on connection errors and read errors (TCP/TLS failures)
    - Does NOT retry on HTTP error status codes — those are BaseDarajaClient's job
    - backoff_factor=0.3 → waits 0s, 0.3s, 0.6s between retries
    """
    session = requests.Session()

    retry = Retry(
        total=2,
        connect=2,
        read=2,
        status=0,              # no HTTP-status-code retries at transport layer
        raise_on_status=False,
        backoff_factor=0.3,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    session.headers.update({
        "User-Agent": f"django-mpesa/{__version__}",
        "Accept": "application/json",
    })

    return session

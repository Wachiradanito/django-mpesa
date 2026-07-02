"""
IP allowlist middleware for django-mpesa callback endpoints.

Rejects inbound requests to M-PESA callback URLs from IPs not in
Safaricom's published allowlist. This is the primary authentication
mechanism for callbacks — Safaricom does not send auth tokens.

The middleware is a no-op for all non-callback paths so it has zero
overhead on normal application requests.
"""

import logging

from django.http import HttpResponse

from django_mpesa.conf import mpesa_settings

logger = logging.getLogger("django_mpesa")

# Callback path segment — used to identify callback requests
# The full prefix is resolved at first request to avoid import-time
# URL resolution issues.
_MPESA_PATH_CACHE: str | None = None


def _get_mpesa_prefix() -> str:
    """
    Resolve the URL prefix for django_mpesa callback endpoints.
    Cached after first call.
    """
    global _MPESA_PATH_CACHE
    if _MPESA_PATH_CACHE is not None:
        return _MPESA_PATH_CACHE

    try:
        from django.urls import reverse
        url = reverse("django_mpesa:stk-callback")
        # Extract everything before "stk/callback/"
        prefix = url.split("stk/")[0]
        _MPESA_PATH_CACHE = prefix
        return prefix
    except Exception:
        # Fallback if URL resolution fails (e.g. URLs not yet wired)
        _MPESA_PATH_CACHE = "/mpesa/"
        return _MPESA_PATH_CACHE


def _get_client_ip(request) -> str:
    """
    Resolve the real client IP from the request.

    When TRUST_FORWARDED_FOR is True, parses X-Forwarded-For and
    returns the leftmost IP not in FORWARDED_FOR_TRUSTED_PROXIES.
    Otherwise returns REMOTE_ADDR directly.
    """
    if not mpesa_settings.TRUST_FORWARDED_FOR:
        return request.META.get("REMOTE_ADDR", "")

    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if not forwarded_for:
        return request.META.get("REMOTE_ADDR", "")

    trusted_proxies = set(mpesa_settings.FORWARDED_FOR_TRUSTED_PROXIES)
    ips = [ip.strip() for ip in forwarded_for.split(",")]

    # Walk right-to-left; the first non-trusted IP is the real client
    for ip in reversed(ips):
        if ip not in trusted_proxies:
            return ip

    return request.META.get("REMOTE_ADDR", "")


class MpesaCallbackIPAllowlistMiddleware:
    """
    Middleware that enforces Safaricom's IP allowlist on callback endpoints.

    Applied only to paths under the django_mpesa URL prefix. For all
    other paths it is a zero-cost passthrough.

    Configuration:
        MPESA = {
            "VERIFY_CALLBACK_SOURCE_IP": True,   # default
            "CALLBACK_IP_ALLOWLIST": [...],       # Safaricom's IPs
            "TRUST_FORWARDED_FOR": False,         # set True behind a proxy
        }

    Set VERIFY_CALLBACK_SOURCE_IP=False for local development where
    Safaricom cannot reach your machine.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Fast path: not a callback path — skip entirely
        try:
            prefix = _get_mpesa_prefix()
        except Exception:
            return self.get_response(request)

        if not request.path.startswith(prefix):
            return self.get_response(request)

        # Fast path: IP verification disabled (local dev)
        if not mpesa_settings.VERIFY_CALLBACK_SOURCE_IP:
            return self.get_response(request)

        ip = _get_client_ip(request)
        allowlist = mpesa_settings.CALLBACK_IP_ALLOWLIST

        if ip not in allowlist:
            logger.warning(
                "django_mpesa: blocked callback from %s — not in IP allowlist", ip
            )
            return HttpResponse(status=403)

        return self.get_response(request)

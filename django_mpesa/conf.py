"""
Settings resolver for django-mpesa.

All library settings live under a single MPESA dict in the host app's
Django settings.py. This module exposes a mpesa_settings object that
provides attribute access with defaults and callable resolution.

Pattern is borrowed from DRF's api_settings object.
"""

from django.conf import settings as django_settings
from django.test.signals import setting_changed

from django_mpesa.exceptions import DarajaConfigError

# ------------------------------------------------------------------
# Safaricom's published callback IP ranges (as of 2024).
# Override CALLBACK_IP_ALLOWLIST in your MPESA settings if these change.
# ------------------------------------------------------------------
SAFARICOM_IP_ALLOWLIST = [
    "196.201.214.200",
    "196.201.214.206",
    "196.201.213.114",
    "196.201.214.207",
    "196.201.214.208",
    "196.201.213.44",
    "196.201.212.127",
    "196.201.212.128",
    "196.201.212.129",
    "196.201.212.132",
    "196.201.212.136",
]

# ------------------------------------------------------------------
# All settings that have a default value
# ------------------------------------------------------------------
DEFAULTS: dict = {
    "ENV": "sandbox",
    "INITIATOR_NAME": None,
    "INITIATOR_PASSWORD": None,
    "SECURITY_CREDENTIAL": None,
    "STK_CALLBACK_URL": None,
    "C2B_VALIDATION_URL": None,
    "C2B_CONFIRMATION_URL": None,
    "B2C_RESULT_URL": None,
    "B2C_TIMEOUT_URL": None,
    "TOKEN_CACHE_ALIAS": "default",
    "TOKEN_CACHE_TTL_BUFFER": 60,
    "REQUEST_TIMEOUT": 30,
    "MAX_RETRIES": 3,
    "RETRY_BACKOFF_FACTOR": 0.5,
    "VERIFY_CALLBACK_SOURCE_IP": True,
    "TRUST_FORWARDED_FOR": False,
    "FORWARDED_FOR_TRUSTED_PROXIES": [],
    "CALLBACK_IP_ALLOWLIST": SAFARICOM_IP_ALLOWLIST,
    "USE_CELERY": True,
    "CELERY_TASK_MAX_RETRIES": 5,
    "CELERY_TASK_RETRY_BACKOFF": True,
}

# Settings that must be present — no default
REQUIRED: set = {
    "CONSUMER_KEY",
    "CONSUMER_SECRET",
    "SHORTCODE",
    "TRANSACTION_MODEL",
    "CALLBACK_LOG_MODEL",
}

# Settings that support callable resolution (lambda / function)
CALLABLE_SETTINGS: set = {
    "CONSUMER_KEY",
    "CONSUMER_SECRET",
    "SHORTCODE",
    "PASSKEY",
    "INITIATOR_NAME",
    "INITIATOR_PASSWORD",
    "SECURITY_CREDENTIAL",
}

# All valid setting names
ALL_SETTINGS: set = REQUIRED | set(DEFAULTS.keys()) | {"PASSKEY"}

BASE_URLS = {
    "sandbox": "https://sandbox.safaricom.co.ke",
    "production": "https://api.safaricom.co.ke",
}


class MpesaSettings:
    """
    Settings resolver. Accessed via the module-level mpesa_settings instance.

    Usage:
        from django_mpesa.conf import mpesa_settings
        key = mpesa_settings.CONSUMER_KEY
    """

    def __init__(self, user_settings: dict | None = None, defaults: dict | None = None):
        self._user_settings = user_settings or {}
        self._defaults = defaults or DEFAULTS
        self._cache: dict = {}

    def __getattr__(self, attr: str):
        if attr.startswith("_"):
            raise AttributeError(attr)

        if attr not in ALL_SETTINGS:
            raise AttributeError(
                f"Invalid MPESA setting: {attr!r}. "
                f"Check the django-mpesa documentation for valid settings."
            )

        if attr in self._cache:
            return self._cache[attr]

        try:
            val = self._user_settings[attr]
        except KeyError:
            if attr in REQUIRED:
                raise DarajaConfigError(
                    f"MPESA[{attr!r}] is required but not configured. "
                    f"Add it to your MPESA settings dict."
                )
            val = self._defaults.get(attr)

        # Resolve callables (lambda / function returning the real value)
        if attr in CALLABLE_SETTINGS and callable(val):
            val = val()

        self._cache[attr] = val
        return val

    def reload(self) -> None:
        """
        Clear the internal cache and re-read from Django settings.
        Called automatically when MPESA settings change (e.g. in tests
        using @override_settings).
        """
        self._cache.clear()
        self._user_settings = getattr(django_settings, "MPESA", {})


def get_base_url() -> str:
    """
    Return the Daraja base URL for the configured environment.
    Re-reads ENV on every call so test overrides are reflected.
    """
    env = mpesa_settings.ENV
    if env not in BASE_URLS:
        raise DarajaConfigError(
            f"MPESA['ENV'] must be 'sandbox' or 'production', got {env!r}."
        )
    return BASE_URLS[env]


# Module-level singleton — import this everywhere
mpesa_settings = MpesaSettings(
    user_settings=getattr(django_settings, "MPESA", {}),
    defaults=DEFAULTS,
)


# Reload on @override_settings in tests
def _reload_on_setting_changed(*, setting: str, **kwargs) -> None:
    if setting == "MPESA":
        mpesa_settings.reload()


setting_changed.connect(_reload_on_setting_changed)

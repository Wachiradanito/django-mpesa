"""
Minimal Django settings for the django-mpesa test suite.
Not for use in production.
"""

SECRET_KEY = "django-mpesa-test-secret-key-not-for-production"

DEBUG = True

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        # Use a file-based DB (not :memory:) so concurrent threads in the
        # idempotency tests share the same database. In-memory SQLite
        # gives each connection its own isolated database.
        "NAME": "/tmp/django_mpesa_test.db",
        "OPTIONS": {
            "timeout": 5,  # wait up to 5s on lock instead of raising
        },
    }
}

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "rest_framework",
    "django_mpesa",
    "tests.testapp",
]

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "django-mpesa-test",
    }
}

USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

ROOT_URLCONF = "tests.urls"

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
}

# Minimal MPESA config for tests.
# Credentials are dummy values — no real Daraja calls are made in the test suite.
MPESA = {
    "ENV": "sandbox",
    "CONSUMER_KEY": "test_consumer_key",
    "CONSUMER_SECRET": "test_consumer_secret",
    "SHORTCODE": "174379",
    "PASSKEY": "bfb279f9aa9bdbcf158e97dd71a467cd2e0c893059b10f78e6b72ada1ed2c919",
    "INITIATOR_NAME": "testapi",
    "SECURITY_CREDENTIAL": "test_security_credential",
    "STK_CALLBACK_URL": "https://example.com/mpesa/stk/callback/",
    "C2B_VALIDATION_URL": "https://example.com/mpesa/c2b/validate/",
    "C2B_CONFIRMATION_URL": "https://example.com/mpesa/c2b/confirm/",
    "B2C_RESULT_URL": "https://example.com/mpesa/b2c/result/",
    "B2C_TIMEOUT_URL": "https://example.com/mpesa/b2c/timeout/",
    "TRANSACTION_MODEL": "testapp.MpesaTransaction",
    "CALLBACK_LOG_MODEL": "testapp.MpesaCallbackLog",
    "USE_CELERY": False,  # Synchronous processing in tests
    "VERIFY_CALLBACK_SOURCE_IP": False,  # Disabled so test client can POST freely
    "TOKEN_CACHE_TTL_BUFFER": 60,
    "REQUEST_TIMEOUT": 30,
    "MAX_RETRIES": 3,
    "RETRY_BACKOFF_FACTOR": 0.5,
}

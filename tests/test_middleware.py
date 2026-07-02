import pytest
from django.test import RequestFactory, override_settings
from django.http import HttpResponse

from django_mpesa.middleware import MpesaCallbackIPAllowlistMiddleware, _get_client_ip
import django_mpesa.middleware as mw


@pytest.fixture(autouse=True)
def reset_path_cache():
    mw._MPESA_PATH_CACHE = None
    yield
    mw._MPESA_PATH_CACHE = None


def make_get_response(status=200):
    def get_response(request):
        return HttpResponse(status=status)
    return get_response


def test_non_callback_path_passes_through():
    middleware = MpesaCallbackIPAllowlistMiddleware(make_get_response())
    factory = RequestFactory()
    request = factory.get("/some/other/path/")
    request.META["REMOTE_ADDR"] = "1.2.3.4"
    response = middleware(request)
    assert response.status_code == 200


@override_settings(MPESA={
    **__import__("django.conf", fromlist=["settings"]).settings.MPESA,
    "VERIFY_CALLBACK_SOURCE_IP": False,
})
def test_verify_disabled_allows_any_ip():
    from django_mpesa.conf import mpesa_settings
    mpesa_settings.reload()
    middleware = MpesaCallbackIPAllowlistMiddleware(make_get_response())
    factory = RequestFactory()
    request = factory.post("/mpesa/stk/callback/")
    request.META["REMOTE_ADDR"] = "9.9.9.9"
    response = middleware(request)
    mpesa_settings.reload()
    assert response.status_code == 200


@override_settings(MPESA={
    **__import__("django.conf", fromlist=["settings"]).settings.MPESA,
    "VERIFY_CALLBACK_SOURCE_IP": True,
    "CALLBACK_IP_ALLOWLIST": ["196.201.214.200"],
},
MIDDLEWARE=["django_mpesa.middleware.MpesaCallbackIPAllowlistMiddleware"])
def test_safaricom_ip_allowed_direct():
    from django_mpesa.conf import mpesa_settings
    mpesa_settings.reload()
    middleware = MpesaCallbackIPAllowlistMiddleware(make_get_response())
    factory = RequestFactory()
    request = factory.post("/mpesa/stk/callback/")
    request.META["REMOTE_ADDR"] = "196.201.214.200"
    response = middleware(request)
    mpesa_settings.reload()
    assert response.status_code == 200


@override_settings(MPESA={
    **__import__("django.conf", fromlist=["settings"]).settings.MPESA,
    "VERIFY_CALLBACK_SOURCE_IP": True,
    "CALLBACK_IP_ALLOWLIST": ["196.201.214.200"],
})
def test_non_safaricom_ip_blocked_direct():
    from django_mpesa.conf import mpesa_settings
    mpesa_settings.reload()
    middleware = MpesaCallbackIPAllowlistMiddleware(make_get_response())
    factory = RequestFactory()
    request = factory.post("/mpesa/stk/callback/")
    request.META["REMOTE_ADDR"] = "1.2.3.4"
    response = middleware(request)
    mpesa_settings.reload()
    assert response.status_code == 403


@override_settings(MPESA={
    **__import__("django.conf", fromlist=["settings"]).settings.MPESA,
    "TRUST_FORWARDED_FOR": True,
    "FORWARDED_FOR_TRUSTED_PROXIES": ["10.0.0.1"],
})
def test_x_forwarded_for_resolves_real_ip():
    from django_mpesa.conf import mpesa_settings
    mpesa_settings.reload()
    factory = RequestFactory()
    request = factory.post("/mpesa/stk/callback/")
    request.META["REMOTE_ADDR"] = "10.0.0.1"
    request.META["HTTP_X_FORWARDED_FOR"] = "196.201.214.200, 10.0.0.1"
    ip = _get_client_ip(request)
    mpesa_settings.reload()
    assert ip == "196.201.214.200"


def test_get_client_ip_returns_remote_addr_by_default():
    factory = RequestFactory()
    request = factory.get("/")
    request.META["REMOTE_ADDR"] = "5.6.7.8"
    assert _get_client_ip(request) == "5.6.7.8"


@override_settings(MPESA={
    **__import__("django.conf", fromlist=["settings"]).settings.MPESA,
    "TRUST_FORWARDED_FOR": True,
    "FORWARDED_FOR_TRUSTED_PROXIES": [],
})
def test_x_forwarded_for_no_header_falls_back_to_remote_addr():
    from django_mpesa.conf import mpesa_settings
    mpesa_settings.reload()
    factory = RequestFactory()
    request = factory.get("/")
    request.META["REMOTE_ADDR"] = "5.6.7.8"
    ip = _get_client_ip(request)
    mpesa_settings.reload()
    assert ip == "5.6.7.8"

import pytest
from requests.adapters import HTTPAdapter

from django_mpesa import __version__
from django_mpesa.client.http import get_session


def test_session_has_user_agent():
    session = get_session()
    assert f"django-mpesa/{__version__}" in session.headers["User-Agent"]


def test_session_has_accept_json_header():
    session = get_session()
    assert session.headers["Accept"] == "application/json"


def test_session_has_retry_adapter_on_https():
    session = get_session()
    adapter = session.get_adapter("https://example.com")
    assert isinstance(adapter, HTTPAdapter)


def test_session_has_retry_adapter_on_http():
    session = get_session()
    adapter = session.get_adapter("http://example.com")
    assert isinstance(adapter, HTTPAdapter)


def test_get_session_returns_new_instance_each_call():
    s1 = get_session()
    s2 = get_session()
    assert s1 is not s2

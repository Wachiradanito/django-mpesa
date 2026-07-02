import pytest
from django.test import override_settings

from django_mpesa.exceptions import DarajaAPIError, DarajaConfigError, DarajaValidationError
from django_mpesa.services.c2b import C2BService


class MockClient:
    def __init__(self, response=None, raise_exc=None):
        self.calls = []
        self._response = response or {"ResponseCode": "0", "ResponseDescription": "Success"}
        self._raise = raise_exc

    def post(self, path, payload):
        self.calls.append({"path": path, "payload": payload})
        if self._raise:
            raise self._raise
        return self._response


@pytest.fixture
def mock():
    return MockClient()


def test_register_urls_posts_correct_payload(mock):
    service = C2BService(client=mock)
    service.register_urls()
    assert len(mock.calls) == 1
    payload = mock.calls[0]["payload"]
    assert "ShortCode" in payload
    assert "ConfirmationURL" in payload
    assert "ValidationURL" in payload
    assert payload["ResponseType"] == "Completed"


def test_register_urls_invalid_response_type_raises(mock):
    service = C2BService(client=mock)
    with pytest.raises(DarajaValidationError):
        service.register_urls(response_type="Invalid")
    assert mock.calls == []


def test_register_urls_cancelled_response_type(mock):
    service = C2BService(client=mock)
    service.register_urls(response_type="Cancelled")
    assert mock.calls[0]["payload"]["ResponseType"] == "Cancelled"


def test_simulate_raises_in_production(mock):
    with override_settings(MPESA={
        **__import__("django.conf", fromlist=["settings"]).settings.MPESA,
        "ENV": "production",
    }):
        from django_mpesa.conf import mpesa_settings
        mpesa_settings.reload()
        service = C2BService(client=mock)
        with pytest.raises(DarajaConfigError, match="production"):
            service.simulate("254712345678", 100, "INV-001")
        mpesa_settings.reload()
    assert mock.calls == []


def test_simulate_succeeds_in_sandbox(mock):
    service = C2BService(client=mock)
    result = service.simulate("254712345678", 100, "INV-001")
    assert result["ResponseCode"] == "0"
    assert len(mock.calls) == 1


def test_simulate_validates_phone_before_network(mock):
    service = C2BService(client=mock)
    with pytest.raises(DarajaValidationError):
        service.simulate("not_a_phone", 100, "INV-001")
    assert mock.calls == []


def test_simulate_payload_contains_shortcode(mock):
    service = C2BService(client=mock)
    service.simulate("254712345678", 100, "INV-001")
    payload = mock.calls[0]["payload"]
    assert "ShortCode" in payload
    assert payload["CommandID"] == "CustomerPayBillOnline"

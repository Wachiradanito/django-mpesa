"""
Testing utilities for django-mpesa.

Import in your host app's conftest.py:

    from django_mpesa.testing.fixtures import *  # noqa

Or use the mock client directly:

    from django_mpesa.testing import MockDarajaClient

    def test_my_payment(db):
        mock = MockDarajaClient()
        service = STKPushService(client=mock)
        txn = service.initiate("254712345678", 100, "INV-001", "Payment")
        assert txn.status == "PENDING"
        mock.assert_called_once_with_path("/mpesa/stkpush/v1/processrequest")
"""

from django_mpesa.testing.mock_client import MockDarajaClient

__all__ = ["MockDarajaClient"]

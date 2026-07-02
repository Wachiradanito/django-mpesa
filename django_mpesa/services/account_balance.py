"""
Account Balance query service for django-mpesa.

Queries the M-PESA business account balance. The actual balance arrives
via a callback — this call only confirms the query was accepted.
"""

import logging

from django_mpesa.client.base import BaseDarajaClient
from django_mpesa.conf import mpesa_settings
from django_mpesa.exceptions import DarajaValidationError

logger = logging.getLogger("django_mpesa")

ACCOUNT_BALANCE_PATH = "/mpesa/accountbalance/v1/query"
VALID_IDENTIFIER_TYPES = {"1", "2", "4"}


class AccountBalanceService:
    """Query the M-PESA business account balance."""

    def __init__(self, client: BaseDarajaClient | None = None):
        self.client = client or BaseDarajaClient()

    def query(self, identifier_type: str = "4") -> dict:
        """
        Initiate an account balance query.

        The balance result arrives via a callback to B2C_RESULT_URL —
        this method only returns the synchronous acknowledgement.

        Args:
            identifier_type: "1" = MSISDN, "2" = till, "4" = shortcode (default)

        Returns:
            Raw Daraja acknowledgement dict
        """
        if identifier_type not in VALID_IDENTIFIER_TYPES:
            raise DarajaValidationError(
                f"identifier_type must be one of {sorted(VALID_IDENTIFIER_TYPES)}, "
                f"got {identifier_type!r}."
            )

        payload = {
            "Initiator": mpesa_settings.INITIATOR_NAME,
            "SecurityCredential": mpesa_settings.SECURITY_CREDENTIAL,
            "CommandID": "AccountBalance",
            "PartyA": mpesa_settings.SHORTCODE,
            "IdentifierType": identifier_type,
            "Remarks": "Account balance query",
            "QueueTimeOutURL": mpesa_settings.B2C_TIMEOUT_URL,
            "ResultURL": mpesa_settings.B2C_RESULT_URL,
        }

        return self.client.post(ACCOUNT_BALANCE_PATH, payload)

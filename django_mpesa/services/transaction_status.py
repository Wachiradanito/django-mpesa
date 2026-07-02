"""
Transaction Status query service for django-mpesa.

Used for reconciliation when a transaction is stuck PENDING past a
reasonable SLA. Does NOT mutate any transaction record.
"""

import logging

from django_mpesa.client.base import BaseDarajaClient
from django_mpesa.conf import mpesa_settings
from django_mpesa.exceptions import DarajaValidationError

logger = logging.getLogger("django_mpesa")

TRANSACTION_STATUS_PATH = "/mpesa/transactionstatus/v1/query"
VALID_IDENTIFIER_TYPES = {"1", "2", "4"}


class TransactionStatusService:
    """Query the status of a Daraja transaction by its M-PESA transaction ID."""

    def __init__(self, client: BaseDarajaClient | None = None):
        self.client = client or BaseDarajaClient()

    def query(self, transaction_id: str, identifier_type: str = "1") -> dict:
        """
        Query a transaction's status.

        Args:
            transaction_id: The M-PESA transaction ID (e.g. NLJ7RT61SV)
            identifier_type: "1" = MSISDN, "2" = till, "4" = shortcode

        Returns:
            Raw Daraja response dict

        Raises:
            DarajaValidationError: if identifier_type is invalid
        """
        if identifier_type not in VALID_IDENTIFIER_TYPES:
            raise DarajaValidationError(
                f"identifier_type must be one of {sorted(VALID_IDENTIFIER_TYPES)}, "
                f"got {identifier_type!r}."
            )

        payload = {
            "Initiator": mpesa_settings.INITIATOR_NAME,
            "SecurityCredential": mpesa_settings.SECURITY_CREDENTIAL,
            "CommandID": "TransactionStatusQuery",
            "TransactionID": transaction_id,
            "PartyA": mpesa_settings.SHORTCODE,
            "IdentifierType": identifier_type,
            "ResultURL": mpesa_settings.B2C_RESULT_URL,
            "QueueTimeOutURL": mpesa_settings.B2C_TIMEOUT_URL,
            "Remarks": "Transaction status query",
            "Occasion": "",
        }

        return self.client.post(TRANSACTION_STATUS_PATH, payload)

"""
Reversal service for django-mpesa.

Reverses a completed M-PESA transaction. The original transaction's
status is updated to REVERSED only after the reversal result callback
confirms success — never optimistically on the initiate response.
"""

import logging

from django_mpesa.client.base import BaseDarajaClient
from django_mpesa.conf import mpesa_settings
from django_mpesa.validators import validate_amount

logger = logging.getLogger("django_mpesa")

REVERSAL_PATH = "/mpesa/reversal/v1/request"


class ReversalService:
    """Reverse a completed M-PESA transaction."""

    def __init__(self, client: BaseDarajaClient | None = None):
        self.client = client or BaseDarajaClient()

    def reverse(
        self,
        transaction_id: str,
        amount,
        remarks: str,
        receiver_party: str,
    ) -> dict:
        """
        Initiate a transaction reversal.

        The original transaction's status is updated to REVERSED only
        after the reversal result callback confirms success.

        Args:
            transaction_id: The M-PESA transaction ID to reverse
            amount: Amount to reverse
            remarks: Reason for reversal
            receiver_party: The party to receive the reversal

        Returns:
            Raw Daraja acknowledgement dict

        Raises:
            DarajaValidationError: on invalid amount
            DarajaAPIError: on Daraja API failure
        """
        amt = validate_amount(amount)

        payload = {
            "Initiator": mpesa_settings.INITIATOR_NAME,
            "SecurityCredential": mpesa_settings.SECURITY_CREDENTIAL,
            "CommandID": "TransactionReversal",
            "TransactionID": transaction_id,
            "Amount": int(amt),
            "ReceiverParty": receiver_party,
            "RecieverIdentifierType": "11",
            "ResultURL": mpesa_settings.B2C_RESULT_URL,
            "QueueTimeOutURL": mpesa_settings.B2C_TIMEOUT_URL,
            "Remarks": remarks,
            "Occasion": "",
        }

        return self.client.post(REVERSAL_PATH, payload)

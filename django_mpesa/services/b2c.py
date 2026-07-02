"""
B2C (Business to Customer) service for django-mpesa.

B2C handles outbound payouts — sending money from the business account
to a customer's phone number. Used for seller payouts, salaries, refunds.

Terminal status (SUCCESS / FAILED) arrives via callback, not here.
This service only initiates the request and creates a PENDING record.
"""

import logging

from django_mpesa.client.base import BaseDarajaClient
from django_mpesa.conf import mpesa_settings
from django_mpesa.exceptions import DarajaAPIError
from django_mpesa.models import get_transaction_model
from django_mpesa.validators import (
    validate_amount,
    validate_command_id,
    validate_phone_number,
)

logger = logging.getLogger("django_mpesa")

B2C_PATH = "/mpesa/b2c/v1/paymentrequest"


class B2CService:
    """
    Service for initiating B2C (Business to Customer) payouts.

    Usage:
        service = B2CService()
        txn = service.send_payment(
            phone_number="254712345678",
            amount=500,
            remarks="Seller payout",
        )
        # txn.status == "PENDING"
        # Terminal status arrives via B2C_RESULT_URL callback

    Inject a MockDarajaClient in tests:
        service = B2CService(client=mock_daraja)
    """

    def __init__(self, client: BaseDarajaClient | None = None):
        self.client = client or BaseDarajaClient()

    def send_payment(
        self,
        phone_number: str,
        amount,
        remarks: str,
        occasion: str = "",
        command_id: str = "BusinessPayment",
    ):
        """
        Initiate a B2C payout.

        Args:
            phone_number: Recipient's phone number
            amount: Amount to send
            remarks: Description of the payment (max 100 chars)
            occasion: Optional additional context (max 100 chars)
            command_id: One of "BusinessPayment", "SalaryPayment", "PromotionPayment"

        Returns:
            Saved transaction instance with status=PENDING

        Raises:
            DarajaValidationError: On invalid inputs (no network call made)
            DarajaAPIError: On Daraja API failure (no transaction created)
        """
        phone = validate_phone_number(phone_number)
        amt = validate_amount(amount)
        cmd = validate_command_id(command_id)

        if not remarks or not remarks.strip():
            from django_mpesa.exceptions import DarajaValidationError
            raise DarajaValidationError("remarks must not be empty.")
        if len(remarks) > 100:
            from django_mpesa.exceptions import DarajaValidationError
            raise DarajaValidationError(
                f"remarks must be 100 characters or fewer, got {len(remarks)}."
            )

        payload = {
            "InitiatorName": mpesa_settings.INITIATOR_NAME,
            "SecurityCredential": mpesa_settings.SECURITY_CREDENTIAL,
            "CommandID": cmd,
            "Amount": int(amt),
            "PartyA": mpesa_settings.SHORTCODE,
            "PartyB": phone,
            "Remarks": remarks.strip(),
            "QueueTimeOutURL": mpesa_settings.B2C_TIMEOUT_URL,
            "ResultURL": mpesa_settings.B2C_RESULT_URL,
            "Occasion": occasion,
        }

        response = self.client.post(B2C_PATH, payload)

        if response.get("ResponseCode") not in ("0", 0):
            raise DarajaAPIError(
                f"B2C initiation failed: {response.get('ResponseDescription')}",
                result_code=response.get("ResponseCode"),
                result_desc=response.get("ResponseDescription"),
            )

        Transaction = get_transaction_model()
        txn = Transaction.objects.create(
            transaction_type="B2C",
            status="PENDING",
            conversation_id=response.get("ConversationID"),
            originator_conversation_id=response.get("OriginatorConversationID"),
            phone_number=phone,
            amount=amt,
            account_reference=phone,  # B2C uses phone as reference
            transaction_desc=remarks[:13],
        )

        logger.info(
            "django_mpesa: B2C initiated — txn=%s conversation_id=%s",
            txn.id,
            txn.conversation_id,
        )

        return txn

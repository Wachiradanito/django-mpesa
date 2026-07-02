"""
C2B (Customer to Business) service for django-mpesa.

C2B handles payments where the customer initiates the transfer from
their M-PESA menu (paybill or till). The library receives callbacks;
it does not initiate anything.

Two service methods:
- register_urls(): one-time setup to tell Safaricom where to send callbacks
- simulate(): sandbox-only testing tool
"""

import logging

from django_mpesa.client.base import BaseDarajaClient
from django_mpesa.conf import mpesa_settings
from django_mpesa.exceptions import DarajaConfigError, DarajaValidationError
from django_mpesa.validators import validate_amount, validate_phone_number

logger = logging.getLogger("django_mpesa")

REGISTER_URL_PATH = "/mpesa/c2b/v1/registerurl"
SIMULATE_PATH = "/mpesa/c2b/v1/simulate"

VALID_RESPONSE_TYPES = {"Completed", "Cancelled"}


class C2BService:
    """
    Service for C2B URL registration and sandbox simulation.

    Validation and confirmation are handled by callback views, not here —
    C2B is Safaricom pushing data to you, not you initiating a request.
    """

    def __init__(self, client: BaseDarajaClient | None = None):
        self.client = client or BaseDarajaClient()

    def register_urls(self, response_type: str = "Completed") -> dict:
        """
        Register validation and confirmation URLs with Safaricom.

        This is a one-time infrastructure call — run it once during
        deployment setup, not on every request.

        Args:
            response_type: "Completed" (accept all) or "Cancelled" (reject all).
                           Use "Completed" for production.

        Returns:
            Raw Daraja response dict

        Raises:
            DarajaValidationError: if response_type is invalid
            DarajaAPIError: on Daraja API failure
        """
        if response_type not in VALID_RESPONSE_TYPES:
            raise DarajaValidationError(
                f"response_type must be one of {sorted(VALID_RESPONSE_TYPES)}, "
                f"got {response_type!r}."
            )

        payload = {
            "ShortCode": mpesa_settings.SHORTCODE,
            "ResponseType": response_type,
            "ConfirmationURL": mpesa_settings.C2B_CONFIRMATION_URL,
            "ValidationURL": mpesa_settings.C2B_VALIDATION_URL,
        }

        response = self.client.post(REGISTER_URL_PATH, payload)
        logger.info(
            "django_mpesa: C2B URLs registered — response=%s", response
        )
        return response

    def simulate(self, phone_number: str, amount, bill_ref: str) -> dict:
        """
        Simulate a C2B payment — sandbox only.

        Args:
            phone_number: Paying customer's phone number
            amount: Amount to simulate
            bill_ref: Bill reference number (account number)

        Returns:
            Raw Daraja response dict

        Raises:
            DarajaConfigError: if called in production
            DarajaValidationError: on invalid inputs
            DarajaAPIError: on Daraja API failure
        """
        if mpesa_settings.ENV == "production":
            raise DarajaConfigError(
                "C2BService.simulate() is not available in production. "
                "This method is for sandbox testing only."
            )

        phone = validate_phone_number(phone_number)
        amt = validate_amount(amount)

        payload = {
            "ShortCode": mpesa_settings.SHORTCODE,
            "CommandID": "CustomerPayBillOnline",
            "Amount": int(amt),
            "Msisdn": phone,
            "BillRefNumber": bill_ref,
        }

        return self.client.post(SIMULATE_PATH, payload)

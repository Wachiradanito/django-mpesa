"""
STK Push service for django-mpesa.

Maps to Daraja's Lipa Na M-PESA Online API. Triggers the M-PESA PIN
prompt on the customer's phone.
"""

import base64
import logging
from datetime import datetime
from decimal import Decimal

import pytz

from django_mpesa.client.base import BaseDarajaClient
from django_mpesa.conf import mpesa_settings
from django_mpesa.exceptions import DarajaAPIError
from django_mpesa.models import get_transaction_model
from django_mpesa.validators import (
    validate_account_reference,
    validate_amount,
    validate_phone_number,
    validate_transaction_desc,
)

logger = logging.getLogger("django_mpesa")

STK_PUSH_PATH = "/mpesa/stkpush/v1/processrequest"
STK_QUERY_PATH = "/mpesa/stkpushquery/v1/query"

NAIROBI_TZ = pytz.timezone("Africa/Nairobi")


class STKPushService:
    """
    Service for initiating and querying STK Push (Lipa Na M-PESA Online) requests.

    Usage:
        service = STKPushService()
        txn = service.initiate(
            phone_number="254712345678",
            amount=100,
            account_reference="INV-001",
            transaction_desc="Payment",
        )

    Inject a MockDarajaClient in tests:
        service = STKPushService(client=mock_daraja)
    """

    def __init__(self, client: BaseDarajaClient | None = None):
        self.client = client or BaseDarajaClient()

    def initiate(
        self,
        phone_number: str,
        amount,
        account_reference: str,
        transaction_desc: str,
    ):
        """
        Initiate an STK Push request.

        Validates all inputs before making any network call. Creates a
        PENDING transaction record only on a successful Daraja response.

        Args:
            phone_number: Customer phone in any accepted format (normalised internally)
            amount: Payment amount — int, float, str, or Decimal
            account_reference: Reference tied to this payment (max 12 chars)
            transaction_desc: Human-readable description (max 13 chars)

        Returns:
            Saved transaction instance with status=PENDING

        Raises:
            DarajaValidationError: On invalid inputs (no network call made)
            DarajaAPIError: On Daraja API failure (no transaction created)
        """
        # Step 1: Validate all inputs before touching the network
        phone = validate_phone_number(phone_number)
        amt = validate_amount(amount)
        ref = validate_account_reference(account_reference)
        desc = validate_transaction_desc(transaction_desc)

        # Step 2: Build password and timestamp
        password, timestamp = self._build_password()

        shortcode = mpesa_settings.SHORTCODE

        # Step 3: Build payload
        # Amount sent as int — Daraja rejects decimal amounts for STK Push
        payload = {
            "BusinessShortCode": shortcode,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": int(amt),
            "PartyA": phone,
            "PartyB": shortcode,
            "PhoneNumber": phone,
            "CallBackURL": mpesa_settings.STK_CALLBACK_URL,
            "AccountReference": ref,
            "TransactionDesc": desc,
        }

        # Step 4: Call Daraja
        response = self.client.post(STK_PUSH_PATH, payload)

        # Step 5: Validate response
        if response.get("ResponseCode") != "0":
            raise DarajaAPIError(
                f"STK Push initiation failed: {response.get('ResponseDescription')}",
                result_code=response.get("ResponseCode"),
                result_desc=response.get("ResponseDescription"),
            )

        # Step 6: Create transaction record only after a successful response
        Transaction = get_transaction_model()
        txn = Transaction.objects.create(
            transaction_type="STK_PUSH",
            status="PENDING",
            checkout_request_id=response["CheckoutRequestID"],
            merchant_request_id=response.get("MerchantRequestID"),
            phone_number=phone,
            amount=amt,
            account_reference=ref,
            transaction_desc=desc,
        )

        logger.info(
            "django_mpesa: STK Push initiated — txn=%s checkout_request_id=%s",
            txn.id,
            txn.checkout_request_id,
        )

        return txn

    def query(self, checkout_request_id: str) -> dict:
        """
        Query the status of a pending STK Push request.

        Useful for reconciliation when the callback hasn't arrived within
        a reasonable window. Does NOT mutate any transaction record —
        the caller decides what to do with the response.

        Args:
            checkout_request_id: The CheckoutRequestID from the initiate() response

        Returns:
            Raw response dict from Daraja
        """
        password, timestamp = self._build_password()

        payload = {
            "BusinessShortCode": mpesa_settings.SHORTCODE,
            "Password": password,
            "Timestamp": timestamp,
            "CheckoutRequestID": checkout_request_id,
        }

        return self.client.post(STK_QUERY_PATH, payload)

    def _build_password(self) -> tuple[str, str]:
        """
        Build the Daraja STK Push password field.

        Password = base64(BusinessShortCode + Passkey + Timestamp)
        Timestamp = YYYYMMDDHHmmss in Africa/Nairobi timezone.

        Returns:
            (base64_password, timestamp) tuple — both use the same moment
        """
        timestamp = datetime.now(NAIROBI_TZ).strftime("%Y%m%d%H%M%S")
        raw = f"{mpesa_settings.SHORTCODE}{mpesa_settings.PASSKEY}{timestamp}"
        password = base64.b64encode(raw.encode()).decode()
        return password, timestamp

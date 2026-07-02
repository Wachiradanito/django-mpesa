"""
Input validators for django-mpesa.

All validators are plain functions that either return the normalised
value or raise DarajaValidationError. They are called explicitly by
service methods before any network call is made.
"""

from decimal import Decimal, InvalidOperation

from django_mpesa.exceptions import DarajaValidationError

VALID_COMMAND_IDS = frozenset({
    "BusinessPayment",
    "SalaryPayment",
    "PromotionPayment",
})


def validate_phone_number(value: str) -> str:
    """
    Validate and normalise a Kenyan M-PESA phone number to 2547XXXXXXXX format.

    Accepted formats:
        2547XXXXXXXX  (12 digits, already normalised)
        +2547XXXXXXXX (with leading +)
        07XXXXXXXX    (10 digits, local format)
        7XXXXXXXX     (9 digits, short local format)

    Returns:
        Normalised string in 2547XXXXXXXX format (12 digits, no +)

    Raises:
        DarajaValidationError: if the value cannot be normalised
    """
    if not isinstance(value, str):
        raise DarajaValidationError(
            f"Phone number must be a string, got {type(value).__name__!r}."
        )

    cleaned = value.strip().lstrip("+")

    if not cleaned.isdigit():
        raise DarajaValidationError(
            f"Phone number must contain only digits (after stripping +), got {value!r}."
        )

    # Already in 254 format
    if cleaned.startswith("254") and len(cleaned) == 12:
        return cleaned

    # Local 07XXXXXXXX format
    if cleaned.startswith("0") and len(cleaned) == 10:
        return "254" + cleaned[1:]

    # Short 7XXXXXXXX format
    if cleaned.startswith("7") and len(cleaned) == 9:
        return "254" + cleaned

    raise DarajaValidationError(
        f"Phone number {value!r} could not be normalised to 2547XXXXXXXX format. "
        f"Accepted formats: 2547XXXXXXXX, +2547XXXXXXXX, 07XXXXXXXX, 7XXXXXXXX."
    )


def validate_amount(value) -> Decimal:
    """
    Validate and convert a payment amount to Decimal.

    Accepts int, float, str, or Decimal. Floats are converted via str()
    to avoid binary floating-point precision issues.

    Returns:
        Decimal with up to 2 decimal places

    Raises:
        DarajaValidationError: if value is zero, negative, non-numeric,
                               or has more than 2 decimal places
    """
    if isinstance(value, float):
        # Use str() conversion to avoid float binary representation leaking
        # e.g. Decimal(100.5) -> Decimal('100.4999...'), but
        #      Decimal(str(100.5)) -> Decimal('100.5')
        try:
            decimal_value = Decimal(str(value))
        except InvalidOperation:
            raise DarajaValidationError(f"Amount {value!r} is not a valid number.")
    elif isinstance(value, (int, str, Decimal)):
        try:
            decimal_value = Decimal(str(value))
        except InvalidOperation:
            raise DarajaValidationError(f"Amount {value!r} is not a valid number.")
    else:
        raise DarajaValidationError(
            f"Amount must be a number (int, float, Decimal, or str), "
            f"got {type(value).__name__!r}."
        )

    if decimal_value <= 0:
        raise DarajaValidationError(
            f"Amount must be greater than zero, got {decimal_value}."
        )

    # Check decimal places — Safaricom rejects fractional amounts on some APIs
    sign, digits, exponent = decimal_value.as_tuple()
    if isinstance(exponent, int) and exponent < -2:
        raise DarajaValidationError(
            f"Amount {decimal_value} has more than 2 decimal places. "
            f"M-PESA amounts must be whole shillings or have at most 2 decimal places."
        )

    return decimal_value


def validate_account_reference(value: str) -> str:
    """
    Validate an account reference string (max 12 characters per Daraja spec).

    Returns:
        Stripped string

    Raises:
        DarajaValidationError: if empty or longer than 12 characters
    """
    if not isinstance(value, str):
        raise DarajaValidationError(
            f"account_reference must be a string, got {type(value).__name__!r}."
        )

    stripped = value.strip()

    if not stripped:
        raise DarajaValidationError("account_reference must not be empty.")

    if len(stripped) > 12:
        raise DarajaValidationError(
            f"account_reference must be 12 characters or fewer "
            f"(Daraja limit), got {len(stripped)}: {stripped!r}."
        )

    return stripped


def validate_transaction_desc(value: str) -> str:
    """
    Validate a transaction description string (max 13 characters per Daraja spec).

    Returns:
        Stripped string

    Raises:
        DarajaValidationError: if empty or longer than 13 characters
    """
    if not isinstance(value, str):
        raise DarajaValidationError(
            f"transaction_desc must be a string, got {type(value).__name__!r}."
        )

    stripped = value.strip()

    if not stripped:
        raise DarajaValidationError("transaction_desc must not be empty.")

    if len(stripped) > 13:
        raise DarajaValidationError(
            f"transaction_desc must be 13 characters or fewer "
            f"(Daraja limit), got {len(stripped)}: {stripped!r}."
        )

    return stripped


def validate_command_id(value: str) -> str:
    """
    Validate a B2C command ID.

    Valid values: 'BusinessPayment', 'SalaryPayment', 'PromotionPayment'

    Returns:
        The value unchanged if valid

    Raises:
        DarajaValidationError: if not one of the valid values
    """
    if value not in VALID_COMMAND_IDS:
        raise DarajaValidationError(
            f"command_id must be one of {sorted(VALID_COMMAND_IDS)}, got {value!r}."
        )
    return value

from decimal import Decimal

import pytest

from django_mpesa.exceptions import DarajaValidationError
from django_mpesa.validators import (
    validate_account_reference,
    validate_amount,
    validate_command_id,
    validate_phone_number,
    validate_transaction_desc,
)


# ------------------------------------------------------------------
# Phone number
# ------------------------------------------------------------------

def test_254_format_passthrough():
    assert validate_phone_number("254712345678") == "254712345678"


def test_plus_prefix_stripped():
    assert validate_phone_number("+254712345678") == "254712345678"


def test_07_format_normalised():
    assert validate_phone_number("0712345678") == "254712345678"


def test_7_format_normalised():
    assert validate_phone_number("712345678") == "254712345678"


def test_whitespace_stripped_from_phone():
    assert validate_phone_number("  0712345678  ") == "254712345678"


def test_invalid_phone_letters_raises():
    with pytest.raises(DarajaValidationError):
        validate_phone_number("0712abc678")


def test_invalid_phone_too_short_raises():
    with pytest.raises(DarajaValidationError):
        validate_phone_number("071234")


def test_invalid_phone_wrong_prefix_raises():
    with pytest.raises(DarajaValidationError):
        validate_phone_number("1234567890123")


def test_non_string_phone_raises():
    with pytest.raises(DarajaValidationError):
        validate_phone_number(254712345678)


# ------------------------------------------------------------------
# Amount
# ------------------------------------------------------------------

def test_int_converted_to_decimal():
    result = validate_amount(100)
    assert result == Decimal("100")
    assert isinstance(result, Decimal)


def test_float_converted_safely():
    result = validate_amount(100.5)
    assert result == Decimal("100.5")


def test_decimal_passthrough():
    result = validate_amount(Decimal("250.00"))
    assert result == Decimal("250.00")


def test_string_amount_converted():
    result = validate_amount("500")
    assert result == Decimal("500")


def test_zero_raises():
    with pytest.raises(DarajaValidationError):
        validate_amount(0)


def test_negative_raises():
    with pytest.raises(DarajaValidationError):
        validate_amount(-100)


def test_more_than_2_decimal_places_raises():
    with pytest.raises(DarajaValidationError):
        validate_amount(Decimal("100.123"))


def test_non_numeric_string_raises():
    with pytest.raises(DarajaValidationError):
        validate_amount("not_a_number")


def test_wrong_type_raises():
    with pytest.raises(DarajaValidationError):
        validate_amount([100])


# ------------------------------------------------------------------
# Account reference
# ------------------------------------------------------------------

def test_valid_account_reference():
    assert validate_account_reference("INV-001") == "INV-001"


def test_account_reference_strips_whitespace():
    assert validate_account_reference("  INV-001  ") == "INV-001"


def test_account_reference_exactly_12_chars():
    assert validate_account_reference("A" * 12) == "A" * 12


def test_account_reference_too_long_raises():
    with pytest.raises(DarajaValidationError):
        validate_account_reference("A" * 13)


def test_account_reference_empty_raises():
    with pytest.raises(DarajaValidationError):
        validate_account_reference("   ")


def test_account_reference_non_string_raises():
    with pytest.raises(DarajaValidationError):
        validate_account_reference(12345)


# ------------------------------------------------------------------
# Transaction description
# ------------------------------------------------------------------

def test_valid_transaction_desc():
    assert validate_transaction_desc("Payment") == "Payment"


def test_transaction_desc_exactly_13_chars():
    assert validate_transaction_desc("A" * 13) == "A" * 13


def test_transaction_desc_too_long_raises():
    with pytest.raises(DarajaValidationError):
        validate_transaction_desc("A" * 14)


def test_transaction_desc_empty_raises():
    with pytest.raises(DarajaValidationError):
        validate_transaction_desc("")


# ------------------------------------------------------------------
# Command ID
# ------------------------------------------------------------------

def test_business_payment_valid():
    assert validate_command_id("BusinessPayment") == "BusinessPayment"


def test_salary_payment_valid():
    assert validate_command_id("SalaryPayment") == "SalaryPayment"


def test_promotion_payment_valid():
    assert validate_command_id("PromotionPayment") == "PromotionPayment"


def test_invalid_command_id_raises():
    with pytest.raises(DarajaValidationError):
        validate_command_id("SendMoney")


def test_lowercase_command_id_raises():
    with pytest.raises(DarajaValidationError):
        validate_command_id("businesspayment")

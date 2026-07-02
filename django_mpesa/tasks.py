"""
Celery tasks for processing M-PESA callbacks.

Each task:
1. Loads the raw CallbackLog row
2. Parses the payload
3. Acquires a select_for_update() row lock on the transaction
4. Checks for terminal state (idempotency guard)
5. Updates the transaction status
6. Fires the appropriate signal OUTSIDE the lock

The signal fires after the atomic block exits so slow receivers never
hold the database row lock open.
"""

import logging
from decimal import Decimal

from django.db import transaction as db_transaction
from django.utils import timezone

from django_mpesa.conf import mpesa_settings
from django_mpesa.models import TERMINAL_STATES, get_callback_log_model, get_transaction_model
from django_mpesa.signals import (
    payment_confirmed,
    payment_failed,
    payout_completed,
    payout_failed,
)

logger = logging.getLogger("django_mpesa")


def _get_shared_task():
    """Return Celery's shared_task decorator if available, else a no-op."""
    try:
        from celery import shared_task  # pragma: no cover
        return shared_task  # pragma: no cover
    except ImportError:
        return None


def _make_task(func):
    """
    Wrap func as a Celery shared_task if Celery is available and USE_CELERY
    is True. Otherwise return it as a plain callable.
    """
    shared_task = _get_shared_task()
    if shared_task is not None and mpesa_settings.USE_CELERY:  # pragma: no cover
        return shared_task(  # pragma: no cover
            bind=True,
            max_retries=mpesa_settings.CELERY_TASK_MAX_RETRIES,
            retry_backoff=mpesa_settings.CELERY_TASK_RETRY_BACKOFF,
        )(func)
    return func


# ---------------------------------------------------------------------------
# STK Push callback processing
# ---------------------------------------------------------------------------

def process_stk_callback(callback_log_id: str, _self=None):
    """
    Process an STK Push callback.

    Idempotency is guaranteed by:
    1. select_for_update() — serialises concurrent deliveries
    2. Terminal state check — second delivery exits silently
    """
    CallbackLog = get_callback_log_model()
    Transaction = get_transaction_model()

    try:
        log = CallbackLog.objects.get(id=callback_log_id)
    except CallbackLog.DoesNotExist:
        logger.error(
            "django_mpesa: CallbackLog %s not found — cannot process STK callback",
            callback_log_id,
        )
        return

    body = log.raw_body
    stk = body.get("Body", {}).get("stkCallback", {})
    checkout_request_id = stk.get("CheckoutRequestID")
    result_code = stk.get("ResultCode")
    result_desc = stk.get("ResultDesc", "")

    if checkout_request_id is None:
        logger.error(
            "django_mpesa: STK callback missing CheckoutRequestID in log %s",
            callback_log_id,
        )
        log.error = "Missing CheckoutRequestID in payload"
        log.save(update_fields=["error"])
        return

    # Parse receipt number from metadata (present only on success)
    receipt = None
    if result_code == 0:
        for item in stk.get("CallbackMetadata", {}).get("Item", []):
            if item.get("Name") == "MpesaReceiptNumber":
                receipt = item.get("Value")
                break

    txn = None
    try:
        with db_transaction.atomic():
            try:
                txn = Transaction.objects.select_for_update().get(
                    checkout_request_id=checkout_request_id
                )
            except Transaction.DoesNotExist:
                logger.warning(
                    "django_mpesa: STK callback for unknown checkout_request_id=%s "
                    "(log=%s) — no matching transaction found",
                    checkout_request_id,
                    callback_log_id,
                )
                log.error = f"No transaction found for checkout_request_id={checkout_request_id}"
                log.save(update_fields=["error"])
                return

            # Idempotency check — terminal state guard
            if txn.status in TERMINAL_STATES:
                logger.info(
                    "django_mpesa: STK callback for already-settled txn=%s "
                    "(status=%s) — no-op",
                    txn.id,
                    txn.status,
                )
                log.processed = True
                log.save(update_fields=["processed"])
                return

            # Settle the transaction
            txn.status = "SUCCESS" if result_code == 0 else "FAILED"
            txn.result_code = result_code
            txn.result_desc = result_desc
            txn.settled_at = timezone.now()
            txn.raw_callback_payload = body
            if receipt:
                txn.mpesa_receipt_number = receipt
            txn.save()

            log.related_transaction_id = txn.id
            log.processed = True
            log.save(update_fields=["related_transaction_id", "processed"])

    except Exception as exc:
        logger.exception(
            "django_mpesa: error processing STK callback log=%s", callback_log_id
        )
        if _self is not None:
            raise _self.retry(exc=exc)
        raise

    # Fire signal OUTSIDE the atomic block — lock is released, slow
    # receivers do not hold the row lock open
    if txn is not None:
        try:
            if result_code == 0:
                payment_confirmed.send(sender=Transaction, transaction=txn)
            else:
                payment_failed.send(
                    sender=Transaction,
                    transaction=txn,
                    result_code=result_code,
                    result_desc=result_desc,
                )
        except Exception:
            logger.exception(
                "django_mpesa: signal receiver raised for txn=%s — "
                "transaction is settled but receiver failed",
                txn.id,
            )


# ---------------------------------------------------------------------------
# B2C result callback processing
# ---------------------------------------------------------------------------

def process_b2c_result(callback_log_id: str, _self=None):
    """Process a B2C result callback (success or failure)."""
    CallbackLog = get_callback_log_model()
    Transaction = get_transaction_model()

    try:
        log = CallbackLog.objects.get(id=callback_log_id)
    except CallbackLog.DoesNotExist:
        logger.error("django_mpesa: CallbackLog %s not found", callback_log_id)
        return

    result = log.raw_body.get("Result", {})
    conversation_id = result.get("ConversationID")
    result_code = result.get("ResultCode")
    result_desc = result.get("ResultDesc", "")
    transaction_id = result.get("TransactionID")

    if conversation_id is None:
        logger.error(
            "django_mpesa: B2C result missing ConversationID in log %s",
            callback_log_id,
        )
        log.error = "Missing ConversationID in payload"
        log.save(update_fields=["error"])
        return

    # Parse receipt from ResultParameters if success
    receipt = None
    if result_code == 0:
        params = result.get("ResultParameters", {}).get("ResultParameter", [])
        for param in params:
            if param.get("Key") == "TransactionReceipt":
                receipt = param.get("Value")
                break
        if not receipt and transaction_id:
            receipt = transaction_id

    txn = None
    is_success = result_code == 0

    try:
        with db_transaction.atomic():
            try:
                txn = Transaction.objects.select_for_update().get(
                    conversation_id=conversation_id
                )
            except Transaction.DoesNotExist:
                logger.warning(
                    "django_mpesa: B2C result for unknown conversation_id=%s",
                    conversation_id,
                )
                log.error = f"No transaction found for conversation_id={conversation_id}"
                log.save(update_fields=["error"])
                return

            if txn.status in TERMINAL_STATES:
                log.processed = True
                log.save(update_fields=["processed"])
                return

            txn.status = "SUCCESS" if is_success else "FAILED"
            txn.result_code = result_code
            txn.result_desc = result_desc
            txn.settled_at = timezone.now()
            txn.raw_callback_payload = log.raw_body
            if receipt:
                txn.mpesa_receipt_number = receipt
            txn.save()

            log.related_transaction_id = txn.id
            log.processed = True
            log.save(update_fields=["related_transaction_id", "processed"])

    except Exception as exc:
        logger.exception(
            "django_mpesa: error processing B2C result log=%s", callback_log_id
        )
        if _self is not None:
            raise _self.retry(exc=exc)
        raise

    if txn is not None:
        try:
            if is_success:
                payout_completed.send(sender=Transaction, transaction=txn)
            else:
                payout_failed.send(
                    sender=Transaction,
                    transaction=txn,
                    result_code=result_code,
                    result_desc=result_desc,
                )
        except Exception:
            logger.exception(
                "django_mpesa: signal receiver raised for B2C txn=%s", txn.id
            )


# ---------------------------------------------------------------------------
# B2C timeout callback processing
# ---------------------------------------------------------------------------

def process_b2c_timeout(callback_log_id: str, _self=None):
    """Process a B2C timeout callback."""
    CallbackLog = get_callback_log_model()
    Transaction = get_transaction_model()

    try:
        log = CallbackLog.objects.get(id=callback_log_id)
    except CallbackLog.DoesNotExist:
        logger.error("django_mpesa: CallbackLog %s not found", callback_log_id)
        return

    # B2C timeout payloads use the same Result structure
    result = log.raw_body.get("Result", {})
    conversation_id = result.get("ConversationID")

    if conversation_id is None:
        log.error = "Missing ConversationID in timeout payload"
        log.save(update_fields=["error"])
        return

    txn = None
    try:
        with db_transaction.atomic():
            try:
                txn = Transaction.objects.select_for_update().get(
                    conversation_id=conversation_id
                )
            except Transaction.DoesNotExist:
                log.error = f"No transaction for conversation_id={conversation_id}"
                log.save(update_fields=["error"])
                return

            if txn.status in TERMINAL_STATES:
                log.processed = True
                log.save(update_fields=["processed"])
                return

            txn.status = "TIMEOUT"
            txn.result_desc = "B2C request timed out"
            txn.settled_at = timezone.now()
            txn.raw_callback_payload = log.raw_body
            txn.save()

            log.related_transaction_id = txn.id
            log.processed = True
            log.save(update_fields=["related_transaction_id", "processed"])

    except Exception as exc:
        logger.exception(
            "django_mpesa: error processing B2C timeout log=%s", callback_log_id
        )
        if _self is not None:
            raise _self.retry(exc=exc)
        raise

    if txn is not None:
        try:
            payout_failed.send(
                sender=Transaction,
                transaction=txn,
                result_code=None,
                result_desc="Timeout",
            )
        except Exception:
            logger.exception(
                "django_mpesa: signal receiver raised for B2C timeout txn=%s", txn.id
            )


# ---------------------------------------------------------------------------
# C2B confirmation callback processing
# ---------------------------------------------------------------------------

def process_c2b_confirmation(callback_log_id: str, _self=None):
    """
    Process a C2B confirmation callback.

    Uses get_or_create because a C2B payment may arrive without a prior
    initiation call (customer pays directly via paybill).
    """
    CallbackLog = get_callback_log_model()
    Transaction = get_transaction_model()

    try:
        log = CallbackLog.objects.get(id=callback_log_id)
    except CallbackLog.DoesNotExist:
        logger.error("django_mpesa: CallbackLog %s not found", callback_log_id)
        return

    body = log.raw_body
    trans_id = body.get("TransID", "")
    trans_amount = body.get("TransAmount", "0")
    msisdn = body.get("MSISDN", "")
    bill_ref = body.get("BillRefNumber", "")

    try:
        amount = Decimal(str(trans_amount))
    except Exception:
        amount = Decimal("0")

    txn = None
    try:
        with db_transaction.atomic():
            # First check: has this exact M-PESA receipt already been processed?
            # This is the idempotency guard for C2B duplicate confirmations.
            if trans_id and Transaction.objects.filter(
                mpesa_receipt_number=trans_id
            ).exists():
                log.processed = True
                log.save(update_fields=["processed"])
                return

            # Look for an existing PENDING transaction with this reference
            existing = Transaction.objects.select_for_update().filter(
                account_reference=bill_ref,
                status="PENDING",
                transaction_type="C2B",
            ).first()

            if existing:
                txn = existing
                txn.status = "SUCCESS"
                txn.mpesa_receipt_number = trans_id
                txn.settled_at = timezone.now()
                txn.raw_callback_payload = body
                txn.save()
            else:
                # Create a new transaction directly as SUCCESS
                txn = Transaction.objects.create(
                    transaction_type="C2B",
                    status="SUCCESS",
                    mpesa_receipt_number=trans_id,
                    phone_number=msisdn or "000000000000",
                    amount=amount,
                    account_reference=bill_ref or "UNKNOWN",
                    transaction_desc="C2B Payment",
                    settled_at=timezone.now(),
                    raw_callback_payload=body,
                )

            log.related_transaction_id = txn.id
            log.processed = True
            log.save(update_fields=["related_transaction_id", "processed"])

    except Exception as exc:
        logger.exception(
            "django_mpesa: error processing C2B confirmation log=%s", callback_log_id
        )
        if _self is not None:
            raise _self.retry(exc=exc)
        raise

    if txn is not None:
        try:
            payment_confirmed.send(sender=Transaction, transaction=txn)
        except Exception:
            logger.exception(
                "django_mpesa: signal receiver raised for C2B txn=%s", txn.id
            )

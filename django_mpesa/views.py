"""
Callback views for django-mpesa.

All views follow the same pattern:
1. Log raw payload to CallbackLog (unconditional — even if malformed)
2. Dispatch processing task (async or sync)
3. Return {"ResultCode": 0, "ResultDesc": "Accepted"} — always

Safaricom must always receive a 200. Internal errors are logged but
never surfaced in the HTTP response.

C2BValidationView is the only exception — it may return a non-zero
ResultCode to reject a transaction before it is accepted.
"""

import logging

from rest_framework.response import Response
from rest_framework.views import APIView

from django_mpesa.conf import mpesa_settings
from django_mpesa.middleware import _get_client_ip
from django_mpesa.models import get_callback_log_model
from django_mpesa.signals import c2b_validation_received
from django_mpesa.tasks import (
    process_b2c_result,
    process_b2c_timeout,
    process_c2b_confirmation,
    process_stk_callback,
)

logger = logging.getLogger("django_mpesa")

ACCEPTED = {"ResultCode": 0, "ResultDesc": "Accepted"}


def _dispatch(task_func, log_id: str) -> None:
    """
    Dispatch a processing task — async (Celery) or synchronous.
    Never raises; errors are logged internally.
    """
    try:
        if mpesa_settings.USE_CELERY:
            task_func.delay(str(log_id))
        else:
            task_func(str(log_id))
    except Exception:
        logger.exception(
            "django_mpesa: failed to dispatch task %s for log %s",
            getattr(task_func, "__name__", task_func),
            log_id,
        )


class STKCallbackView(APIView):
    """Receives STK Push (Lipa Na M-PESA) callbacks from Safaricom."""

    authentication_classes = []
    permission_classes = []

    def post(self, request):
        source_ip = _get_client_ip(request)

        try:
            body = request.data if isinstance(request.data, dict) else {}
        except Exception:  # pragma: no cover
            body = {}

        CallbackLog = get_callback_log_model()
        try:
            log = CallbackLog.objects.create(
                callback_type="STK",
                source_ip=source_ip or "0.0.0.0",
                raw_body=body,
            )
            _dispatch(process_stk_callback, log.id)
        except Exception:  # pragma: no cover
            logger.exception("django_mpesa: error logging STK callback")

        return Response(ACCEPTED)


class C2BValidationView(APIView):
    """
    Receives C2B validation callbacks from Safaricom.

    This is the only view that may return a non-zero ResultCode to
    reject a transaction. Signal receivers can return a rejection dict.
    """

    authentication_classes = []
    permission_classes = []

    def post(self, request):
        source_ip = _get_client_ip(request)

        try:
            body = request.data if isinstance(request.data, dict) else {}
        except Exception:  # pragma: no cover
            body = {}

        CallbackLog = get_callback_log_model()
        try:
            CallbackLog.objects.create(
                callback_type="C2B_VALIDATION",
                source_ip=source_ip or "0.0.0.0",
                raw_body=body,
            )
        except Exception:  # pragma: no cover
            logger.exception("django_mpesa: error logging C2B validation callback")

        # Fire signal and check if any receiver wants to reject
        try:
            responses = c2b_validation_received.send(
                sender=self.__class__,
                raw_payload=body,
            )
            for _, retval in responses:
                if isinstance(retval, dict) and "ResultCode" in retval:
                    return Response(retval)
        except Exception:  # pragma: no cover
            logger.exception("django_mpesa: error in C2B validation signal receiver")

        return Response(ACCEPTED)


class C2BConfirmationView(APIView):
    """Receives C2B confirmation callbacks from Safaricom."""

    authentication_classes = []
    permission_classes = []

    def post(self, request):
        source_ip = _get_client_ip(request)

        try:
            body = request.data if isinstance(request.data, dict) else {}
        except Exception:  # pragma: no cover
            body = {}

        CallbackLog = get_callback_log_model()
        try:
            log = CallbackLog.objects.create(
                callback_type="C2B_CONFIRMATION",
                source_ip=source_ip or "0.0.0.0",
                raw_body=body,
            )
            _dispatch(process_c2b_confirmation, log.id)
        except Exception:  # pragma: no cover
            logger.exception("django_mpesa: error logging C2B confirmation callback")

        return Response(ACCEPTED)


class B2CResultView(APIView):
    """Receives B2C result callbacks from Safaricom."""

    authentication_classes = []
    permission_classes = []

    def post(self, request):
        source_ip = _get_client_ip(request)

        try:
            body = request.data if isinstance(request.data, dict) else {}
        except Exception:  # pragma: no cover
            body = {}

        CallbackLog = get_callback_log_model()
        try:
            log = CallbackLog.objects.create(
                callback_type="B2C_RESULT",
                source_ip=source_ip or "0.0.0.0",
                raw_body=body,
            )
            _dispatch(process_b2c_result, log.id)
        except Exception:  # pragma: no cover
            logger.exception("django_mpesa: error logging B2C result callback")

        return Response(ACCEPTED)


class B2CTimeoutView(APIView):
    """Receives B2C timeout callbacks from Safaricom."""

    authentication_classes = []
    permission_classes = []

    def post(self, request):
        source_ip = _get_client_ip(request)

        try:
            body = request.data if isinstance(request.data, dict) else {}
        except Exception:  # pragma: no cover
            body = {}

        CallbackLog = get_callback_log_model()
        try:
            log = CallbackLog.objects.create(
                callback_type="B2C_TIMEOUT",
                source_ip=source_ip or "0.0.0.0",
                raw_body=body,
            )
            _dispatch(process_b2c_timeout, log.id)
        except Exception:  # pragma: no cover
            logger.exception("django_mpesa: error logging B2C timeout callback")

        return Response(ACCEPTED)

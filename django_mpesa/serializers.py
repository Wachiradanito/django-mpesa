"""
DRF serializers for Daraja callback payload validation.

These serializers are used by Celery tasks to parse already-logged
callback payloads — NOT by views for request validation. Views always
log the raw payload first and return 200; tasks then use serializers
to extract fields cleanly from the logged body.

If serializer validation fails (malformed payload), the task logs the
error on CallbackLog.error and does not retry — a malformed payload
will never become valid on retry.
"""

from rest_framework import serializers


# ------------------------------------------------------------------
# STK Push callback
# ------------------------------------------------------------------

class _STKCallbackMetadataItemSerializer(serializers.Serializer):
    Name = serializers.CharField()
    Value = serializers.JSONField(required=False)


class _STKCallbackMetadataSerializer(serializers.Serializer):
    Item = _STKCallbackMetadataItemSerializer(many=True, required=False)


class _STKCallbackBodySerializer(serializers.Serializer):
    MerchantRequestID = serializers.CharField()
    CheckoutRequestID = serializers.CharField()
    ResultCode = serializers.IntegerField()
    ResultDesc = serializers.CharField()
    CallbackMetadata = _STKCallbackMetadataSerializer(required=False)


class _STKBodyWrapperSerializer(serializers.Serializer):
    stkCallback = _STKCallbackBodySerializer()


class STKCallbackSerializer(serializers.Serializer):
    """Validates the full nested structure of an STK Push callback."""
    Body = _STKBodyWrapperSerializer()


# ------------------------------------------------------------------
# C2B confirmation callback
# ------------------------------------------------------------------

class C2BConfirmationSerializer(serializers.Serializer):
    """Validates a C2B confirmation payload."""
    TransactionType = serializers.CharField(required=False, default="")
    TransID = serializers.CharField()
    TransTime = serializers.CharField()
    TransAmount = serializers.CharField()
    BusinessShortCode = serializers.CharField()
    BillRefNumber = serializers.CharField()
    InvoiceNumber = serializers.CharField(required=False, default="")
    OrgAccountBalance = serializers.CharField(required=False, default="")
    ThirdPartyTransID = serializers.CharField(required=False, default="")
    MSISDN = serializers.CharField()
    FirstName = serializers.CharField(required=False, default="")
    MiddleName = serializers.CharField(required=False, default="")
    LastName = serializers.CharField(required=False, default="")


# ------------------------------------------------------------------
# B2C result callback
# ------------------------------------------------------------------

class _B2CResultParameterItemSerializer(serializers.Serializer):
    Key = serializers.CharField()
    Value = serializers.JSONField(required=False)


class _B2CResultParametersSerializer(serializers.Serializer):
    ResultParameter = _B2CResultParameterItemSerializer(many=True, required=False)


class _B2CResultBodySerializer(serializers.Serializer):
    ResultType = serializers.IntegerField()
    ResultCode = serializers.IntegerField()
    ResultDesc = serializers.CharField()
    OriginatorConversationID = serializers.CharField()
    ConversationID = serializers.CharField()
    TransactionID = serializers.CharField()
    ResultParameters = _B2CResultParametersSerializer(required=False)


class B2CResultSerializer(serializers.Serializer):
    """Validates a B2C result payload."""
    Result = _B2CResultBodySerializer()

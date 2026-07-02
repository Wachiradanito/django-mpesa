from django.urls import path

from django_mpesa.views import (
    B2CResultView,
    B2CTimeoutView,
    C2BConfirmationView,
    C2BValidationView,
    STKCallbackView,
)

app_name = "django_mpesa"

urlpatterns = [
    path("stk/callback/", STKCallbackView.as_view(), name="stk-callback"),
    path("c2b/validate/", C2BValidationView.as_view(), name="c2b-validate"),
    path("c2b/confirm/", C2BConfirmationView.as_view(), name="c2b-confirm"),
    path("b2c/result/", B2CResultView.as_view(), name="b2c-result"),
    path("b2c/timeout/", B2CTimeoutView.as_view(), name="b2c-timeout"),
]

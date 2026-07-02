from django.apps import AppConfig


class MpesaConfig(AppConfig):
    name = "django_mpesa"
    default_auto_field = "django.db.models.BigAutoField"
    verbose_name = "M-PESA"

    def ready(self):
        # Importing conf registers the setting_changed signal handler
        # so @override_settings(MPESA=...) works correctly in tests.
        import django_mpesa.conf  # noqa: F401

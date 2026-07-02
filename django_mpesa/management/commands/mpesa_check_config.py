"""
Management command: mpesa_check_config

Validates the MPESA settings dict at deploy time. Run this in CI
and as a deployment health check.

Usage:
    python manage.py mpesa_check_config
    python manage.py mpesa_check_config --fail-fast
"""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Validate MPESA settings and report any configuration problems."

    def add_arguments(self, parser):
        parser.add_argument(
            "--fail-fast",
            action="store_true",
            help="Stop after the first failing check.",
        )

    def handle(self, *args, **options):
        fail_fast = options["fail_fast"]
        checks = list(self._run_checks())

        failures = [c for c in checks if not c["ok"]]

        for check in checks:
            if check["ok"]:
                self.stdout.write(self.style.SUCCESS(f"[OK]   {check['name']}"))
            else:
                self.stdout.write(self.style.ERROR(f"[FAIL] {check['name']}: {check['reason']}"))
                if fail_fast:
                    self.stderr.write("Stopping at first failure (--fail-fast).")
                    raise SystemExit(1)

        if failures:
            self.stderr.write(
                self.style.ERROR(
                    f"\n{len(failures)} check(s) failed. "
                    "Fix the issues above before deploying."
                )
            )
            raise SystemExit(1)
        else:
            self.stdout.write(
                self.style.SUCCESS("\nAll checks passed.")
            )

    def _run_checks(self):
        from django.conf import settings as django_settings
        from django_mpesa.conf import mpesa_settings

        mpesa = getattr(django_settings, "MPESA", None)

        # Check 1: MPESA dict exists
        yield self._check(
            "MPESA settings dict exists",
            mpesa is not None,
            "Add MPESA = {...} to your Django settings.",
        )
        if mpesa is None:
            return

        # Check 2: ENV is valid
        env = mpesa.get("ENV", "sandbox")
        yield self._check(
            "ENV is 'sandbox' or 'production'",
            env in ("sandbox", "production"),
            f"ENV must be 'sandbox' or 'production', got {env!r}.",
        )

        # Check 3 & 4: Credentials resolvable
        for key in ("CONSUMER_KEY", "CONSUMER_SECRET", "SHORTCODE"):
            val = mpesa.get(key)
            resolved = val() if callable(val) else val
            yield self._check(
                f"{key} is set and resolvable",
                bool(resolved),
                f"MPESA[{key!r}] is missing or empty.",
            )

        # Check 5: Callback URLs are HTTPS in production
        callback_url_keys = [
            "STK_CALLBACK_URL", "C2B_VALIDATION_URL", "C2B_CONFIRMATION_URL",
            "B2C_RESULT_URL", "B2C_TIMEOUT_URL",
        ]
        if env == "production":
            for key in callback_url_keys:
                url = mpesa.get(key, "")
                if url:
                    yield self._check(
                        f"{key} uses HTTPS",
                        str(url).startswith("https://"),
                        f"MPESA[{key!r}] must use HTTPS in production, got {url!r}.",
                    )

        # Check 6: Warn if sandbox URLs are localhost
        if env == "sandbox":
            for key in callback_url_keys:
                url = str(mpesa.get(key, ""))
                if any(h in url for h in ("localhost", "127.0.0.1")):
                    self.stdout.write(
                        self.style.WARNING(
                            f"[WARN] {key} points to localhost — "
                            "Safaricom cannot reach this URL."
                        )
                    )

        # Check 7 & 8 & 9: TRANSACTION_MODEL and CALLBACK_LOG_MODEL resolve
        from django.apps import apps
        from django_mpesa.models import AbstractMpesaCallbackLog, AbstractMpesaTransaction

        for setting_key, base_class in [
            ("TRANSACTION_MODEL", AbstractMpesaTransaction),
            ("CALLBACK_LOG_MODEL", AbstractMpesaCallbackLog),
        ]:
            model_string = mpesa.get(setting_key, "")
            try:
                app_label, model_name = model_string.rsplit(".", 1)
                model = apps.get_model(app_label, model_name)
                yield self._check(
                    f"{setting_key} resolves",
                    True,
                    "",
                )
                yield self._check(
                    f"{setting_key} subclasses {base_class.__name__}",
                    issubclass(model, base_class),
                    f"{model_string} must subclass {base_class.__name__}.",
                )
            except Exception as exc:
                yield self._check(
                    f"{setting_key} resolves",
                    False,
                    f"Could not resolve {model_string!r}: {exc}",
                )

        # Check 10: Celery importable if USE_CELERY=True
        use_celery = mpesa.get("USE_CELERY", True)
        if use_celery:
            try:
                import celery  # noqa: F401
                celery_ok = True
            except ImportError:
                celery_ok = False
            yield self._check(
                "Celery is installed (USE_CELERY=True)",
                celery_ok,
                "Install celery: pip install django-mpesa[celery]",
            )

        # Check 11: TOKEN_CACHE_TTL_BUFFER is valid
        buffer = mpesa.get("TOKEN_CACHE_TTL_BUFFER", 60)
        yield self._check(
            "TOKEN_CACHE_TTL_BUFFER is a positive integer < 3600",
            isinstance(buffer, int) and 0 < buffer < 3600,
            f"TOKEN_CACHE_TTL_BUFFER must be an integer between 1 and 3599, got {buffer!r}.",
        )

        # Check 12: PASSKEY is set
        passkey = mpesa.get("PASSKEY")
        resolved_passkey = passkey() if callable(passkey) else passkey
        yield self._check(
            "PASSKEY is set (required for STK Push)",
            bool(resolved_passkey),
            "MPESA['PASSKEY'] is required for STK Push.",
        )

        # Check 13: SECURITY_CREDENTIAL or INITIATOR_PASSWORD set if INITIATOR_NAME set
        initiator = mpesa.get("INITIATOR_NAME")
        if initiator:
            has_cred = bool(
                mpesa.get("SECURITY_CREDENTIAL") or mpesa.get("INITIATOR_PASSWORD")
            )
            yield self._check(
                "SECURITY_CREDENTIAL or INITIATOR_PASSWORD set (required for B2C/Reversal)",
                has_cred,
                "Set MPESA['SECURITY_CREDENTIAL'] when INITIATOR_NAME is configured.",
            )

    @staticmethod
    def _check(name: str, condition: bool, reason: str) -> dict:
        return {"name": name, "ok": bool(condition), "reason": reason}

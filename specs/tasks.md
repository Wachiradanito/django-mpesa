# django-mpesa — Implementation Task Breakdown

**Version:** 1.0
**Date:** 2026-07-02
**Author:** Daniel Maina / Mainfinity
**Status:** Approved for implementation

> Read `specs/requirements.md` for *what* to build. Read `specs/design.md` for *how* it is designed. This document breaks the design into discrete, independently executable tasks with explicit acceptance criteria.

---

## Conventions

### Task ID format
`M{milestone}.{sequence}` — e.g. `M1.02` is the second task in Milestone 1.

### Status labels
- `[ ]` — not started
- `[~]` — in progress
- `[x]` — done

### Acceptance criteria
Every task has a **Done when** section. A task is not complete until every criterion is met. "It runs" is not a criterion — every task must have a test or a verifiable output.

### Dependency notation
`Depends on: M1.01, M1.02` — this task cannot start until those tasks are done.

### File references
All paths are relative to the project root `django-mpesa/`.

---

## Milestone Map

| Milestone | Theme | Release | Tasks |
|---|---|---|---|
| M0 | Project scaffold | — | M0.01–M0.05 |
| M1 | Client layer | — | M1.01–M1.05 |
| M2 | Core Django layer | — | M2.01–M2.06 |
| M3 | STK Push end-to-end | **v0.1.0** | M3.01–M3.07 |
| M4 | C2B | v0.2.0 | M4.01–M4.05 |
| M5 | B2C | v0.2.0 | M5.01–M5.05 |
| M6 | Remaining services + ops | v0.3.0 | M6.01–M6.07 |
| M7 | Full test suite + coverage | v0.3.0 | M7.01–M7.06 |
| M8 | Packaging + docs + release | v0.3.0 | M8.01–M8.06 |

**v0.1.0 shippable gate:** M0 + M1 + M2 + M3 all green, coverage ≥ 90% on those modules, `mpesa_check_config` passes against sandbox settings.

---

---

## Milestone 0 — Project Scaffold

> Goal: a runnable, importable Python package with CI passing before a single line of business logic is written.

---

### M0.01 — Initialise repository structure

**Depends on:** nothing

**Create the following files and directories:**

```
django-mpesa/
├── pyproject.toml
├── LICENSE
├── README.md
├── CHANGELOG.md
├── CONTRIBUTING.md
├── CODE_OF_CONDUCT.md
├── .github/
│   ├── workflows/
│   │   ├── test.yml        (stub — runs `echo ok` for now)
│   │   └── publish.yml     (stub)
│   └── ISSUE_TEMPLATE/
│       ├── bug_report.md
│       └── feature_request.md
├── django_mpesa/
│   └── __init__.py
└── tests/
    ├── conftest.py
    └── settings.py
```

**`pyproject.toml` must contain:**
- `[project]` with `name`, `version = "0.1.0"`, `requires-python = ">=3.10"`, all runtime dependencies, all optional dependency groups (`celery`, `test`, `dev`).
- `[build-system]` using `hatchling`.
- `[tool.pytest.ini_options]` with `DJANGO_SETTINGS_MODULE = "tests.settings"`.
- `[tool.coverage.run]` with `source = ["django_mpesa"]` and `omit = ["django_mpesa/testing/*"]`.
- `[tool.coverage.report]` with `fail_under = 90`.
- `[tool.ruff]` with line length and selected rules.

**`django_mpesa/__init__.py` must:**
- Read `__version__` via `importlib.metadata.version("django-mpesa")` with a `"0.0.0-dev"` fallback.
- Export only `__version__` at the package level.

**`tests/settings.py` must be a minimal valid Django settings module** with SQLite in-memory DB, `INSTALLED_APPS` containing `django.contrib.contenttypes`, `django.contrib.auth`, `django_mpesa`, and `tests.testapp`. Include a placeholder `MPESA = {}` dict.

**`tests/conftest.py`** — empty for now, with a comment `# fixtures imported here in later milestones`.

**Done when:**
- `pip install -e ".[test]"` completes without errors.
- `python -c "import django_mpesa; print(django_mpesa.__version__)"` prints a version string.
- `pytest tests/` exits 0 (no tests yet, but collection must succeed).

---

### M0.02 — Create test app for concrete models

**Depends on:** M0.01

**Create:**
```
tests/
└── testapp/
    ├── __init__.py
    ├── apps.py
    └── models.py
```

**`tests/testapp/models.py`:**
```python
from django_mpesa.models import AbstractMpesaTransaction, AbstractMpesaCallbackLog

class MpesaTransaction(AbstractMpesaTransaction):
    class Meta(AbstractMpesaTransaction.Meta):
        app_label = "testapp"

class MpesaCallbackLog(AbstractMpesaCallbackLog):
    class Meta(AbstractMpesaCallbackLog.Meta):
        app_label = "testapp"
```

**`tests/settings.py` must be updated** to:
- Add `"tests.testapp"` to `INSTALLED_APPS`.
- Set `MPESA["TRANSACTION_MODEL"] = "testapp.MpesaTransaction"`.
- Set `MPESA["CALLBACK_LOG_MODEL"] = "testapp.MpesaCallbackLog"`.

**Done when:**
- `pytest tests/` still exits 0.
- `python -m django migrate --settings=tests.settings` creates the testapp tables without error (once models are defined in M2 — this task just scaffolds the app).

---

### M0.03 — CI test workflow

**Depends on:** M0.01

**Replace the stub `.github/workflows/test.yml`** with the full matrix workflow as designed in `specs/design.md §9.4`:
- Matrix: Python 3.10 / 3.11 / 3.12 × Django 4.2 / 5.0 (6 combinations).
- Steps: checkout, setup-python, install deps, run pytest with coverage, upload to Codecov.
- Coverage threshold: 90% (via `--cov-fail-under=90`).
- `continue-on-error: false` — CI must block on test failures.

**Done when:**
- Workflow YAML is valid (passes `yamllint` or GitHub Actions syntax check).
- A push to a feature branch triggers the workflow and all 6 matrix jobs pass (they will pass trivially since there are no real tests yet, but the workflow infrastructure must be green).

---

### M0.04 — CI publish workflow

**Depends on:** M0.01

**Replace the stub `.github/workflows/publish.yml`** with the full publish workflow:
- Triggered on `push` to tags matching `v*.*.*`.
- Builds with `python -m build`.
- Publishes via `pypa/gh-action-pypi-publish` using `secrets.PYPI_API_TOKEN`.
- Requires manual approval via `environment: pypi`.

**Done when:**
- Workflow YAML is valid.
- No actual publish is triggered (just the workflow definition is correct).

---

### M0.05 — README and CHANGELOG stubs

**Depends on:** M0.01

**`README.md`** must contain:
- Package name, one-line description.
- Badges: PyPI version, CI status, coverage, Python versions, Django versions, License.
- Install snippet: `pip install django-mpesa`.
- Link to the documentation site.
- Link to `CONTRIBUTING.md`.

**`CHANGELOG.md`** must follow [Keep a Changelog](https://keepachangelog.com) format with an `[Unreleased]` section.

**`CONTRIBUTING.md`** must cover:
- Local setup instructions.
- How to run tests.
- The idempotency test requirement: any PR touching `tasks.py` must include or update `tests/test_idempotency.py`.
- PR checklist.

**`CODE_OF_CONDUCT.md`** — Contributor Covenant 2.1 standard text.

**Done when:**
- All four files exist and contain the required sections.
- README badges use correct shield.io URL patterns (even if CI isn't live yet).

---

## Milestone 1 — Client Layer

> Goal: a fully tested HTTP client that authenticates against Daraja and executes retried POST requests. No service logic yet.

---

### M1.01 — `client/http.py` — HTTP session factory

**Depends on:** M0.01

**Create `django_mpesa/client/__init__.py`** (empty).

**Create `django_mpesa/client/http.py`** implementing `get_session() -> requests.Session`:
- Mounts an `HTTPAdapter` with a `urllib3.Retry` configured for transport-level retries only (`status=0`, `connect=2`, `read=2`).
- Sets default `User-Agent` header to `django-mpesa/{__version__}`.
- Sets `Accept: application/json` header.
- Session is `https://` and `http://` mounted.

**Create `tests/test_client/__init__.py`** (empty).

**Create `tests/test_client/test_http.py`** with:
- `test_session_has_user_agent` — asserts `User-Agent` header contains `django-mpesa`.
- `test_session_has_retry_adapter` — asserts the session has an `HTTPAdapter` mounted.
- `test_get_session_returns_new_instance` — asserts two calls return different objects (not a singleton).

**Done when:**
- All three tests pass.
- `get_session()` is importable from `django_mpesa.client.http`.

---

### M1.02 — `exceptions.py` — full exception hierarchy

**Depends on:** M0.01

**Create `django_mpesa/exceptions.py`** with the full hierarchy from `specs/design.md §7.3`:
- `MpesaError(Exception)` base with `__init__(message, result_code=None, result_desc=None)` and `__repr__`.
- `DarajaConfigError`, `DarajaAuthError`, `DarajaValidationError` all inheriting `MpesaError`.
- `DarajaAPIError(MpesaError)` with additional `status_code` and `response_body` attributes.
- `DarajaRateLimitError(DarajaAPIError)`, `DarajaTimeoutError(DarajaAPIError)`.
- `InvalidCallbackError(MpesaError)`.

**Create `tests/test_exceptions.py`** with:
- `test_all_exceptions_inherit_mpesa_error` — asserts `isinstance(DarajaConfigError(), MpesaError)` etc. for every class.
- `test_result_code_accessible` — asserts `e.result_code == 400` when constructed with `result_code=400`.
- `test_daraja_api_error_has_status_code` — asserts `DarajaAPIError(status_code=500).status_code == 500`.
- `test_repr_contains_class_name` — asserts `"DarajaAuthError"` in `repr(DarajaAuthError("fail"))`.

**Done when:**
- All tests pass.
- Every exception class is importable from `django_mpesa.exceptions`.

---

### M1.03 — `client/auth.py` — `TokenManager`

**Depends on:** M1.01, M1.02

**Create `django_mpesa/client/auth.py`** implementing `TokenManager` as designed in `specs/design.md §4.3`:
- `get_token() -> str` — cache-check → lock → fetch → cache → return.
- `_fetch_new_token() -> tuple[str, int]` — Basic Auth GET to OAuth endpoint, returns `(token, expires_in)`.
- `invalidate() -> None` — deletes cache key.
- Cache key: `f"django_mpesa:token:{env}"`.
- Lock key: `f"django_mpesa:token_lock:{env}"`.
- Lock timeout: 10 seconds. Max lock-wait retries: 5 with 0.1s sleep.
- Uses `mpesa_settings` for `ENV`, `CONSUMER_KEY`, `CONSUMER_SECRET`, `TOKEN_CACHE_ALIAS`, `TOKEN_CACHE_TTL_BUFFER`.

**Create `tests/test_client/test_auth.py`** with:
- `test_get_token_fetches_and_caches` — mock HTTP, assert token returned and cached.
- `test_get_token_returns_cached_on_second_call` — assert only one HTTP call made across two `get_token()` calls.
- `test_invalidate_clears_cache` — assert `get_token()` fetches fresh after `invalidate()`.
- `test_fetch_raises_auth_error_on_non_200` — assert `DarajaAuthError` raised when mock returns 401.
- `test_token_ttl_uses_buffer` — assert cached TTL equals `expires_in - TOKEN_CACHE_TTL_BUFFER`.
- `test_stampede_prevention` — two threads call `get_token()` simultaneously; assert exactly one HTTP call is made.

Use the `responses` library to mock HTTP calls without network access.

**Done when:**
- All six tests pass.
- `TokenManager` importable from `django_mpesa.client.auth`.

---

### M1.04 — `client/base.py` — `BaseDarajaClient`

**Depends on:** M1.03

**Create `django_mpesa/client/base.py`** implementing `BaseDarajaClient` as designed in `specs/design.md §4.4`:
- `__init__(token_manager=None, session=None)` — defaults to real `TokenManager()` and `get_session()`.
- `post(path, payload) -> dict` — full decision tree: auth header, debug logging with redaction, 401 re-auth retry, 429 → `DarajaRateLimitError`, 5xx retry with backoff, 4xx → `DarajaAPIError` (no retry), timeout → `DarajaTimeoutError`, 2xx with `errorCode` field → `DarajaAPIError`, success → return dict.
- `_redact(payload)` — replaces values for `SENSITIVE_KEYS` with `"***"`.
- `get_base_url()` — reads `mpesa_settings.ENV`, returns correct base URL.

**Create `tests/test_client/test_base.py`** with:
- `test_successful_post_returns_dict` — mock 200 response, assert dict returned.
- `test_5xx_retries_up_to_max` — mock 500, assert retried `MAX_RETRIES` times then raises `DarajaAPIError`.
- `test_4xx_raises_immediately_no_retry` — mock 400, assert raised immediately, exactly one HTTP call.
- `test_401_invalidates_and_retries_once` — first call returns 401, second returns 200; assert token invalidated and result returned.
- `test_401_twice_raises_auth_error` — both calls return 401; assert `DarajaAuthError` raised.
- `test_429_raises_rate_limit_error`.
- `test_timeout_raises_daraja_timeout_error`.
- `test_sensitive_fields_redacted_in_log` — assert `Password` value does not appear in captured log output.
- `test_2xx_with_error_code_raises_api_error` — mock 200 with `{"errorCode": "400.002.02"}` in body.

**Done when:**
- All nine tests pass.
- `BaseDarajaClient` importable from `django_mpesa.client.base`.

---

### M1.05 — Export client layer public API

**Depends on:** M1.03, M1.04

**Update `django_mpesa/client/__init__.py`** to export:
```python
from django_mpesa.client.auth import TokenManager
from django_mpesa.client.base import BaseDarajaClient
from django_mpesa.client.http import get_session

__all__ = ["TokenManager", "BaseDarajaClient", "get_session"]
```

**Done when:**
- `from django_mpesa.client import BaseDarajaClient, TokenManager` works.
- Existing M1 tests still pass.

---

---

## Milestone 2 — Core Django Layer

> Goal: the `conf.py` settings resolver, abstract models, validators, and `AppConfig` are all in place and tested. No service or callback logic yet — this is the foundation everything else sits on.

---

### M2.01 — `conf.py` — settings resolver

**Depends on:** M1.02

**Create `django_mpesa/conf.py`** implementing `MpesaSettings` as designed in `specs/design.md §2.2`:
- `DEFAULTS` dict with all defaultable keys and their default values, including the full Safaricom IP allowlist.
- `REQUIRED` set: `CONSUMER_KEY`, `CONSUMER_SECRET`, `SHORTCODE`, `TRANSACTION_MODEL`, `CALLBACK_LOG_MODEL`.
- `CALLABLE_SETTINGS` set: all credential keys that support callable resolution.
- `MpesaSettings.__getattr__` — resolves from user settings, falls back to defaults, calls callables, raises `DarajaConfigError` for missing required keys.
- `MpesaSettings.reload()` — clears internal cache, re-reads from `django.conf.settings.MPESA`.
- Module-level `mpesa_settings = MpesaSettings(...)` instance.
- `setting_changed` signal handler that calls `mpesa_settings.reload()` when `setting == "MPESA"`.
- `get_base_url() -> str` function that returns the correct Daraja base URL from `mpesa_settings.ENV`.

**Update `tests/settings.py`** to include a minimal valid `MPESA` dict with all required keys set.

**Create `tests/test_conf.py`** with:
- `test_default_env_is_sandbox` — assert `mpesa_settings.ENV == "sandbox"` when not overridden.
- `test_missing_required_key_raises_config_error` — override settings to remove `CONSUMER_KEY`, assert `DarajaConfigError` raised on access.
- `test_callable_setting_is_resolved` — set `CONSUMER_KEY` to a lambda, assert the resolved string is returned.
- `test_reload_clears_cache` — change setting via `override_settings`, call `reload()`, assert new value visible.
- `test_invalid_attribute_raises_attribute_error` — assert `AttributeError` on `mpesa_settings.NONEXISTENT_KEY`.
- `test_get_base_url_sandbox` — assert returns sandbox URL.
- `test_get_base_url_production` — override `ENV="production"`, assert returns production URL.

**Done when:**
- All seven tests pass.
- `from django_mpesa.conf import mpesa_settings` works.

---

### M2.02 — `validators.py` — input validators

**Depends on:** M1.02

**Create `django_mpesa/validators.py`** implementing all five validators from `specs/requirements.md §7`:

- `validate_phone_number(value: str) -> str` — normalise to `2547XXXXXXXX`, raise `DarajaValidationError` on bad input.
- `validate_amount(value) -> Decimal` — convert to `Decimal` via `str()` path, raise on zero/negative/> 2dp.
- `validate_account_reference(value: str) -> str` — strip, raise on empty or > 12 chars.
- `validate_transaction_desc(value: str) -> str` — strip, raise on empty or > 13 chars.
- `validate_command_id(value: str) -> str` — must be one of `BusinessPayment`, `SalaryPayment`, `PromotionPayment`.

**Create `tests/test_validators.py`** with:
- Phone: `test_254_format_passthrough`, `test_07_format_normalised`, `test_7_format_normalised`, `test_plus_prefix_stripped`, `test_invalid_phone_raises`.
- Amount: `test_int_converted_to_decimal`, `test_float_converted_safely`, `test_decimal_passthrough`, `test_zero_raises`, `test_negative_raises`, `test_string_raises`.
- Account reference: `test_valid_reference`, `test_too_long_raises`, `test_empty_raises`.
- Transaction desc: `test_valid_desc`, `test_too_long_raises_desc`.
- Command ID: `test_valid_command_ids`, `test_invalid_command_id_raises`.

**Done when:**
- All tests pass.
- All five validators importable from `django_mpesa.validators`.

---

### M2.03 — `models.py` — abstract base models

**Depends on:** M2.01

**Create `django_mpesa/models.py`** implementing:
- `TRANSACTION_TYPE_CHOICES`, `STATUS_CHOICES`, `TERMINAL_STATES` constants.
- `CALLBACK_TYPE_CHOICES` constant.
- `AbstractMpesaTransaction` — all fields from `specs/requirements.md §5.2`, `Meta: abstract=True, ordering=["-initiated_at"]`, indexes from `specs/design.md §3.6`, `__str__`.
- `AbstractMpesaCallbackLog` — all fields from `specs/requirements.md §5.3`, `Meta: abstract=True, ordering=["-received_at"]`, `__str__`.
- `get_transaction_model()` helper function using `apps.get_model()`.
- `get_callback_log_model()` helper function.

**Run initial migration** for the test app:
```
python -m django makemigrations testapp --settings=tests.settings
```
Commit the generated migration file at `tests/testapp/migrations/0001_initial.py`.

**Create `tests/test_models/test_abstract_models.py`** with:
- `test_transaction_str` — assert `__str__` returns expected format.
- `test_callback_log_str`.
- `test_terminal_states_set_contains_expected_values`.
- `test_get_transaction_model_returns_correct_class` — assert return value is `testapp.MpesaTransaction`.
- `test_transaction_amount_is_decimal_field` — assert `amount` field is a `DecimalField`.
- `test_checkout_request_id_is_unique` — assert field has `unique=True`.
- `test_transaction_default_status_is_pending` — create an instance without setting `status`, assert `"PENDING"`.

**Done when:**
- All tests pass.
- `python -m django migrate --settings=tests.settings` creates all tables without error.
- `AbstractMpesaTransaction` and `AbstractMpesaCallbackLog` importable from `django_mpesa.models`.

---

### M2.04 — `apps.py` — `MpesaConfig`

**Depends on:** M2.01

**Create `django_mpesa/apps.py`**:
```python
from django.apps import AppConfig

class MpesaConfig(AppConfig):
    name = "django_mpesa"
    default_auto_field = "django.db.models.BigAutoField"
    verbose_name = "M-PESA"

    def ready(self):
        import django_mpesa.conf  # noqa: F401 — registers setting_changed handler
```

**Update `django_mpesa/__init__.py`** to set `default_app_config = "django_mpesa.apps.MpesaConfig"` (required for Django 4.2 compatibility; Django 5.0 uses `AppConfig` auto-discovery).

**Done when:**
- `python -m django check --settings=tests.settings` passes with no errors.
- `MpesaConfig` importable from `django_mpesa.apps`.

---

### M2.05 — `signals.py` — signal definitions

**Depends on:** M0.01

**Create `django_mpesa/signals.py`** with all seven signals:
```python
payment_confirmed, payment_failed, c2b_validation_received,
payout_completed, payout_failed, reversal_completed, balance_received
```

Each is a `django.dispatch.Signal()` instance. Include a module-level docstring listing each signal and its kwargs.

**Create `tests/test_signals.py`** with:
- `test_all_signals_are_signal_instances` — assert each is a `Signal` instance.
- `test_payment_confirmed_fires_with_transaction` — connect a receiver, manually send the signal, assert receiver called with `transaction` kwarg.
- `test_payment_failed_fires_with_result_code` — same pattern with `result_code` and `result_desc` kwargs.

**Done when:**
- All tests pass.
- All signals importable from `django_mpesa.signals`.

---

### M2.06 — `serializers.py` — callback payload serializers

**Depends on:** M2.01

**Create `django_mpesa/serializers.py`** with:
- `STKCallbackSerializer` — validates the full nested STK Push callback structure.
- `C2BConfirmationSerializer` — validates C2B confirmation payload fields.
- `B2CResultSerializer` — validates B2C result payload structure.

**Create `tests/test_serializers.py`** with:
- `test_stk_success_payload_valid` — assert a well-formed STK success payload passes validation.
- `test_stk_missing_checkout_id_invalid` — assert validation fails when `CheckoutRequestID` absent.
- `test_c2b_confirmation_payload_valid`.
- `test_b2c_result_payload_valid`.
- `test_b2c_result_missing_conversation_id_invalid`.

**Done when:**
- All tests pass.
- All serializers importable from `django_mpesa.serializers`.

---

---

## Milestone 3 — STK Push End-to-End *(v0.1.0 gate)*

> Goal: a host app can call `STKPushService.initiate()`, receive the callback, and have the `payment_confirmed` signal fire — all idempotently. This milestone alone is shippable as v0.1.0.

---

### M3.01 — `services/stk_push.py` — `STKPushService.initiate()`

**Depends on:** M1.04, M2.02, M2.03

**Create `django_mpesa/services/__init__.py`** (empty).

**Create `django_mpesa/services/stk_push.py`** implementing `STKPushService`:
- `__init__(self, client=None)` — injectable client.
- `_build_password(shortcode, passkey) -> tuple[str, str]` — returns `(base64_password, timestamp)` using Africa/Nairobi timezone.
- `initiate(phone_number, amount, account_reference, transaction_desc) -> Transaction`:
  1. Validate all four inputs via validators.
  2. Build password and timestamp.
  3. Build payload (see `specs/requirements.md §9.1`).
  4. `Amount` cast to `int`.
  5. POST to `/mpesa/stkpush/v1/processrequest`.
  6. On success: create and return `PENDING` transaction.
  7. On failure: raise `DarajaAPIError` — no transaction created.
- `query(checkout_request_id) -> dict`:
  1. Build payload with shortcode, password, timestamp, and `CheckoutRequestID`.
  2. POST to `/mpesa/stkpushquery/v1/query`.
  3. Return raw dict. No DB mutation.

**Create `tests/test_services/__init__.py`** (empty).

**Create `tests/test_services/test_stk_push.py`** with:
- `test_initiate_creates_pending_transaction(mock_daraja)` — assert transaction created with `status="PENDING"` and `checkout_request_id` from mock response.
- `test_initiate_stores_merchant_request_id(mock_daraja)`.
- `test_initiate_normalises_07_phone(mock_daraja)` — pass `"0712345678"`, assert stored as `"254712345678"`.
- `test_initiate_invalid_reference_too_long_raises_before_network` — assert `DarajaValidationError` and `mock_daraja.calls == []`.
- `test_initiate_invalid_desc_too_long_raises_before_network`.
- `test_initiate_negative_amount_raises_before_network`.
- `test_initiate_api_failure_does_not_create_transaction(mock_daraja)` — configure mock to raise `DarajaAPIError`, assert no DB row created.
- `test_query_returns_dict_without_db_mutation(mock_daraja)` — assert dict returned and no transaction fields changed.
- `test_amount_sent_as_integer(mock_daraja)` — assert the captured payload has `"Amount": 100` not `"Amount": "100.00"`.

**Done when:**
- All nine tests pass.
- `STKPushService` importable from `django_mpesa.services.stk_push`.

---

### M3.02 — `views.py` — `STKCallbackView`

**Depends on:** M2.03, M2.05

**Create `django_mpesa/views.py`** with `STKCallbackView(APIView)`:
- `authentication_classes = []`, `permission_classes = []`.
- `post(request)`:
  1. Resolve source IP via `_get_client_ip(request)`.
  2. Get `request.data` (DRF parsed JSON); default to `{}` on error.
  3. Create `CallbackLog(callback_type="STK", source_ip=ip, raw_body=body)` and save.
  4. Dispatch `process_stk_callback` (sync, since `USE_CELERY=False` in test settings); wrapped in `try/except` so broker failures never cause non-200.
  5. Return `Response({"ResultCode": 0, "ResultDesc": "Accepted"})` — always.
- `_get_client_ip(request) -> str` helper.

**Create `django_mpesa/urls.py`** with all five URL patterns (only `stk/callback/` wired to a real view for now; others point to a `501_not_implemented` placeholder view):
```python
app_name = "django_mpesa"
urlpatterns = [
    path("stk/callback/", STKCallbackView.as_view(), name="stk-callback"),
    # C2B and B2C views added in M4 and M5
]
```

**Create `tests/test_callbacks/__init__.py`** (empty).

**Create `tests/test_callbacks/test_stk_callback.py`** with:
- `test_callback_view_always_returns_200` — POST a valid callback, assert 200.
- `test_callback_view_returns_200_on_malformed_payload` — POST `"not json"`, assert 200.
- `test_callback_view_logs_raw_payload` — assert a `CallbackLog` row is created with the correct `raw_body`.
- `test_callback_view_logs_source_ip` — assert `source_ip` is recorded on the log.

Use DRF's `APIClient` for all view tests.

**Done when:**
- All four tests pass.
- `STKCallbackView` importable from `django_mpesa.views`.

---

### M3.03 — `tasks.py` — `process_stk_callback`

**Depends on:** M3.02

**Create `django_mpesa/tasks.py`** with `process_stk_callback` as designed in `specs/design.md §6.5`:
- Decorated with `@shared_task(bind=True, ...)` — parameters from `mpesa_settings`.
- Full implementation: load log → parse payload → `select_for_update()` → terminal state check → settle → link log → fire signal outside lock.
- On `Transaction.DoesNotExist`: log warning, set `log.error`, return (no retry).
- On unexpected exception: `self.retry(exc=exc)`.

**Update `tests/test_callbacks/test_stk_callback.py`** adding:
- `test_success_callback_moves_transaction_to_success(pending_stk_transaction, stk_success_callback)` — create a `CallbackLog` with the success payload, call `process_stk_callback(log_id)`, assert `txn.status == "SUCCESS"` and `txn.mpesa_receipt_number == "NLJ7RT61SV"`.
- `test_success_callback_sets_settled_at`.
- `test_failure_callback_moves_transaction_to_failed(pending_stk_transaction, stk_failure_callback)`.
- `test_payment_confirmed_signal_fires_on_success` — use a mock receiver, assert fired exactly once with correct `transaction`.
- `test_payment_failed_signal_fires_on_failure`.
- `test_duplicate_callback_is_noop(pending_stk_transaction, stk_success_callback)` — process same callback twice, assert `settled_at` not overwritten and signal fires only once.
- `test_unknown_checkout_id_logs_error_and_does_not_raise` — assert `CallbackLog.error` is set, no exception raised.

**Done when:**
- All new tests pass alongside existing M3.02 tests.
- `process_stk_callback` importable from `django_mpesa.tasks`.

---

### M3.04 — Idempotency concurrency test

**Depends on:** M3.03

**Create `tests/test_idempotency.py`** with the full concurrency test from `specs/design.md §8.4`:
- Uses `threading.Barrier(2)` to force simultaneous entry.
- Marked `@pytest.mark.django_db(transaction=True)`.
- Asserts: no exceptions, `txn.status == "SUCCESS"`, `settled_at` set once, signal fired exactly once.

This test must be run as a separate pytest step (it uses `transaction=True` which is slower and incompatible with the default test runner's transaction rollback strategy).

**Done when:**
- Test passes consistently across at least 5 sequential runs (concurrency tests can be flaky — run with `pytest --count=5` via `pytest-repeat` or equivalent).
- Test fails immediately if `select_for_update()` is removed from the task (verified manually once, then reverted).

---

### M3.05 — `middleware.py` — IP allowlist middleware

**Depends on:** M2.01

**Create `django_mpesa/middleware.py`** implementing `MpesaCallbackIPAllowlistMiddleware` as designed in `specs/design.md §7.1`:
- Passthrough for non-callback paths (zero overhead).
- Passthrough when `VERIFY_CALLBACK_SOURCE_IP=False`.
- IP resolution: direct `REMOTE_ADDR` or `X-Forwarded-For` depending on `TRUST_FORWARDED_FOR`.
- 403 for IPs not in allowlist, with WARNING log.

**Create `tests/test_middleware.py`** with:
- `test_non_callback_path_not_checked` — request to `/` with non-Safaricom IP passes through.
- `test_safaricom_ip_allowed` — request to `/mpesa/stk/callback/` from `196.201.214.200` passes.
- `test_non_safaricom_ip_blocked` — request from `1.2.3.4` returns 403.
- `test_verify_disabled_allows_any_ip` — `VERIFY_CALLBACK_SOURCE_IP=False`, assert any IP passes.
- `test_x_forwarded_for_trusted` — `TRUST_FORWARDED_FOR=True`, assert leftmost non-proxy IP used.

**Done when:**
- All five tests pass.
- Middleware importable from `django_mpesa.middleware`.

---

### M3.06 — `management/commands/mpesa_check_config.py`

**Depends on:** M2.01, M2.03

**Create `django_mpesa/management/__init__.py`** and `django_mpesa/management/commands/__init__.py`** (both empty).

**Create `django_mpesa/management/commands/mpesa_check_config.py`** implementing all 13 checks from `specs/requirements.md §14.1`:
- Prints `[OK] <check name>` or `[FAIL] <check name>: <reason>` per check.
- Accepts `--fail-fast` flag.
- Exits with code `1` if any check fails, `0` if all pass.

**Create `tests/test_management/test_check_config.py`** with:
- `test_all_checks_pass_with_valid_settings` — run command against test settings, assert exit code 0.
- `test_fails_on_missing_consumer_key` — remove `CONSUMER_KEY` from settings, assert exit code 1 and `[FAIL]` in output.
- `test_fails_on_http_callback_url_in_production` — set `ENV="production"` and an `http://` callback URL, assert fail.
- `test_warns_on_localhost_callback_in_sandbox` — set callback to `http://localhost/...`, assert warning in output.
- `test_fail_fast_stops_at_first_failure` — multiple broken settings, assert only one `[FAIL]` line when `--fail-fast` used.

**Done when:**
- All five tests pass.
- `python -m django mpesa_check_config --settings=tests.settings` exits 0.

---

### M3.07 — v0.1.0 integration smoke test

**Depends on:** M3.01–M3.06

**Create `tests/test_integration/test_stk_push_e2e.py`** with a single end-to-end scenario test:

```
1. Call STKPushService.initiate() with mock_daraja → assert PENDING transaction created
2. Simulate STK success callback via test client POST to /mpesa/stk/callback/
3. Assert view returns 200
4. Assert transaction status is SUCCESS
5. Assert payment_confirmed signal fired
6. Assert CallbackLog row exists and processed=True
7. Re-POST same callback → assert still SUCCESS (idempotency), signal not fired twice
```

This is a black-box test over the full stack — HTTP in, DB out, signal out.

**Done when:**
- Test passes.
- `pytest tests/ --cov=django_mpesa --cov-fail-under=90` passes for all M0–M3 modules.
- `python -m django mpesa_check_config --settings=tests.settings` exits 0.
- **v0.1.0 is shippable at this point.**

---

---

## Milestone 4 — C2B Service + Callbacks

> Goal: host apps can register C2B URLs, receive paybill payments, validate them before acceptance, and have them settled idempotently.

---

### M4.01 — `services/c2b.py` — `C2BService`

**Depends on:** M1.04, M2.02, M2.03

**Create `django_mpesa/services/c2b.py`** implementing `C2BService`:
- `register_urls(response_type="Completed") -> dict`:
  - Validate `response_type` is `"Completed"` or `"Cancelled"`.
  - POST to `/mpesa/c2b/v1/registerurl` with shortcode, response type, validation URL, confirmation URL from settings.
  - Return raw response dict.
- `simulate(phone_number, amount, bill_ref) -> dict`:
  - Raise `DarajaConfigError` immediately if `ENV == "production"`.
  - Validate phone and amount.
  - POST to `/mpesa/c2b/v1/simulate`.
  - Return raw response dict.

**Create `tests/test_services/test_c2b.py`** with:
- `test_register_urls_posts_correct_payload(mock_daraja)` — assert payload contains shortcode, both URL settings, and `ResponseType`.
- `test_register_urls_invalid_response_type_raises`.
- `test_simulate_raises_in_production` — `@override_settings(MPESA={..., "ENV": "production"})`, assert `DarajaConfigError`.
- `test_simulate_succeeds_in_sandbox(mock_daraja)`.
- `test_simulate_validates_phone_before_network(mock_daraja)` — bad phone, assert `DarajaValidationError` and no HTTP call.

**Done when:**
- All five tests pass.
- `C2BService` importable from `django_mpesa.services.c2b`.

---

### M4.02 — `views.py` — `C2BValidationView` and `C2BConfirmationView`

**Depends on:** M2.03, M2.05, M4.01

**Add to `django_mpesa/views.py`**:

`C2BValidationView(APIView)`:
- Log raw payload to `CallbackLog(callback_type="C2B_VALIDATION")`.
- Fire `c2b_validation_received` signal with `raw_payload=body`.
- Collect return values from receivers; if any returns a dict with `"ResultCode"`, return that response.
- Default: return `{"ResultCode": 0, "ResultDesc": "Accepted"}`.

`C2BConfirmationView(APIView)`:
- Log raw payload to `CallbackLog(callback_type="C2B_CONFIRMATION")`.
- Dispatch `process_c2b_confirmation(log_id)` (sync or async).
- Always return `{"ResultCode": 0, "ResultDesc": "Accepted"}`.

**Update `django_mpesa/urls.py`** to wire both views.

**Create `tests/test_callbacks/test_c2b_callbacks.py`** with:
- `test_validation_view_fires_signal` — assert `c2b_validation_received` fires with correct `raw_payload`.
- `test_validation_view_default_accepts` — no receiver connected, assert `ResultCode: 0` returned.
- `test_validation_view_receiver_can_reject` — connect receiver returning `{"ResultCode": "C2B00012", ...}`, assert response body contains that code.
- `test_confirmation_view_always_returns_200` — even with broken task dispatch.
- `test_confirmation_view_logs_raw_payload` — assert `CallbackLog` row created.

**Done when:**
- All five tests pass.
- Both views importable and URLs registered.

---

### M4.03 — `tasks.py` — `process_c2b_confirmation`

**Depends on:** M4.02

**Add `process_c2b_confirmation` to `django_mpesa/tasks.py`**:
- Load `CallbackLog`.
- Parse: `TransID` → `mpesa_receipt_number`, `TransAmount` → `amount`, `MSISDN` → `phone_number`, `BillRefNumber` → `account_reference`.
- `with transaction.atomic()`:
  - `get_or_create` pattern: look for existing `PENDING` transaction by `account_reference`; if not found, create new `SUCCESS` row directly.
  - If found and already terminal: no-op.
  - Set `status="SUCCESS"`, `mpesa_receipt_number`, `settled_at`, `raw_callback_payload`.
  - Link log to transaction, mark `processed=True`.
- Outside lock: fire `payment_confirmed`.

**Update `tests/test_callbacks/test_c2b_callbacks.py`** adding:
- `test_confirmation_creates_new_transaction_if_none_exists(c2b_confirmation_payload)`.
- `test_confirmation_updates_existing_pending_transaction(c2b_confirmation_payload)`.
- `test_confirmation_is_noop_for_already_settled_transaction(c2b_confirmation_payload)` — idempotency check.
- `test_payment_confirmed_fires_on_c2b_confirmation`.

**Done when:**
- All four new tests pass alongside existing M4.02 tests.

---

### M4.04 — C2B idempotency test

**Depends on:** M4.03

**Add to `tests/test_idempotency.py`** a second concurrency test:
- `test_duplicate_c2b_confirmation_settles_exactly_once` — same structure as the STK test: two threads, `Barrier(2)`, assert signal fires once and status set once.

**Done when:**
- New test passes consistently across 5 runs.

---

### M4.05 — C2B integration smoke test

**Depends on:** M4.01–M4.04

**Create `tests/test_integration/test_c2b_e2e.py`** with:
1. POST a validation callback → assert 200 and accepted.
2. POST a rejection via signal receiver → assert `ResultCode != 0` returned.
3. POST a confirmation callback → assert transaction created with `SUCCESS` and signal fired.
4. Re-POST confirmation → assert still `SUCCESS`, signal not fired twice.

**Done when:**
- Test passes.
- Coverage on `services/c2b.py`, `views.py` (C2B views), `tasks.py` (C2B task) ≥ 90%.

---

## Milestone 5 — B2C Service + Callbacks

> Goal: host apps can initiate B2C payouts and receive result/timeout callbacks idempotently.

---

### M5.01 — `services/b2c.py` — `B2CService`

**Depends on:** M1.04, M2.02, M2.03

**Create `django_mpesa/services/b2c.py`** implementing `B2CService.send_payment()` as designed in `specs/requirements.md §9.3`:
- Validate all inputs including `validate_command_id()`.
- Build payload with `SecurityCredential` from settings.
- POST to `/mpesa/b2c/v1/paymentrequest`.
- Create `PENDING` transaction storing `conversation_id` and `originator_conversation_id`.
- Return transaction. Terminal status is NOT set here.

**Create `tests/test_services/test_b2c.py`** with:
- `test_send_payment_creates_pending_transaction(mock_daraja)`.
- `test_send_payment_stores_conversation_id(mock_daraja)`.
- `test_send_payment_invalid_command_id_raises_before_network(mock_daraja)`.
- `test_send_payment_does_not_set_terminal_status(mock_daraja)` — assert `status == "PENDING"` after `send_payment()`.
- `test_send_payment_invalid_phone_raises_before_network(mock_daraja)`.
- `test_send_payment_api_failure_does_not_create_transaction(mock_daraja)`.

**Done when:**
- All six tests pass.
- `B2CService` importable from `django_mpesa.services.b2c`.

---

### M5.02 — `views.py` — `B2CResultView` and `B2CTimeoutView`

**Depends on:** M2.03, M2.05

**Add to `django_mpesa/views.py`**:

`B2CResultView(APIView)`:
- Log to `CallbackLog(callback_type="B2C_RESULT")`.
- Dispatch `process_b2c_result(log_id)`.
- Always return `{"ResultCode": 0, "ResultDesc": "Accepted"}`.

`B2CTimeoutView(APIView)`:
- Log to `CallbackLog(callback_type="B2C_TIMEOUT")`.
- Dispatch `process_b2c_timeout(log_id)`.
- Always return `{"ResultCode": 0, "ResultDesc": "Accepted"}`.

**Update `django_mpesa/urls.py`** to wire both views.

**Create `tests/test_callbacks/test_b2c_callbacks.py`** with:
- `test_result_view_always_returns_200`.
- `test_result_view_logs_payload`.
- `test_timeout_view_always_returns_200`.
- `test_timeout_view_logs_payload`.

**Done when:**
- All four tests pass.

---

### M5.03 — `tasks.py` — `process_b2c_result` and `process_b2c_timeout`

**Depends on:** M5.02

**Add to `django_mpesa/tasks.py`**:

`process_b2c_result(callback_log_id)`:
- Load log, parse `ConversationID`, `ResultCode`, `ResultDesc`, `TransactionReceipt` (from `ResultParameters` on success).
- `select_for_update()` on transaction by `conversation_id`.
- Terminal state check.
- Set `status="SUCCESS"` or `"FAILED"`, `settled_at`, `mpesa_receipt_number` (if success).
- Outside lock: fire `payout_completed` or `payout_failed`.

`process_b2c_timeout(callback_log_id)`:
- Parse `ConversationID`.
- `select_for_update()`.
- Terminal state check.
- Set `status="TIMEOUT"`, `settled_at`.
- Outside lock: fire `payout_failed(result_code=None, result_desc="Timeout")`.

**Update `tests/test_callbacks/test_b2c_callbacks.py`** adding:
- `test_b2c_success_result_moves_to_success(pending_b2c_transaction, b2c_result_success_payload)`.
- `test_b2c_success_sets_receipt_number`.
- `test_b2c_failure_result_moves_to_failed(pending_b2c_transaction, b2c_result_failure_payload)`.
- `test_payout_completed_signal_fires_on_success`.
- `test_payout_failed_signal_fires_on_failure`.
- `test_b2c_timeout_moves_to_timeout(pending_b2c_transaction, b2c_timeout_payload)`.
- `test_payout_failed_signal_fires_on_timeout`.
- `test_duplicate_b2c_result_is_noop` — idempotency check.

**Done when:**
- All eight new tests pass.

---

### M5.04 — B2C idempotency test

**Depends on:** M5.03

**Add to `tests/test_idempotency.py`**:
- `test_duplicate_b2c_result_settles_exactly_once` — two concurrent threads processing the same B2C result callback, assert settled once and `payout_completed` fires once.

**Done when:**
- New test passes consistently across 5 runs.

---

### M5.05 — B2C integration smoke test

**Depends on:** M5.01–M5.04

**Create `tests/test_integration/test_b2c_e2e.py`** with:
1. `send_payment()` with mock → `PENDING` transaction.
2. POST success result callback → `SUCCESS`, `payout_completed` fires.
3. POST same result again → still `SUCCESS`, signal not fired twice.
4. Separate test: `send_payment()` → POST timeout callback → `TIMEOUT`, `payout_failed` fires.

**Done when:**
- All scenarios pass.
- Coverage on `services/b2c.py` and B2C tasks ≥ 90%.

---

---

## Milestone 6 — Remaining Services, Admin, Management Command

> Goal: Transaction Status, Account Balance, and Reversal services; admin mixins; and the full `mpesa_check_config` command are production-ready.

---

### M6.01 — `services/transaction_status.py` — `TransactionStatusService`

**Depends on:** M1.04, M2.02

**Create `django_mpesa/services/transaction_status.py`** implementing `TransactionStatusService.query()` as specified in `specs/requirements.md §9.4`:
- Validate `identifier_type` is `"1"`, `"2"`, or `"4"`.
- Build full payload with initiator, security credential, `TransactionStatusQuery` command ID.
- POST to `/mpesa/transactionstatus/v1/query`.
- Return raw dict. Must not mutate any DB row.

**Create `tests/test_services/test_transaction_status.py`** with:
- `test_query_returns_raw_dict(mock_daraja)`.
- `test_query_does_not_mutate_db(mock_daraja, pending_stk_transaction)` — assert no DB changes after call.
- `test_invalid_identifier_type_raises`.
- `test_payload_contains_correct_command_id(mock_daraja)` — assert `"TransactionStatusQuery"` in captured payload.

**Done when:**
- All four tests pass.
- `TransactionStatusService` importable from `django_mpesa.services.transaction_status`.

---

### M6.02 — `services/account_balance.py` — `AccountBalanceService`

**Depends on:** M1.04, M2.02

**Create `django_mpesa/services/account_balance.py`** implementing `AccountBalanceService.query()` as specified in `specs/requirements.md §9.5`:
- Validate `identifier_type`.
- Build payload with `AccountBalance` command ID.
- POST to `/mpesa/accountbalance/v1/query`.
- Return acknowledgement dict.

**Create `tests/test_services/test_account_balance.py`** with:
- `test_query_returns_dict(mock_daraja)`.
- `test_invalid_identifier_type_raises`.
- `test_payload_contains_account_balance_command_id(mock_daraja)`.

**Done when:**
- All three tests pass.

---

### M6.03 — `services/reversal.py` — `ReversalService`

**Depends on:** M1.04, M2.02

**Create `django_mpesa/services/reversal.py`** implementing `ReversalService.reverse()` as specified in `specs/requirements.md §9.6`:
- Validate `amount` and `remarks`.
- Build payload with `TransactionReversal` command ID.
- POST to `/mpesa/reversal/v1/request`.
- Return raw acknowledgement dict.
- **Must not** set any transaction status here — status changes only via callback.

**Create `tests/test_services/test_reversal.py`** with:
- `test_reverse_returns_dict(mock_daraja)`.
- `test_reverse_does_not_mutate_transaction(mock_daraja, pending_stk_transaction)`.
- `test_payload_contains_transaction_reversal_command_id(mock_daraja)`.
- `test_invalid_amount_raises_before_network(mock_daraja)`.

**Done when:**
- All four tests pass.

---

### M6.04 — `admin.py` — admin mixins

**Depends on:** M2.03

**Create `django_mpesa/admin.py`** implementing `MpesaTransactionAdminMixin` and `MpesaCallbackLogAdminMixin` as designed in `specs/design.md §7.6`:

`MpesaTransactionAdminMixin`:
- `list_display` with `status_badge` coloured column using `format_html`.
- `list_filter`, `search_fields`, `readonly_fields` (all fields), `ordering`, `date_hierarchy`.

`MpesaCallbackLogAdminMixin`:
- `list_display`, `list_filter`, `readonly_fields` (all fields).

Neither mixin auto-registers anything — host apps must explicitly `@admin.register`.

**Create `tests/test_admin.py`** with:
- `test_transaction_mixin_has_correct_list_display`.
- `test_transaction_mixin_all_fields_readonly` — assert `readonly_fields` includes every field from `AbstractMpesaTransaction`.
- `test_callback_log_mixin_has_correct_list_display`.
- `test_no_auto_registration` — assert `admin.site._registry` does not contain the test model after importing `django_mpesa.admin`.

**Done when:**
- All four tests pass.
- Both mixins importable from `django_mpesa.admin`.

---

### M6.05 — Full `mpesa_check_config` implementation

**Depends on:** M3.06 (existing stub), M2.03

This task upgrades the command stub from M3.06 into the complete implementation covering all 13 checks from `specs/requirements.md §14.1`.

**Additional checks to implement beyond M3.06:**
- Check 7: `TRANSACTION_MODEL` and `CALLBACK_LOG_MODEL` resolve via `apps.get_model()`.
- Check 8: resolved `TRANSACTION_MODEL` is a subclass of `AbstractMpesaTransaction`.
- Check 9: resolved `CALLBACK_LOG_MODEL` is a subclass of `AbstractMpesaCallbackLog`.
- Check 10: if `USE_CELERY=True`, Celery is importable.
- Check 11: `TOKEN_CACHE_TTL_BUFFER` is a positive integer < 3600.
- Check 13: if `INITIATOR_NAME` is set, at least one of `SECURITY_CREDENTIAL` or `INITIATOR_PASSWORD` is also set.

**Update `tests/test_management/test_check_config.py`** with additional tests for each new check.

**Done when:**
- All 13 checks are implemented and tested.
- `python -m django mpesa_check_config --settings=tests.settings` exits 0 and prints 13 `[OK]` lines.

---

### M6.06 — Services `__init__.py` public API

**Depends on:** M6.01, M6.02, M6.03

**Update `django_mpesa/services/__init__.py`** to export all six service classes:
```python
from django_mpesa.services.stk_push import STKPushService
from django_mpesa.services.c2b import C2BService
from django_mpesa.services.b2c import B2CService
from django_mpesa.services.transaction_status import TransactionStatusService
from django_mpesa.services.account_balance import AccountBalanceService
from django_mpesa.services.reversal import ReversalService

__all__ = [
    "STKPushService", "C2BService", "B2CService",
    "TransactionStatusService", "AccountBalanceService", "ReversalService",
]
```

**Done when:**
- `from django_mpesa.services import STKPushService` works.
- All existing service tests still pass.

---

### M6.07 — Reversal callback handling

**Depends on:** M6.03, M3.03

**Note:** Daraja's reversal result arrives on the same `B2C_RESULT_URL` endpoint. The result payload includes a `CommandID` of `TransactionReversal`. The existing `process_b2c_result` task must be updated to handle this case:
- If `CommandID == "TransactionReversal"`: look up the original transaction by `TransactionID` in the `ResultParameters`, set `status="REVERSED"`, fire `reversal_completed` signal.
- If `CommandID` is a B2C command: existing B2C result logic applies.

**Update `tests/test_callbacks/test_b2c_callbacks.py`** adding:
- `test_reversal_result_moves_transaction_to_reversed`.
- `test_reversal_completed_signal_fires`.
- `test_reversal_is_idempotent` — process same reversal result twice, assert `status="REVERSED"` and signal fires once.

**Done when:**
- All three new tests pass.
- `reversal_completed` signal fires correctly and is importable from `django_mpesa.signals`.

---

---

## Milestone 7 — Testing Module + Full Test Suite

> Goal: `django_mpesa/testing/` ships as a first-class tool for host-app test authors, the full library test suite is complete, and coverage is ≥ 90%.

---

### M7.01 — `testing/mock_client.py` — `MockDarajaClient`

**Depends on:** M1.04

**Create `django_mpesa/testing/__init__.py`** (empty).

**Create `django_mpesa/testing/mock_client.py`** with the full `MockDarajaClient` implementation from `specs/design.md §8.2`:
- `__init__(responses=None, raise_on=None)` — dict of path → response or exception.
- `_DEFAULT_RESPONSES` — all eight Daraja paths with realistic success payloads.
- `post(path, payload) -> dict` — lookup table + call recording.
- `set_response(path, response)`, `set_raise(path, exception)`, `reset()`.
- `calls` property.
- `assert_called_once_with_path(path)` assertion helper.

**Create `tests/test_testing/test_mock_client.py`** with:
- `test_returns_default_stk_response`.
- `test_custom_response_overrides_default`.
- `test_raise_on_path_raises_exception`.
- `test_calls_recorded` — assert `len(mock.calls) == 2` after two `post()` calls.
- `test_reset_clears_calls_and_custom_responses`.
- `test_unknown_path_raises_api_error` — path not in defaults or custom, assert `DarajaAPIError`.
- `test_assert_called_once_passes_when_called_once`.
- `test_assert_called_once_fails_when_called_twice` — assert `AssertionError` raised.

**Done when:**
- All eight tests pass.
- `MockDarajaClient` importable from `django_mpesa.testing`.

---

### M7.02 — `testing/factories.py` — factory_boy factories

**Depends on:** M2.03, M7.01

**Create `django_mpesa/testing/factories.py`** with `MpesaTransactionFactory` and `MpesaCallbackLogFactory` as designed in `specs/design.md §8.3`:
- Both factories use `factory.django.DjangoModelFactory`.
- `MpesaTransactionFactory` — sensible defaults for all required fields; `checkout_request_id` uses `factory.Sequence`.
- `MpesaCallbackLogFactory` — `source_ip` defaults to a valid Safaricom IP.
- Both factories resolve the model class lazily via `get_transaction_model()` and `get_callback_log_model()`.

**Create `tests/test_testing/test_factories.py`** with:
- `test_transaction_factory_creates_db_row(db)` — assert row saved with correct defaults.
- `test_transaction_factory_checkout_id_is_unique(db)` — create two, assert different `checkout_request_id` values.
- `test_callback_log_factory_creates_db_row(db)`.
- `test_factory_override_status(db)` — `MpesaTransactionFactory(status="SUCCESS")`, assert `status=="SUCCESS"`.

**Done when:**
- All four tests pass.
- Both factories importable from `django_mpesa.testing.factories`.

---

### M7.03 — `testing/fixtures.py` — pytest fixtures

**Depends on:** M7.02

**Create `django_mpesa/testing/fixtures.py`** with all fixtures from `specs/design.md §8.3`:
- `mock_daraja` — function-scoped, yields `MockDarajaClient()`.
- `stk_success_callback`, `stk_failure_callback` — realistic Safaricom payload dicts.
- `c2b_confirmation_payload`, `b2c_result_success_payload`, `b2c_result_failure_payload`, `b2c_timeout_payload`.
- `pending_stk_transaction`, `pending_b2c_transaction` — factory-created DB rows.

All payload fixtures use exact Safaricom field names and nesting — no simplification.

**Update `tests/conftest.py`** to import all fixtures:
```python
from django_mpesa.testing.fixtures import *  # noqa
```

**Verify** all existing callback tests (M3, M4, M5) that already use these fixtures still pass after this change — they should now consume the fixtures from the official source rather than any local definitions.

**Done when:**
- All existing tests that use fixtures pass unchanged.
- `from django_mpesa.testing.fixtures import mock_daraja` works in a host app's `conftest.py`.

---

### M7.04 — Coverage audit and gap fill

**Depends on:** M7.01–M7.03, all previous milestones

Run:
```bash
pytest --cov=django_mpesa --cov-report=term-missing --cov-fail-under=90
```

For every file below 90%:
1. Identify uncovered lines.
2. Add targeted tests covering those lines — no "coverage padding" (tests must assert meaningful behaviour, not just execute code).
3. Re-run until all files are ≥ 90%.

**Files most likely to need gap-filling:**
- `conf.py` — edge cases in callable resolution, `AttributeError` path.
- `middleware.py` — `X-Forwarded-For` trusted proxy resolution edge cases.
- `tasks.py` — error paths: `CallbackLog.DoesNotExist`, malformed payload, Celery retry path.
- `views.py` — exception during `request.data` parsing.

**Done when:**
- `pytest --cov=django_mpesa --cov-fail-under=90` passes with no failures.
- No test file contains trivial "smoke" tests that assert nothing meaningful just to hit lines.

---

### M7.05 — Final idempotency test review

**Depends on:** M7.04, M3.04, M4.04, M5.04

Review `tests/test_idempotency.py` and confirm all three concurrency tests (STK, C2B, B2C) are present and:
- Use `@pytest.mark.django_db(transaction=True)`.
- Use `threading.Barrier(2)`.
- Assert signal fires exactly once.
- Assert `settled_at` is set exactly once (not overwritten by the second thread).
- Pass consistently across 10 sequential runs: `pytest tests/test_idempotency.py --count=10`.

**Done when:**
- All three tests pass 10/10 runs.
- The test file has a module-level comment explaining why `transaction=True` is required (for the next contributor who wonders why it's different from other tests).

---

### M7.06 — Testing module public API

**Depends on:** M7.01–M7.03

**Update `django_mpesa/testing/__init__.py`** to export:
```python
from django_mpesa.testing.mock_client import MockDarajaClient
from django_mpesa.testing.factories import MpesaTransactionFactory, MpesaCallbackLogFactory

__all__ = ["MockDarajaClient", "MpesaTransactionFactory", "MpesaCallbackLogFactory"]
```

**Create `docs/testing.md`** covering:
- How to install test extras: `pip install django-mpesa[test]`.
- How to use `MockDarajaClient` in tests.
- How to import and use fixtures.
- The idempotency test pattern (reference the concurrency test as an example).

**Done when:**
- `from django_mpesa.testing import MockDarajaClient` works.
- `docs/testing.md` exists and covers all four bullet points.

---

## Milestone 8 — Packaging, Documentation, Release

> Goal: the package is installable from PyPI, documentation is live on Read the Docs, and v0.3.0 is tagged and published.

---

### M8.01 — Final `pyproject.toml` review

**Depends on:** all previous milestones

Audit `pyproject.toml` for:
- Version is `"0.3.0"` (or `"0.1.0"` if doing a phased release — see milestone map).
- All runtime dependencies have correct minimum version pins.
- `[project.urls]` section includes Homepage, Documentation, Repository, Issues, Changelog.
- `classifiers` list includes all supported Python and Django versions.
- `[tool.hatch.build.targets.wheel]` excludes `tests/`, `docs/`, `plan/`, `specs/`.

Run `python -m build` and inspect the generated wheel to verify only `django_mpesa/` is included.

**Done when:**
- `python -m build` succeeds.
- `unzip -l dist/django_mpesa-*.whl | grep -v django_mpesa` shows no non-package files included.

---

### M8.02 — Documentation site setup

**Depends on:** M0.05

**Create `mkdocs.yml`** at project root with the full structure from `specs/design.md §9.6`.

**Create all documentation pages** listed in `specs/requirements.md §20.1`. Each page must contain:
- `docs/index.md` — overview, compatibility matrix, install snippet, links.
- `docs/quickstart.md` — the 9-step recipe targeting < 10 minutes to working STK Push.
- `docs/settings.md` — full settings reference table.
- `docs/models.md` — field reference, example host-app subclass.
- `docs/callbacks.md` — log-first pattern explained, idempotency section.
- `docs/signals.md` — signal catalog with kwargs and example receivers.
- `docs/security.md` — credential setup, security credential generation, IP allowlist.
- `docs/testing.md` — from M7.06.
- All six `docs/services/*.md` pages with method signatures and usage examples.

**Done when:**
- `mkdocs build` completes without warnings.
- `mkdocs serve` renders all pages correctly (manual check).
- Every code example in the docs is syntactically valid Python.

---

### M8.03 — Read the Docs configuration

**Depends on:** M8.02

**Create `.readthedocs.yaml`** at project root:
```yaml
version: 2
build:
  os: ubuntu-22.04
  tools:
    python: "3.12"
python:
  install:
    - method: pip
      path: .
      extra_requirements: [docs]
mkdocs:
  configuration: mkdocs.yml
```

**Connect the GitHub repository to Read the Docs** (manual step — document the steps in `CONTRIBUTING.md`).

**Done when:**
- `.readthedocs.yaml` exists and is valid.
- `CONTRIBUTING.md` includes Read the Docs setup instructions.

---

### M8.04 — `CHANGELOG.md` for release

**Depends on:** all previous milestones

**Update `CHANGELOG.md`** with a complete entry for the release version, covering:
- Added: list of all new features (all six services, callback handling, testing module, admin mixins, management command).
- Security: IP allowlist middleware, credential callable resolution.
- Known limitations: no multi-tenancy, Celery optional.

Follow [Keep a Changelog](https://keepachangelog.com) format.

**Done when:**
- `CHANGELOG.md` has a complete version entry with date.
- `[Unreleased]` section is empty (all items moved to the versioned entry).

---

### M8.05 — Pre-release checklist

**Depends on:** M8.01–M8.04

Work through every item in the security checklist from `specs/requirements.md §21`:

- [ ] `SEC-01` — no credentials in source. Run `git log --all -S "MPESA_CONSUMER" -- "*.py"` to verify.
- [ ] `SEC-02` — `SECURITY_CREDENTIAL` never stored as plaintext in library code.
- [ ] `SEC-03` — `mpesa_check_config` rejects HTTP callback URLs in production.
- [ ] `SEC-04` — IP allowlist enabled by default, verified by middleware tests.
- [ ] `SEC-05` — callback views never return stack traces (verified by test `test_callback_view_returns_200_on_malformed_payload`).
- [ ] `SEC-06` — sensitive field redaction verified by `test_sensitive_fields_redacted_in_log`.
- [ ] `SEC-07` — phone number logging only at DEBUG level (code review).
- [ ] `SEC-08` — `mpesa_check_config` warns on `DEBUG=True` in production.
- [ ] `SEC-09` — `pip-audit` passes with no high-severity findings.
- [ ] `SEC-10` — no unconstrained `*` dependencies in `pyproject.toml`.

Run the full test matrix locally across all 6 Python/Django combinations:
```bash
tox -e py310-django42,py310-django50,py311-django42,py311-django50,py312-django42,py312-django50
```

(Requires a `tox.ini` — create one if not present.)

**Done when:**
- All 10 security checklist items are checked off.
- All 6 tox environments pass.
- `pip-audit` exits 0 or with only low-severity informational findings.

---

### M8.06 — Tag and release

**Depends on:** M8.05

1. Bump version in `pyproject.toml` to the release version.
2. Final commit: `git commit -am "Release v0.x.0"`.
3. Tag: `git tag v0.x.0`.
4. Push: `git push origin main --tags`.
5. Verify the `publish.yml` CI workflow triggers and completes successfully.
6. Verify the package is installable: `pip install django-mpesa==0.x.0` in a clean virtualenv.
7. Follow `docs/quickstart.md` from scratch in the clean virtualenv — must reach a working STK Push (with mock client) in < 10 minutes.

**Done when:**
- Package appears on PyPI at the correct version.
- `pip install django-mpesa` installs the new version.
- Read the Docs has built and published the versioned docs.
- The quickstart guide works end-to-end in a fresh environment.

---

## Task Summary

| Milestone | Tasks | Key output |
|---|---|---|
| M0 | M0.01–M0.05 | Repo scaffold, CI, README |
| M1 | M1.01–M1.05 | HTTP client, auth, base client — all tested |
| M2 | M2.01–M2.06 | Settings, models, validators, signals, serializers |
| M3 | M3.01–M3.07 | STK Push end-to-end + idempotency — **v0.1.0** |
| M4 | M4.01–M4.05 | C2B service + validation + confirmation callbacks |
| M5 | M5.01–M5.05 | B2C service + result + timeout callbacks |
| M6 | M6.01–M6.07 | Transaction Status, Account Balance, Reversal, Admin, full config check |
| M7 | M7.01–M7.06 | Testing module, coverage ≥ 90%, concurrency tests |
| M8 | M8.01–M8.06 | Packaging, docs, security audit, PyPI release |

**Total tasks: 46**

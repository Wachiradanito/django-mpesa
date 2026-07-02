# django-mpesa — Full Software Requirements Specification

**Version:** 1.0
**Date:** 2026-07-01
**Author:** Daniel Maina / Mainfinity
**Status:** Draft — awaiting approval before design phase

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Design Goals & Principles](#2-design-goals--principles)
3. [Package Structure](#3-package-structure)
4. [Configuration System — `conf.py`](#4-configuration-system--confpy)
5. [Data Models — `models.py`](#5-data-models--modelspy)
6. [Exception Hierarchy — `exceptions.py`](#6-exception-hierarchy--exceptionspy)
7. [Validators — `validators.py`](#7-validators--validatorspy)
8. [Client Layer — `client/`](#8-client-layer--client)
9. [Service Layer — `services/`](#9-service-layer--services)
10. [Callback Handling — `views.py`, `tasks.py`, `middleware.py`](#10-callback-handling--viewspy-taskspy-middlewarepy)
11. [URL Configuration — `urls.py`](#11-url-configuration--urlspy)
12. [Signals — `signals.py`](#12-signals--signalspy)
13. [Admin — `admin.py`](#13-admin--adminpy)
14. [Management Commands](#14-management-commands)
15. [Serializers — `serializers.py`](#15-serializers--serializerspy)
16. [Testing Module — `django_mpesa/testing/`](#16-testing-module--django_mpesatesting)
17. [Test Suite — `tests/`](#17-test-suite--tests)
18. [Packaging & Distribution](#18-packaging--distribution)
19. [CI/CD](#19-cicd)
20. [Documentation](#20-documentation)
21. [Security Requirements](#21-security-requirements)
22. [Non-Functional Requirements](#22-non-functional-requirements)
23. [Out of Scope](#23-out-of-scope)
24. [Constraints & Assumptions](#24-constraints--assumptions)
25. [Glossary](#25-glossary)

---

## 1. Project Overview

`django-mpesa` is a reusable, open-source Django application that wraps Safaricom's Daraja API. It is extracted from production logic used in Zaruni and is designed to be installed into any Django project as a first-class, zero-fork dependency.

### 1.1 What it does

- Provides service classes for every Daraja API endpoint: STK Push, C2B, B2C, Transaction Status, Account Balance, and Reversal.
- Handles inbound Safaricom callbacks with guaranteed idempotent settlement — a transaction is settled exactly once even when Safaricom delivers the same callback multiple times or concurrently.
- Exposes abstract Django models that host applications subclass and extend with their own domain fields (orders, users, wallets).
- Fires Django signals at settlement time so host apps can react (credit a wallet, send an SMS) without the library knowing about their domain.
- Ships a mock client and pytest fixtures so host-app test suites never need Safaricom's sandbox to be reachable.

### 1.2 What it does NOT do

- Wallet, ledger, or balance logic.
- User authentication or authorization.
- SMS, email, or push notification delivery.
- Any UI components or frontend code.
- Multi-tenancy (multiple shortcodes in one Django instance) — deferred post-1.0.0.
- Order management or any other host-app business logic.

### 1.3 Primary users

| User | How they interact |
|---|---|
| Integrating developer | Installs the package, subclasses models, wires signals, calls service methods |
| Open-source contributor | Adds features or fixes bugs following the contributing guide |
| Safaricom Daraja system | POSTs callbacks to the registered callback endpoints |

### 1.4 Source of truth

This document is the authoritative requirements reference for all implementation work. The blueprint in `plan/django-mpesa-blueprint.md` is the design narrative that informed this document. Where the two differ, this document takes precedence.

---

## 2. Design Goals & Principles

These are binding constraints on every implementation decision. If a proposed implementation violates one of these principles, it must be redesigned.

| # | Principle | Meaning |
|---|---|---|
| G-01 | **Idempotent by default** | A transaction is settled exactly once regardless of how many times the same callback arrives, including concurrent delivery. This is the single most important correctness property. |
| G-02 | **Host-agnostic** | The library contains zero project-specific logic. No wallet fields, no user FKs, no Zaruni-specific code. |
| G-03 | **Swappable models** | Host apps subclass abstract base models and register them via settings, the same pattern Django uses for `AUTH_USER_MODEL`. The library never imports a concrete model directly. |
| G-04 | **Sandbox-safe testing** | The full test suite must pass with no external network access. A mock client ships with the package. |
| G-05 | **Secure by default** | Credentials never hardcoded. Callback source IP verified. Sensitive fields never leak into logs or HTTP responses. |
| G-06 | **One responsibility per module** | Each Daraja API is a separate service class. No god-object client. |
| G-07 | **Fail loudly on misconfiguration** | A misconfigured library must fail at deploy time (management command) or at import time, never silently at runtime when a payment is attempted. |
| G-08 | **No forced Celery dependency** | Celery is optional. The library must be fully functional (synchronous callback processing) without it. |

---

## 3. Package Structure

The following is the complete, canonical file tree for the project. Every file listed here must exist in the final package. Files marked `(generated)` are created during build/install and not committed.

```
django-mpesa/
├── pyproject.toml                        # build config, dependencies, metadata
├── LICENSE                               # MIT
├── README.md                             # PyPI landing page + quick install
├── CONTRIBUTING.md                       # contributor guide
├── CODE_OF_CONDUCT.md                    # Contributor Covenant
├── CHANGELOG.md                          # semver changelog
│
├── .github/
│   ├── workflows/
│   │   ├── test.yml                      # pytest matrix on every PR
│   │   └── publish.yml                   # PyPI publish on version tag
│   └── ISSUE_TEMPLATE/
│       ├── bug_report.md
│       └── feature_request.md
│
├── docs/
│   ├── index.md
│   ├── quickstart.md
│   ├── settings.md
│   ├── models.md
│   ├── callbacks.md
│   ├── signals.md
│   ├── testing.md
│   ├── security.md
│   └── services/
│       ├── stk_push.md
│       ├── c2b.md
│       ├── b2c.md
│       ├── transaction_status.md
│       ├── account_balance.md
│       └── reversal.md
│
├── django_mpesa/
│   ├── __init__.py                       # exports __version__
│   ├── apps.py                           # MpesaConfig(AppConfig)
│   ├── conf.py                           # settings resolver
│   ├── exceptions.py                     # full exception hierarchy
│   ├── models.py                         # abstract base models
│   ├── signals.py                        # signal definitions
│   ├── views.py                          # callback endpoints (DRF APIView)
│   ├── urls.py                           # includeable URL patterns
│   ├── tasks.py                          # Celery tasks for async processing
│   ├── middleware.py                     # Safaricom IP allowlist middleware
│   ├── validators.py                     # phone, amount, reference validators
│   ├── serializers.py                    # DRF serializers for callback payloads
│   ├── admin.py                          # optional admin registration mixin
│   │
│   ├── client/
│   │   ├── __init__.py
│   │   ├── auth.py                       # TokenManager
│   │   ├── base.py                       # BaseDarajaClient
│   │   └── http.py                       # requests.Session factory
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── stk_push.py                   # STKPushService
│   │   ├── c2b.py                        # C2BService
│   │   ├── b2c.py                        # B2CService
│   │   ├── transaction_status.py         # TransactionStatusService
│   │   ├── account_balance.py            # AccountBalanceService
│   │   └── reversal.py                   # ReversalService
│   │
│   ├── management/
│   │   └── commands/
│   │       └── mpesa_check_config.py     # deploy-time config validator
│   │
│   └── testing/
│       ├── __init__.py
│       ├── mock_client.py                # MockDarajaClient
│       ├── fixtures.py                   # pytest fixtures
│       └── factories.py                  # factory_boy model factories
│
└── tests/
    ├── conftest.py
    ├── settings.py                       # minimal Django settings for test suite
    ├── test_client/
    │   ├── test_auth.py
    │   ├── test_base.py
    │   └── test_http.py
    ├── test_services/
    │   ├── test_stk_push.py
    │   ├── test_c2b.py
    │   ├── test_b2c.py
    │   ├── test_transaction_status.py
    │   ├── test_account_balance.py
    │   └── test_reversal.py
    ├── test_callbacks/
    │   ├── test_stk_callback.py
    │   ├── test_c2b_callbacks.py
    │   └── test_b2c_callbacks.py
    ├── test_models/
    │   └── test_abstract_models.py
    └── test_idempotency.py               # concurrency regression test
```

---

## 4. Configuration System — `conf.py`

### 4.1 Settings dict

All settings live under a single `MPESA` top-level key in the host app's Django `settings.py`. The library must never read any other top-level setting key.

### 4.2 Full settings reference

| Key | Type | Required | Default | Description |
|---|---|---|---|---|
| `ENV` | `str` | Yes | `"sandbox"` | `"sandbox"` or `"production"`. Controls the Daraja base URL and enables/disables sandbox-only methods. |
| `CONSUMER_KEY` | `str` or `callable` | Yes | — | Daraja consumer key. Must support callable so it can be resolved from env vars or secrets manager at runtime. |
| `CONSUMER_SECRET` | `str` or `callable` | Yes | — | Daraja consumer secret. Same callable support. |
| `SHORTCODE` | `str` or `callable` | Yes | — | Safaricom business shortcode (paybill or till number). |
| `PASSKEY` | `str` or `callable` | Yes for STK | — | Lipa Na M-Pesa passkey. Used to build the STK Push password field. |
| `INITIATOR_NAME` | `str` or `callable` | Yes for B2C/Reversal | `None` | Name of the API operator configured in the M-PESA portal. |
| `INITIATOR_PASSWORD` | `str` or `callable` | No | `None` | Plaintext initiator password. Used only to generate `SECURITY_CREDENTIAL` — must never be sent to Daraja. |
| `SECURITY_CREDENTIAL` | `str` or `callable` | Yes for B2C/Reversal | `None` | RSA-encrypted initiator password. Pre-generated using Safaricom's public certificate. If provided, `INITIATOR_PASSWORD` is ignored. |
| `STK_CALLBACK_URL` | `str` | Yes for STK | — | Publicly reachable HTTPS URL for STK Push callbacks. Must match the path exposed by `django_mpesa.urls`. |
| `C2B_VALIDATION_URL` | `str` | Yes for C2B | — | HTTPS URL for C2B validation callbacks. |
| `C2B_CONFIRMATION_URL` | `str` | Yes for C2B | — | HTTPS URL for C2B confirmation callbacks. |
| `B2C_RESULT_URL` | `str` | Yes for B2C | — | HTTPS URL for B2C result callbacks. |
| `B2C_TIMEOUT_URL` | `str` | Yes for B2C | — | HTTPS URL for B2C timeout callbacks. |
| `TOKEN_CACHE_ALIAS` | `str` | No | `"default"` | Django cache alias used to store the OAuth bearer token. |
| `TOKEN_CACHE_TTL_BUFFER` | `int` | No | `60` | Seconds subtracted from Safaricom's `expires_in` before storing in cache. Prevents using a token that is about to expire. |
| `REQUEST_TIMEOUT` | `int` | No | `30` | Seconds before an outbound HTTP request times out. |
| `MAX_RETRIES` | `int` | No | `3` | Maximum retry attempts for transient failures (5xx, connection errors). |
| `RETRY_BACKOFF_FACTOR` | `float` | No | `0.5` | Multiplier for exponential backoff between retries. |
| `VERIFY_CALLBACK_SOURCE_IP` | `bool` | No | `True` | Enforce Safaricom IP allowlist on callback endpoints. Set `False` for local development only. |
| `CALLBACK_IP_ALLOWLIST` | `list[str]` | No | See below | List of Safaricom IP addresses allowed to POST to callback endpoints. |
| `TRUST_FORWARDED_FOR` | `bool` | No | `False` | When `True`, use `X-Forwarded-For` header to resolve real client IP (for deployments behind Cloudflare, Caddy, or a load balancer). |
| `FORWARDED_FOR_TRUSTED_PROXIES` | `list[str]` | No | `[]` | Explicit list of trusted proxy IPs whose `X-Forwarded-For` headers should be trusted. |
| `TRANSACTION_MODEL` | `str` | Yes | — | Dotted app-label string pointing to the host app's concrete transaction model, e.g. `"myapp.MpesaTransaction"`. |
| `CALLBACK_LOG_MODEL` | `str` | Yes | — | Dotted app-label string pointing to the host app's concrete callback log model. |
| `USE_CELERY` | `bool` | No | `True` | When `True`, dispatch callback processing to Celery. When `False`, process synchronously in the request. |
| `CELERY_TASK_MAX_RETRIES` | `int` | No | `5` | Max retries for the Celery callback processing tasks. |
| `CELERY_TASK_RETRY_BACKOFF` | `bool` | No | `True` | Enable exponential backoff on Celery task retries. |

**Default IP allowlist** (Safaricom's published ranges as of writing — operator must override if Safaricom publishes new ranges):
```
196.201.214.200, 196.201.214.206, 196.201.213.114,
196.201.214.207, 196.201.214.208, 196.201.213.44,
196.201.212.127, 196.201.212.128, 196.201.212.129,
196.201.212.132, 196.201.212.136
```

### 4.3 Settings resolver

`conf.py` must expose a `mpesa_settings` object (pattern: DRF's `api_settings`) with the following behaviour:

- Attribute access on `mpesa_settings` returns the value from `settings.MPESA` if present, or the default if not.
- If the value is callable, it is called and the return value is used. This allows credentials to be resolved lazily from environment variables or secrets managers.
- If a required key is absent and has no default, accessing it raises `DarajaConfigError` immediately.
- `mpesa_settings` must be importable without a Django project configured (needed for the management command help text).

### 4.4 Settings validation rules

These rules are enforced by both the settings resolver and `mpesa_check_config`:

- `ENV` must be exactly `"sandbox"` or `"production"`.
- All callback URLs must start with `https://` when `ENV == "production"`. In sandbox they may be HTTP (for ngrok/local tunnels).
- `TRANSACTION_MODEL` and `CALLBACK_LOG_MODEL` must be resolvable via `django.apps.apps.get_model()` at startup.
- When `USE_CELERY` is `True`, Celery must be installed and importable — raise `DarajaConfigError` with a clear message if not.
- `TOKEN_CACHE_TTL_BUFFER` must be a positive integer less than 3600.
- `MAX_RETRIES` must be a non-negative integer.

---

## 5. Data Models — `models.py`

### 5.1 Design rules

- All models shipped by the library are **abstract** (`class Meta: abstract = True`). The library generates no migrations.
- Host apps subclass the abstract models, add their own fields, and run `makemigrations` in their own app.
- The library accesses models exclusively through `django.apps.apps.get_model(settings.TRANSACTION_MODEL)` — never via a direct import of a concrete class.
- `amount` is always `DecimalField` — never `FloatField`. Floating-point arithmetic on currency values is a bug, not a shortcut.
- All primary keys are UUID (`default=uuid.uuid4`, `editable=False`) — Safaricom's own IDs are never used as PKs.

### 5.2 `AbstractMpesaTransaction`

Full field specification:

| Field | Django field type | Constraints | Description |
|---|---|---|---|
| `id` | `UUIDField` | PK, `default=uuid.uuid4`, `editable=False` | Internal primary key. Never expose to Safaricom. |
| `transaction_type` | `CharField(max_length=20)` | `choices=TRANSACTION_TYPE_CHOICES`, not null | One of: `STK_PUSH`, `C2B`, `B2C`, `REVERSAL`. |
| `status` | `CharField(max_length=20)` | `choices=STATUS_CHOICES`, `default="PENDING"`, not null | One of: `PENDING`, `PROCESSING`, `SUCCESS`, `FAILED`, `TIMEOUT`, `REVERSED`. |
| `checkout_request_id` | `CharField(max_length=200)` | `unique=True`, `null=True`, `blank=True` | STK Push idempotency key. Populated at initiation time. |
| `merchant_request_id` | `CharField(max_length=200)` | `null=True`, `blank=True` | STK Push cross-reference ID from Daraja. |
| `conversation_id` | `CharField(max_length=200)` | `unique=True`, `null=True`, `blank=True` | B2C / Reversal idempotency key. Populated at initiation time. |
| `originator_conversation_id` | `CharField(max_length=200)` | `null=True`, `blank=True` | B2C / Reversal reference set at request time. |
| `mpesa_receipt_number` | `CharField(max_length=50)` | `null=True`, `blank=True` | Safaricom's M-PESA transaction receipt. Only populated on `SUCCESS`. |
| `phone_number` | `CharField(max_length=15)` | not null | E.164 format, `2547XXXXXXXX`. Validated via `validators.py`. |
| `amount` | `DecimalField(max_digits=12, decimal_places=2)` | not null | Payment amount. Never float. |
| `account_reference` | `CharField(max_length=12)` | not null | Used in STK Push and C2B. Free text tied to host order/invoice. Max 12 chars per Daraja spec. |
| `transaction_desc` | `CharField(max_length=13)` | not null | Human-readable description sent to Daraja. Max 13 chars per Daraja spec. |
| `result_code` | `IntegerField` | `null=True`, `blank=True` | Raw Safaricom result code. `0` = success. Populated from callback. |
| `result_desc` | `TextField` | `null=True`, `blank=True` | Raw Safaricom result description string. Populated from callback. |
| `raw_callback_payload` | `JSONField` | `null=True`, `blank=True` | Full deserialized callback body stored for audit and debug. |
| `initiated_at` | `DateTimeField` | `auto_now_add=True` | Timestamp when the library created the transaction record. |
| `settled_at` | `DateTimeField` | `null=True`, `blank=True` | Timestamp set exactly once when status moves to a terminal state. |
| `idempotency_locked` | `BooleanField` | `default=False` | Set to `True` inside the `select_for_update` block before writing the terminal status, then to `False` after. Used as a fencing token — see §10.4. |

**Choices constants** (defined in `models.py`, importable by host apps):

```python
TRANSACTION_TYPE_CHOICES = [
    ("STK_PUSH", "STK Push"),
    ("C2B", "C2B"),
    ("B2C", "B2C"),
    ("REVERSAL", "Reversal"),
]

STATUS_CHOICES = [
    ("PENDING", "Pending"),
    ("PROCESSING", "Processing"),
    ("SUCCESS", "Success"),
    ("FAILED", "Failed"),
    ("TIMEOUT", "Timeout"),
    ("REVERSED", "Reversed"),
]

TERMINAL_STATES = {"SUCCESS", "FAILED", "TIMEOUT", "REVERSED"}
```

**Class-level contracts:**
- `checkout_request_id` carries `unique=True`. The DB constraint is the last line of defence against duplicate rows, but the primary idempotency mechanism is the row lock in `tasks.py`.
- `conversation_id` carries `unique=True` for the same reason.
- Both fields allow `null=True` because only one applies per transaction type (STK Push uses `checkout_request_id`; B2C uses `conversation_id`).
- The `Meta` class must set `abstract = True` and `ordering = ["-initiated_at"]`.
- The model must define `__str__` returning `f"{self.transaction_type} {self.status} {self.amount} {self.phone_number}"`.

### 5.3 `AbstractMpesaCallbackLog`

Every raw inbound callback — valid, invalid, malformed, duplicate — is logged here before any business logic runs. This is the forensic audit trail.

| Field | Django field type | Constraints | Description |
|---|---|---|---|
| `id` | `UUIDField` | PK, `default=uuid.uuid4`, `editable=False` | |
| `callback_type` | `CharField(max_length=30)` | `choices=CALLBACK_TYPE_CHOICES`, not null | See choices below. |
| `source_ip` | `GenericIPAddressField` | not null | IP address from which the callback was received. |
| `raw_body` | `JSONField` | not null | Full deserialized request body. Stored before any validation. |
| `related_transaction` | `ForeignKey` to `TRANSACTION_MODEL` | `null=True`, `blank=True`, `on_delete=SET_NULL` | Linked to the matching transaction after processing. `null` if no match found. |
| `processed` | `BooleanField` | `default=False` | Set to `True` after the processing task completes successfully. |
| `error` | `TextField` | `null=True`, `blank=True` | If processing failed, the error message is stored here for debugging. |
| `received_at` | `DateTimeField` | `auto_now_add=True` | Timestamp of receipt. |

**Choices:**
```python
CALLBACK_TYPE_CHOICES = [
    ("STK", "STK Push Callback"),
    ("C2B_VALIDATION", "C2B Validation"),
    ("C2B_CONFIRMATION", "C2B Confirmation"),
    ("B2C_RESULT", "B2C Result"),
    ("B2C_TIMEOUT", "B2C Timeout"),
]
```

**Class-level contracts:**
- `Meta: abstract = True`, `ordering = ["-received_at"]`.
- `__str__` returns `f"{self.callback_type} from {self.source_ip} at {self.received_at}"`.

### 5.4 Example host-app implementation

```python
# myapp/models.py
from django.db import models
from django.conf import settings
from django_mpesa.models import AbstractMpesaTransaction, AbstractMpesaCallbackLog

class MpesaTransaction(AbstractMpesaTransaction):
    order = models.ForeignKey(
        "orders.Order", on_delete=models.PROTECT, null=True, blank=True
    )
    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )

    class Meta(AbstractMpesaTransaction.Meta):
        verbose_name = "M-PESA Transaction"
        verbose_name_plural = "M-PESA Transactions"

class MpesaCallbackLog(AbstractMpesaCallbackLog):
    class Meta(AbstractMpesaCallbackLog.Meta):
        verbose_name = "M-PESA Callback Log"
```

```python
# settings.py
MPESA = {
    "TRANSACTION_MODEL": "myapp.MpesaTransaction",
    "CALLBACK_LOG_MODEL": "myapp.MpesaCallbackLog",
    # ... rest of config
}
```

---

## 6. Exception Hierarchy — `exceptions.py`

### 6.1 Full hierarchy

```
MpesaError(Exception)                   # base — all library exceptions inherit from this
├── DarajaConfigError                   # misconfigured settings, wrong env for method
├── DarajaAuthError                     # OAuth token fetch failed (bad credentials, network)
├── DarajaValidationError               # bad input caught before any network call
├── DarajaAPIError                      # Safaricom returned non-2xx or error ResultCode
│   ├── DarajaRateLimitError            # HTTP 429 from Daraja
│   └── DarajaTimeoutError              # request timed out (requests.Timeout)
└── InvalidCallbackError                # callback payload malformed or IP not in allowlist
```

### 6.2 Required attributes on all exceptions

Every exception class must carry:

| Attribute | Type | Description |
|---|---|---|
| `message` | `str` | Human-readable error description. |
| `result_code` | `int \| None` | Safaricom's numeric result code where applicable, else `None`. |
| `result_desc` | `str \| None` | Safaricom's result description string where applicable, else `None`. |

### 6.3 When each exception is raised

| Exception | Raised when |
|---|---|
| `DarajaConfigError` | Required settings key missing; `ENV` invalid; `simulate()` called in production; `TRANSACTION_MODEL` unresolvable; Celery not installed but `USE_CELERY=True`. |
| `DarajaAuthError` | Token fetch returns non-2xx; token fetch fails after one retry post-401; credentials invalid. |
| `DarajaValidationError` | Phone number fails E.164 validation; amount is negative or zero; `account_reference` > 12 chars; `transaction_desc` > 13 chars; any other input constraint violation caught before the HTTP call. |
| `DarajaAPIError` | Safaricom returns any non-2xx that is not 401, 429, or a timeout; Safaricom response body contains a non-zero `ResponseCode` or `ResultCode` indicating a processing error. |
| `DarajaRateLimitError` | Safaricom returns HTTP 429. |
| `DarajaTimeoutError` | `requests.Timeout` raised during any outbound call. |
| `InvalidCallbackError` | Callback IP not in allowlist; callback body missing required top-level fields; JSON parse failure on callback body. |

---

## 7. Validators — `validators.py`

### 7.1 Phone number validator

- Accepts strings in `2547XXXXXXXX` or `+2547XXXXXXXX` format.
- Strips leading `+` if present and normalises to `2547XXXXXXXX` (12 digits, starting with `254`).
- Also accepts `07XXXXXXXX` (10 digits) and `7XXXXXXXX` (9 digits) and normalises them to `2547XXXXXXXX`.
- Raises `DarajaValidationError` if: not a string; contains non-digit characters after stripping `+`; normalised number is not exactly 12 digits; does not start with `254`.
- Returns the normalised E.164 number as a string (without `+`).

### 7.2 Amount validator

- Accepts `int`, `float`, or `Decimal`.
- Converts to `Decimal` with 2 decimal places.
- Raises `DarajaValidationError` if: value is zero; value is negative; value has more than 2 decimal places after conversion (Safaricom rejects fractional shillings in some APIs); value exceeds 150,000 (Safaricom's STK Push per-transaction limit — configurable override allowed for B2C which has different limits).
- Returns a `Decimal` value.

### 7.3 Account reference validator

- Accepts any string.
- Strips leading/trailing whitespace.
- Raises `DarajaValidationError` if: empty after stripping; length > 12 characters.
- Returns the stripped string.

### 7.4 Transaction description validator

- Same as account reference but max length is 13 characters.

### 7.5 Command ID validator (B2C)

- Accepts only: `"BusinessPayment"`, `"SalaryPayment"`, `"PromotionPayment"`.
- Raises `DarajaValidationError` for any other value.

---

## 8. Client Layer — `client/`

### 8.1 `client/http.py` — HTTP session factory

Provides a configured `requests.Session` instance used by `BaseDarajaClient`.

**Requirements:**
- Session must have a `urllib3.util.retry.Retry` adapter mounted for transport-level retries on connection errors only (not HTTP error codes — those are handled at the application layer).
- Must set a default `User-Agent` header: `django-mpesa/{version}`.
- Must not duplicate the application-level retry logic in `base.py` — the two layers must not compound. Transport retries are for TCP/TLS failures; application retries are for Daraja 5xx responses.
- The session factory is a module-level function `get_session() -> requests.Session` so it can be replaced in tests.

### 8.2 `client/auth.py` — `TokenManager`

Manages the Daraja OAuth 2.0 bearer token lifecycle.

**Daraja OAuth endpoint:**
- Sandbox: `https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials`
- Production: `https://api.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials`

**Method: `get_token() -> str`**

Full behaviour:
1. Compute cache key: `f"django_mpesa:token:{env}"` where `env` is `mpesa_settings.ENV`.
2. Attempt `cache.get(cache_key)`. If a token is returned, return it immediately.
3. If not in cache: use `cache.add(lock_key, "1", timeout=10)` as a distributed lock to prevent concurrent cold-start stampedes. `lock_key = f"django_mpesa:token_lock:{env}"`.
4. If `cache.add` returns `True` (lock acquired): call `_fetch_new_token()`, store the result with `cache.set(cache_key, token, timeout=expires_in - TOKEN_CACHE_TTL_BUFFER)`, release the lock by deleting `lock_key`, return the token.
5. If `cache.add` returns `False` (another process is fetching): sleep 0.1 s and retry `get_token()` up to 5 times, then raise `DarajaAuthError("Token fetch lock timeout")`.

**Method: `_fetch_new_token() -> tuple[str, int]`**

1. Base64-encode `consumer_key:consumer_secret`.
2. GET the OAuth endpoint with `Authorization: Basic {encoded}` and `Accept: application/json`.
3. On HTTP 200: parse `access_token` and `expires_in` from response JSON. Return `(access_token, int(expires_in))`.
4. On any non-200: raise `DarajaAuthError` with the response status code and body.
5. On connection error / timeout: raise `DarajaAuthError` wrapping the original exception.

**Method: `invalidate() -> None`**

- Deletes `cache_key` from the Django cache.
- Called by `BaseDarajaClient` after receiving a 401 from any API call.

### 8.3 `client/base.py` — `BaseDarajaClient`

The single HTTP client used by all service classes. Services compose this class rather than inherit from it.

**Constructor:** `__init__(self, token_manager: TokenManager = None, session: requests.Session = None)`
- If `token_manager` is `None`, create a default `TokenManager()`.
- If `session` is `None`, call `get_session()` from `http.py`.
- Both can be injected for testing.

**Base URLs:**
- Sandbox: `https://sandbox.safaricom.co.ke`
- Production: `https://api.safaricom.co.ke`
- Selected from `mpesa_settings.ENV`.

**Method: `post(self, path: str, payload: dict) -> dict`**

Full behaviour:
1. Obtain token via `self.token_manager.get_token()`.
2. Build full URL: `base_url + path`.
3. Build headers: `{"Authorization": f"Bearer {token}", "Content-Type": "application/json", "Accept": "application/json"}`.
4. Log at DEBUG: `f"POST {url} payload={_redact(payload)}"` — `_redact()` replaces values for keys matching `{"Password", "SecurityCredential", "Passkey", "InitiatorPassword"}` with `"***"`.
5. Execute `session.post(url, json=payload, timeout=REQUEST_TIMEOUT, headers=headers)`.
6. Log at DEBUG: `f"Response {response.status_code}: {response.text[:500]}"`.
7. **On 401:** Call `token_manager.invalidate()`. Retry the entire request once (fetch a fresh token). If the retry also returns 401, raise `DarajaAuthError`.
8. **On 429:** Raise `DarajaRateLimitError`.
9. **On 5xx:** Retry up to `MAX_RETRIES` times with `time.sleep(RETRY_BACKOFF_FACTOR * (2 ** attempt))` between retries. After exhausting retries, raise `DarajaAPIError`.
10. **On 4xx (not 401, 429):** Raise `DarajaAPIError` immediately — never retry.
11. **On timeout:** Raise `DarajaTimeoutError`.
12. **On 2xx:** Parse response as JSON. If response contains `"errorCode"` key (Daraja wraps some errors in 200 responses), raise `DarajaAPIError` with the parsed error details.
13. Return parsed response dict.

**Important:** Do NOT retry 4xx responses. A 4xx means Daraja rejected the request as invalid — retrying sends the same invalid request and wastes quota.

---

## 9. Service Layer — `services/`

All service classes follow the same construction pattern:

```python
class SomeService:
    def __init__(self, client: BaseDarajaClient = None):
        self.client = client or BaseDarajaClient()
```

This allows test code to inject a `MockDarajaClient` without any patching.

### 9.1 `services/stk_push.py` — `STKPushService`

Maps to Daraja's **Lipa Na M-Pesa Online (STK Push)** API.

#### Method: `initiate(phone_number, amount, account_reference, transaction_desc) -> Transaction`

**Inputs:**

| Parameter | Type | Validation |
|---|---|---|
| `phone_number` | `str` | Normalised to `2547XXXXXXXX` via `validate_phone_number()` |
| `amount` | `Decimal \| int \| float` | Validated and converted to `Decimal` via `validate_amount()` |
| `account_reference` | `str` | Max 12 chars via `validate_account_reference()` |
| `transaction_desc` | `str` | Max 13 chars via `validate_transaction_desc()` |

**Step-by-step behaviour:**
1. Run all four validators. Raise `DarajaValidationError` on first failure — no network call made.
2. Generate timestamp: `datetime.now().strftime("%Y%m%d%H%M%S")`.
3. Build password: `base64(shortcode + passkey + timestamp)`.
4. Build request payload:
   ```json
   {
     "BusinessShortCode": "<shortcode>",
     "Password": "<base64_password>",
     "Timestamp": "<timestamp>",
     "TransactionType": "CustomerPayBillOnline",
     "Amount": "<amount as integer — Safaricom rejects decimals>",
     "PartyA": "<phone_number>",
     "PartyB": "<shortcode>",
     "PhoneNumber": "<phone_number>",
     "CallBackURL": "<STK_CALLBACK_URL>",
     "AccountReference": "<account_reference>",
     "TransactionDesc": "<transaction_desc>"
   }
   ```
5. POST to `/mpesa/stkpush/v1/processrequest`.
6. On success (response has `ResponseCode == "0"`): create and save a transaction record with:
   - `transaction_type = "STK_PUSH"`
   - `status = "PENDING"`
   - `checkout_request_id` from response `CheckoutRequestID`
   - `merchant_request_id` from response `MerchantRequestID`
   - `phone_number`, `amount`, `account_reference`, `transaction_desc` from inputs
7. Return the saved transaction instance.
8. On failure: raise `DarajaAPIError` — do NOT create a transaction record for a failed initiation.

#### Method: `query(checkout_request_id: str) -> dict`

1. Build payload:
   ```json
   {
     "BusinessShortCode": "<shortcode>",
     "Password": "<base64_password>",
     "Timestamp": "<timestamp>",
     "CheckoutRequestID": "<checkout_request_id>"
   }
   ```
2. POST to `/mpesa/stkpushquery/v1/query`.
3. Return the raw response dict.
4. **Must not** modify any transaction record. The caller is responsible for reconciliation.

### 9.2 `services/c2b.py` — `C2BService`

Maps to Daraja's **Customer to Business (C2B)** API.

#### Method: `register_urls(response_type: str = "Completed") -> dict`

1. `response_type` must be `"Completed"` or `"Cancelled"`. Raise `DarajaValidationError` otherwise.
2. Build payload:
   ```json
   {
     "ShortCode": "<shortcode>",
     "ResponseType": "<response_type>",
     "ConfirmationURL": "<C2B_CONFIRMATION_URL>",
     "ValidationURL": "<C2B_VALIDATION_URL>"
   }
   ```
3. POST to `/mpesa/c2b/v1/registerurl`.
4. Return raw response dict.
5. This is a one-time setup call — must be idempotent (Safaricom allows calling it multiple times).

#### Method: `simulate(phone_number: str, amount: Decimal, bill_ref: str) -> dict`

1. **Raise `DarajaConfigError` immediately if `mpesa_settings.ENV == "production"`.**
2. Validate `phone_number` and `amount`.
3. Build payload:
   ```json
   {
     "ShortCode": "<shortcode>",
     "CommandID": "CustomerPayBillOnline",
     "Amount": "<amount>",
     "Msisdn": "<phone_number>",
     "BillRefNumber": "<bill_ref>"
   }
   ```
4. POST to `/mpesa/c2b/v1/simulate`.
5. Return raw response dict.

### 9.3 `services/b2c.py` — `B2CService`

Maps to Daraja's **Business to Customer (B2C)** API.

#### Method: `send_payment(phone_number, amount, remarks, occasion="", command_id="BusinessPayment") -> Transaction`

**Inputs:**

| Parameter | Type | Validation |
|---|---|---|
| `phone_number` | `str` | `validate_phone_number()` |
| `amount` | `Decimal` | `validate_amount()` |
| `remarks` | `str` | Max 100 chars, not empty |
| `occasion` | `str` | Max 100 chars, optional |
| `command_id` | `str` | `validate_command_id()` — must be one of the three valid values |

**Step-by-step behaviour:**
1. Run all validators.
2. Build payload:
   ```json
   {
     "InitiatorName": "<INITIATOR_NAME>",
     "SecurityCredential": "<SECURITY_CREDENTIAL>",
     "CommandID": "<command_id>",
     "Amount": "<amount>",
     "PartyA": "<shortcode>",
     "PartyB": "<phone_number>",
     "Remarks": "<remarks>",
     "QueueTimeOutURL": "<B2C_TIMEOUT_URL>",
     "ResultURL": "<B2C_RESULT_URL>",
     "Occasion": "<occasion>"
   }
   ```
3. POST to `/mpesa/b2c/v1/paymentrequest`.
4. On synchronous success response: create and save a transaction record with:
   - `transaction_type = "B2C"`
   - `status = "PENDING"`
   - `conversation_id` from response `ConversationID`
   - `originator_conversation_id` from response `OriginatorConversationID`
   - `phone_number`, `amount`, `transaction_desc = remarks`
5. Return the saved transaction instance.
6. **Terminal status (`SUCCESS` or `FAILED`) is set ONLY by the B2C result callback, never here.**

### 9.4 `services/transaction_status.py` — `TransactionStatusService`

#### Method: `query(transaction_id: str, identifier_type: str = "1") -> dict`

1. `identifier_type` must be one of `"1"` (MSISDN), `"2"` (till), `"4"` (shortcode). Raise `DarajaValidationError` otherwise.
2. Build payload:
   ```json
   {
     "Initiator": "<INITIATOR_NAME>",
     "SecurityCredential": "<SECURITY_CREDENTIAL>",
     "CommandID": "TransactionStatusQuery",
     "TransactionID": "<transaction_id>",
     "PartyA": "<shortcode>",
     "IdentifierType": "<identifier_type>",
     "ResultURL": "<B2C_RESULT_URL>",
     "QueueTimeOutURL": "<B2C_TIMEOUT_URL>",
     "Remarks": "Transaction status query",
     "Occasion": ""
   }
   ```
3. POST to `/mpesa/transactionstatus/v1/query`.
4. Return raw response dict.
5. **Must not** mutate any transaction record.

### 9.5 `services/account_balance.py` — `AccountBalanceService`

#### Method: `query(identifier_type: str = "4") -> dict`

1. `identifier_type` must be `"1"`, `"2"`, or `"4"`.
2. Build payload:
   ```json
   {
     "Initiator": "<INITIATOR_NAME>",
     "SecurityCredential": "<SECURITY_CREDENTIAL>",
     "CommandID": "AccountBalance",
     "PartyA": "<shortcode>",
     "IdentifierType": "<identifier_type>",
     "Remarks": "Account balance query",
     "QueueTimeOutURL": "<B2C_TIMEOUT_URL>",
     "ResultURL": "<B2C_RESULT_URL>"
   }
   ```
3. POST to `/mpesa/accountbalance/v1/query`.
4. Return the synchronous acknowledgement dict. The actual balance arrives via callback — this method only confirms the query was accepted.

### 9.6 `services/reversal.py` — `ReversalService`

#### Method: `reverse(transaction_id: str, amount: Decimal, remarks: str, receiver_party: str) -> dict`

1. Validate `amount` and `remarks`.
2. Build payload:
   ```json
   {
     "Initiator": "<INITIATOR_NAME>",
     "SecurityCredential": "<SECURITY_CREDENTIAL>",
     "CommandID": "TransactionReversal",
     "TransactionID": "<transaction_id>",
     "Amount": "<amount>",
     "ReceiverParty": "<receiver_party>",
     "RecieverIdentifierType": "11",
     "ResultURL": "<B2C_RESULT_URL>",
     "QueueTimeOutURL": "<B2C_TIMEOUT_URL>",
     "Remarks": "<remarks>",
     "Occasion": ""
   }
   ```
3. POST to `/mpesa/reversal/v1/request`.
4. Return raw synchronous acknowledgement dict.
5. **The original transaction's status is updated to `REVERSED` only after the reversal result callback confirms success — never here.**

---

## 10. Callback Handling — `views.py`, `tasks.py`, `middleware.py`

### 10.1 Request lifecycle (all callbacks)

```
Safaricom POST
  → MpesaCallbackIPAllowlistMiddleware   (IP check — 403 if blocked)
  → CallbackView.post()
      → Save raw payload to CallbackLog (unconditional, even if malformed)
      → Dispatch processing task (async via Celery OR synchronous)
      → Return {"ResultCode": 0, "ResultDesc": "Accepted"}, HTTP 200
  → Celery task (or synchronous call)
      → select_for_update() row lock on transaction
      → Idempotency check: if terminal state, exit silently
      → Update transaction status
      → Fire signal (outside the lock)
      → Mark CallbackLog.processed = True
```

### 10.2 `middleware.py` — `MpesaCallbackIPAllowlistMiddleware`

**Class:** `MpesaCallbackIPAllowlistMiddleware(get_response)`

**Behaviour:**
- The middleware is only active for URL paths that begin with the django_mpesa URL prefix. For all other paths it must be a pure passthrough with zero overhead.
- To determine the client IP:
  - If `TRUST_FORWARDED_FOR` is `False` (default): use `request.META["REMOTE_ADDR"]` directly.
  - If `TRUST_FORWARDED_FOR` is `True`: parse `X-Forwarded-For` header, take the leftmost IP that is not in `FORWARDED_FOR_TRUSTED_PROXIES`, or fall back to `REMOTE_ADDR` if the header is absent.
- Compare resolved IP against `CALLBACK_IP_ALLOWLIST`. If not found: return `HttpResponse(status=403)` immediately — do not call `get_response`.
- If `VERIFY_CALLBACK_SOURCE_IP` is `False`: skip the check entirely (passthrough).
- Log rejected requests at WARNING level: `f"Blocked callback from {ip} — not in allowlist"`.

### 10.3 `views.py` — callback views

All views are DRF `APIView` subclasses with `authentication_classes = []` and `permission_classes = []` (Safaricom does not send auth headers — the IP allowlist is the security mechanism).

#### `STKCallbackView`

**POST behaviour:**
1. Parse request body as JSON. On parse failure: log the error, still return 200 (do not expose internal errors to Safaricom).
2. Determine source IP (same logic as middleware, in case middleware is disabled).
3. Create `CallbackLog(callback_type="STK", source_ip=ip, raw_body=body)` and save.
4. Extract `CheckoutRequestID` from `Body.stkCallback.CheckoutRequestID`.
5. If `USE_CELERY` is `True`: call `process_stk_callback.delay(str(callback_log.id))`.
6. If `USE_CELERY` is `False`: call `process_stk_callback(str(callback_log.id))` synchronously.
7. Return `Response({"ResultCode": 0, "ResultDesc": "Accepted"}, status=200)` — **always**, even if steps 3–6 raise exceptions. Exceptions are logged internally.

#### `C2BValidationView`

**POST behaviour:**
1. Log raw payload to `CallbackLog(callback_type="C2B_VALIDATION")`.
2. Fire `c2b_validation_received` signal with the raw payload.
3. **This view may return a non-zero ResultCode.** If no receiver has connected to the signal and overridden the result: default to accepting (`ResultCode: 0`).
4. Signal receivers may return a dict `{"ResultCode": <n>, "ResultDesc": "<desc>"}` to reject the transaction. The view must check for this and return accordingly.
5. Pattern: the view calls signal.send() and inspects return values from receivers.

#### `C2BConfirmationView`

**POST behaviour:**
1. Log raw payload to `CallbackLog(callback_type="C2B_CONFIRMATION")`.
2. Extract `BillRefNumber` (maps to `account_reference`), `TransactionAmount`, `MSISDN`, `TransID`.
3. Dispatch `process_c2b_confirmation.delay(str(callback_log.id))` (or synchronous).
4. Return `{"ResultCode": 0, "ResultDesc": "Accepted"}`, 200 — always.

#### `B2CResultView`

**POST behaviour:**
1. Log raw payload to `CallbackLog(callback_type="B2C_RESULT")`.
2. Extract `ConversationID` from `Result.ConversationID`.
3. Dispatch `process_b2c_result.delay(str(callback_log.id))` (or synchronous).
4. Return `{"ResultCode": 0, "ResultDesc": "Accepted"}`, 200 — always.

#### `B2CTimeoutView`

**POST behaviour:**
1. Log raw payload to `CallbackLog(callback_type="B2C_TIMEOUT")`.
2. Dispatch `process_b2c_timeout.delay(str(callback_log.id))` (or synchronous).
3. Return `{"ResultCode": 0, "ResultDesc": "Accepted"}`, 200 — always.

### 10.4 `tasks.py` — async processing tasks

#### `process_stk_callback(callback_log_id: str)`

Decorated with `@shared_task(bind=True, max_retries=CELERY_TASK_MAX_RETRIES, retry_backoff=CELERY_TASK_RETRY_BACKOFF)`.

**Full behaviour:**
1. Load `CallbackLog` by `id`. If not found: log error and return (do not raise — the task should not retry a missing log).
2. Parse `checkout_request_id` from `callback_log.raw_body["Body"]["stkCallback"]["CheckoutRequestID"]`.
3. Parse `result_code` from `raw_body["Body"]["stkCallback"]["ResultCode"]`.
4. Parse `result_desc` from `raw_body["Body"]["stkCallback"]["ResultDesc"]`.
5. If `result_code == 0` (success): parse `mpesa_receipt_number` from `CallbackMetadata` items where `Name == "MpesaReceiptNumber"`.
6. Enter `with transaction.atomic()`:
   a. `txn = Transaction.objects.select_for_update().get(checkout_request_id=checkout_request_id)`.
   b. If `txn.status in TERMINAL_STATES`: set `callback_log.processed = True`, save, return — **idempotency no-op**.
   c. Set `txn.status = "SUCCESS"` if `result_code == 0`, else `"FAILED"`.
   d. Set `txn.result_code = result_code`, `txn.result_desc = result_desc`.
   e. If success: set `txn.mpesa_receipt_number`.
   f. Set `txn.settled_at = timezone.now()`.
   g. Set `txn.raw_callback_payload = callback_log.raw_body`.
   h. `txn.save()`.
   i. Set `callback_log.related_transaction = txn`, `callback_log.processed = True`, `callback_log.save()`.
7. **Outside the atomic block**: fire signal:
   - `result_code == 0`: `payment_confirmed.send(sender=Transaction, transaction=txn)`
   - otherwise: `payment_failed.send(sender=Transaction, transaction=txn, result_code=result_code, result_desc=result_desc)`
8. On any unexpected exception: call `self.retry(exc=exc)` to re-queue with backoff.

**On `Transaction.DoesNotExist`:** log a warning (`"STK callback received for unknown checkout_request_id {id}"`) and mark `callback_log.error = str(e)`, save, return — do not retry. This happens when a callback arrives before the initiation response is processed.

#### `process_c2b_confirmation(callback_log_id: str)`

1. Load `CallbackLog`.
2. Parse fields: `TransID` → `mpesa_receipt_number`; `TransAmount` → `amount`; `MSISDN` → `phone_number`; `BillRefNumber` → `account_reference`.
3. `with transaction.atomic()`:
   a. Look up existing `Transaction` by `account_reference` and `status="PENDING"`, or create a new one if none found (C2B payments may arrive without a prior `initiate()` call — e.g., customer pays directly via paybill).
   b. If existing and already in terminal state: no-op.
   c. Set `status = "SUCCESS"`, `mpesa_receipt_number`, `settled_at`, `raw_callback_payload`.
   d. Save transaction and link callback log.
4. Outside lock: fire `payment_confirmed`.

#### `process_b2c_result(callback_log_id: str)`

1. Load `CallbackLog`.
2. Parse `ConversationID`, `ResultCode`, `ResultDesc` from payload.
3. `with transaction.atomic()`:
   a. `txn = Transaction.objects.select_for_update().get(conversation_id=conversation_id)`.
   b. If already terminal: no-op.
   c. Set `status = "SUCCESS"` or `"FAILED"` based on `ResultCode`.
   d. Parse `TransactionReceipt` from `ResultParameters` if success.
   e. Save transaction, link callback log.
4. Outside lock: fire `payout_completed` or `payout_failed`.

#### `process_b2c_timeout(callback_log_id: str)`

1. Load `CallbackLog`.
2. Parse `ConversationID` from payload.
3. `with transaction.atomic()`:
   a. `txn = Transaction.objects.select_for_update().get(conversation_id=conversation_id)`.
   b. If already terminal: no-op.
   c. Set `status = "TIMEOUT"`, `settled_at = timezone.now()`.
   d. Save.
4. Outside lock: fire `payout_failed` with `result_code=None, result_desc="Timeout"`.

### 10.5 Idempotency guarantee (summary)

The following combination of mechanisms provides the idempotency guarantee:

1. **Unique constraint** on `checkout_request_id` / `conversation_id` — prevents duplicate rows.
2. **`select_for_update()`** — serializes concurrent callback deliveries for the same row. The second concurrent delivery will block until the first commits, then see the terminal status and exit silently.
3. **Terminal state check** — `if txn.status in TERMINAL_STATES: return` — the explicit guard that makes the no-op path visible and testable.
4. **Celery task retry** — if the task fails mid-way (e.g., DB connection lost after updating status but before saving), retrying is safe because the terminal state check prevents double-settlement.

---

## 11. URL Configuration — `urls.py`

```python
from django.urls import path
from django_mpesa.views import (
    STKCallbackView, C2BValidationView, C2BConfirmationView,
    B2CResultView, B2CTimeoutView,
)

app_name = "django_mpesa"

urlpatterns = [
    path("stk/callback/",   STKCallbackView.as_view(),     name="stk-callback"),
    path("c2b/validate/",   C2BValidationView.as_view(),   name="c2b-validate"),
    path("c2b/confirm/",    C2BConfirmationView.as_view(),  name="c2b-confirm"),
    path("b2c/result/",     B2CResultView.as_view(),        name="b2c-result"),
    path("b2c/timeout/",    B2CTimeoutView.as_view(),       name="b2c-timeout"),
]
```

**Host app wiring:**
```python
# host app urls.py
path("mpesa/", include("django_mpesa.urls")),
```

**Critical:** the full callback URLs registered with Safaricom (in `MPESA` settings) must exactly match the final resolved paths. For the example above: `https://yourapp.com/mpesa/stk/callback/`.

---

## 12. Signals — `signals.py`

### 12.1 Signal definitions

```python
from django.dispatch import Signal

payment_confirmed    = Signal()  # STK Push or C2B settled successfully
payment_failed       = Signal()  # STK Push or C2B settlement failed
c2b_validation_received = Signal()  # C2B validation request received (pre-transaction)
payout_completed     = Signal()  # B2C payout confirmed successful
payout_failed        = Signal()  # B2C payout failed or timed out
reversal_completed   = Signal()  # Reversal confirmed by callback
balance_received     = Signal()  # Account balance callback received
```

### 12.2 Signal kwargs

| Signal | `sender` | Additional kwargs |
|---|---|---|
| `payment_confirmed` | Transaction class | `transaction` |
| `payment_failed` | Transaction class | `transaction`, `result_code`, `result_desc` |
| `c2b_validation_received` | `C2BValidationView` | `raw_payload` |
| `payout_completed` | Transaction class | `transaction` |
| `payout_failed` | Transaction class | `transaction`, `result_code`, `result_desc` |
| `reversal_completed` | Transaction class | `transaction` |
| `balance_received` | `AccountBalanceService` | `raw_payload` |

### 12.3 Firing rules

- All signals except `c2b_validation_received` and `balance_received` are fired **after the `atomic()` block exits** — the DB row lock must be released before signal receivers run.
- Signal receivers must never be called with an uncommitted transaction state.
- Exceptions raised by signal receivers must be caught and logged — they must never propagate back to crash the task.

### 12.4 Example host-app usage

```python
# myapp/receivers.py
from django.dispatch import receiver
from django_mpesa.signals import payment_confirmed, payment_failed

@receiver(payment_confirmed)
def on_payment_confirmed(sender, transaction, **kwargs):
    order = transaction.order
    order.mark_paid()
    Wallet.objects.credit(order.user, transaction.amount)
    send_receipt_sms.delay(transaction.phone_number, transaction.amount)

@receiver(payment_failed)
def on_payment_failed(sender, transaction, result_code, result_desc, **kwargs):
    logger.warning(f"Payment failed: {result_code} {result_desc} for {transaction.id}")
```

---

## 13. Admin — `admin.py`

The library provides optional admin registration via mixins — it does not force-register anything. Host apps opt in.

### 13.1 `MpesaTransactionAdminMixin`

Mix into a `ModelAdmin` to get:
- `list_display`: `id`, `transaction_type`, `status`, `phone_number`, `amount`, `mpesa_receipt_number`, `initiated_at`, `settled_at`.
- `list_filter`: `status`, `transaction_type`, `initiated_at`.
- `search_fields`: `phone_number`, `checkout_request_id`, `conversation_id`, `mpesa_receipt_number`, `account_reference`.
- `readonly_fields`: all fields (transactions must never be edited via admin — the system is the source of truth).
- `ordering`: `["-initiated_at"]`.

### 13.2 `MpesaCallbackLogAdminMixin`

- `list_display`: `id`, `callback_type`, `source_ip`, `processed`, `received_at`, `related_transaction`.
- `list_filter`: `callback_type`, `processed`, `received_at`.
- `readonly_fields`: all fields.

---

## 14. Management Commands

### 14.1 `mpesa_check_config`

**File:** `django_mpesa/management/commands/mpesa_check_config.py`

**Purpose:** Validates the entire `MPESA` settings dict at deploy time. Should be run in CI and as a startup check.

**Checks performed (in order):**

1. `MPESA` key exists in `settings`.
2. `ENV` is `"sandbox"` or `"production"`.
3. `CONSUMER_KEY` and `CONSUMER_SECRET` are resolvable (calling callable if needed) and non-empty.
4. `SHORTCODE` is resolvable and non-empty.
5. For `ENV == "production"`: all callback URLs are HTTPS. Fail if any are HTTP.
6. For `ENV == "sandbox"`: warn (not fail) if callback URLs are `localhost` or `127.0.0.1` (these won't receive real callbacks).
7. `TRANSACTION_MODEL` and `CALLBACK_LOG_MODEL` are set and resolvable via `apps.get_model()`.
8. `TRANSACTION_MODEL` is a subclass of `AbstractMpesaTransaction`.
9. `CALLBACK_LOG_MODEL` is a subclass of `AbstractMpesaCallbackLog`.
10. If `USE_CELERY` is `True`: Celery is importable.
11. `TOKEN_CACHE_TTL_BUFFER` is a positive integer < 3600.
12. `PASSKEY` is set (required for STK Push).
13. `SECURITY_CREDENTIAL` or `INITIATOR_PASSWORD` is set if `INITIATOR_NAME` is set (required for B2C/Reversal).

**Output:**
- Each check prints `[OK]` or `[FAIL] <reason>` to stdout.
- Exits with code `0` if all checks pass, `1` if any check fails.
- Use `--fail-fast` flag to stop at first failure.

---

## 15. Serializers — `serializers.py`

DRF serializers for validating and parsing Daraja callback payloads. Used internally by views before saving to `CallbackLog`.

### 15.1 `STKCallbackSerializer`

Validates the outer envelope of an STK Push callback:

```python
{
    "Body": {
        "stkCallback": {
            "MerchantRequestID": str,
            "CheckoutRequestID": str,
            "ResultCode": int,
            "ResultDesc": str,
            "CallbackMetadata": {...}  # optional, present only on success
        }
    }
}
```

### 15.2 `C2BConfirmationSerializer`

Validates C2B confirmation payload fields: `TransactionType`, `TransID`, `TransTime`, `TransAmount`, `BusinessShortCode`, `BillRefNumber`, `InvoiceNumber`, `OrgAccountBalance`, `ThirdPartyTransID`, `MSISDN`, `FirstName`, `MiddleName`, `LastName`.

### 15.3 `B2CResultSerializer`

Validates B2C result payload: `Result.ResultType`, `Result.ResultCode`, `Result.ResultDesc`, `Result.OriginatorConversationID`, `Result.ConversationID`, `Result.TransactionID`, `Result.ResultParameters`.

**Note:** Serializer validation failure does not prevent the raw payload from being saved to `CallbackLog`. The log is saved first; the serializer is used by the Celery task to parse the already-logged payload.

---

## 16. Testing Module — `django_mpesa/testing/`

This module ships as part of the package so host-app test suites can use the mock client and fixtures without writing their own stubs.

### 16.1 `testing/mock_client.py` — `MockDarajaClient`

A drop-in replacement for `BaseDarajaClient`. Returns configurable canned responses with no network calls.

**Class interface:**

```python
class MockDarajaClient:
    def __init__(self, responses: dict[str, dict] = None, raise_on: dict[str, Exception] = None):
        """
        responses: maps Daraja path → response dict to return.
                   Defaults to realistic success responses for all known paths.
        raise_on:  maps Daraja path → exception instance to raise instead of returning.
                   Useful for testing error-handling paths.
        """

    def post(self, path: str, payload: dict) -> dict:
        """
        If path is in raise_on: raise the configured exception.
        If path is in responses: return the configured dict.
        If path not in either: return the default success response for that path.
        Records all calls to self.calls list for assertion in tests.
        """

    def set_response(self, path: str, response: dict) -> None:
        """Overrides the response for a specific path mid-test."""

    def set_raise(self, path: str, exception: Exception) -> None:
        """Configures an exception to be raised for a specific path."""

    def reset(self) -> None:
        """Clears all custom responses, raises, and call records."""

    @property
    def calls(self) -> list[dict]:
        """Returns list of {"path": ..., "payload": ...} for all calls made."""
```

**Default responses** (schema-accurate):

| Path | Default response |
|---|---|
| `/mpesa/stkpush/v1/processrequest` | `{"ResponseCode": "0", "CheckoutRequestID": "ws_CO_test_123", "MerchantRequestID": "test_merchant_123", "ResponseDescription": "Success. Request accepted for processing"}` |
| `/mpesa/stkpushquery/v1/query` | `{"ResponseCode": "0", "ResultCode": "0", "ResultDesc": "The service request is processed successfully."}` |
| `/mpesa/c2b/v1/registerurl` | `{"ResponseCode": "0", "ResponseDescription": "Success"}` |
| `/mpesa/c2b/v1/simulate` | `{"ResponseCode": "0", "ResponseDescription": "Accept the service request successfully."}` |
| `/mpesa/b2c/v1/paymentrequest` | `{"ResponseCode": "0", "ConversationID": "test_conv_123", "OriginatorConversationID": "test_orig_123", "ResponseDescription": "Accept the service request successfully."}` |
| `/mpesa/transactionstatus/v1/query` | `{"ResponseCode": "0", "ResponseDescription": "Accept the service request successfully."}` |
| `/mpesa/accountbalance/v1/query` | `{"ResponseCode": "0", "ResponseDescription": "Accept the service request successfully."}` |
| `/mpesa/reversal/v1/request` | `{"ResponseCode": "0", "ResponseDescription": "Accept the service request successfully."}` |

### 16.2 `testing/fixtures.py` — pytest fixtures

All fixtures are defined for use with `pytest-django`. Import with `from django_mpesa.testing.fixtures import *` or reference individually.

| Fixture | Scope | Description |
|---|---|---|
| `mock_daraja` | `function` | Yields a `MockDarajaClient` instance, reset between tests. |
| `stk_success_callback` | `function` | Returns realistic STK Push success callback JSON dict. |
| `stk_failure_callback` | `function` | Returns realistic STK Push failure callback JSON dict (`ResultCode: 1032` — request cancelled by user). |
| `c2b_confirmation_payload` | `function` | Returns realistic C2B confirmation payload dict. |
| `b2c_result_success_payload` | `function` | Returns realistic B2C result success payload dict. |
| `b2c_result_failure_payload` | `function` | Returns realistic B2C result failure payload dict. |
| `b2c_timeout_payload` | `function` | Returns realistic B2C timeout payload dict. |
| `pending_stk_transaction` | `function` | Creates and returns a `PENDING` STK Push transaction via factory. Uses `db` fixture. |
| `pending_b2c_transaction` | `function` | Creates and returns a `PENDING` B2C transaction via factory. |

### 16.3 `testing/factories.py` — factory_boy factories

```python
class MpesaTransactionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "<resolved TRANSACTION_MODEL>"

    id = factory.LazyFunction(uuid.uuid4)
    transaction_type = "STK_PUSH"
    status = "PENDING"
    checkout_request_id = factory.Sequence(lambda n: f"ws_CO_test_{n}")
    merchant_request_id = factory.Sequence(lambda n: f"merchant_test_{n}")
    phone_number = "254712345678"
    amount = Decimal("100.00")
    account_reference = "TEST-ORDER"
    transaction_desc = "Test payment"
    initiated_at = factory.LazyFunction(timezone.now)

class MpesaCallbackLogFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "<resolved CALLBACK_LOG_MODEL>"

    id = factory.LazyFunction(uuid.uuid4)
    callback_type = "STK"
    source_ip = "196.201.214.200"
    raw_body = factory.LazyFunction(lambda: {})
    processed = False
    received_at = factory.LazyFunction(timezone.now)
```

---

## 17. Test Suite — `tests/`

### 17.1 `tests/settings.py` — test Django settings

Minimal Django settings for running the test suite without a real project:

```python
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django_mpesa",
    "tests.testapp",  # concrete model subclasses for testing
]
MPESA = {
    "ENV": "sandbox",
    "CONSUMER_KEY": "test_key",
    "CONSUMER_SECRET": "test_secret",
    "SHORTCODE": "174379",
    "PASSKEY": "test_passkey",
    "TRANSACTION_MODEL": "testapp.MpesaTransaction",
    "CALLBACK_LOG_MODEL": "testapp.MpesaCallbackLog",
    "USE_CELERY": False,
    "VERIFY_CALLBACK_SOURCE_IP": False,
}
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
```

### 17.2 Required test cases

#### `test_client/test_auth.py`
- Token is fetched from Daraja and cached on first call.
- Cached token is returned on second call (no second HTTP request).
- Token near expiry (within `TOKEN_CACHE_TTL_BUFFER`) is refreshed.
- On 401 from token endpoint: raises `DarajaAuthError`.
- `invalidate()` clears the cache key.
- Concurrent `get_token()` calls result in exactly one HTTP request (lock test using `threading.Thread`).

#### `test_client/test_base.py`
- Successful POST returns parsed response dict.
- 5xx triggers retry up to `MAX_RETRIES` with backoff, then raises `DarajaAPIError`.
- 4xx raises `DarajaAPIError` immediately with no retry.
- 401 triggers token invalidation and one retry; second 401 raises `DarajaAuthError`.
- 429 raises `DarajaRateLimitError`.
- Timeout raises `DarajaTimeoutError`.
- Sensitive fields are redacted from DEBUG logs.

#### `test_services/test_stk_push.py`
- `initiate()` with valid inputs creates a `PENDING` transaction.
- `initiate()` with phone number `0712345678` normalises to `254712345678`.
- `initiate()` with `account_reference` > 12 chars raises `DarajaValidationError` before any HTTP call.
- `initiate()` with `transaction_desc` > 13 chars raises `DarajaValidationError`.
- `initiate()` with negative `amount` raises `DarajaValidationError`.
- `initiate()` stores `checkout_request_id` from mock response.
- `initiate()` does not create a transaction record if the API call fails.
- `query()` returns the response dict without mutating any DB row.

#### `test_services/test_c2b.py`
- `register_urls()` POSTs the correct payload.
- `simulate()` raises `DarajaConfigError` when `ENV == "production"`.
- `simulate()` succeeds in sandbox.

#### `test_services/test_b2c.py`
- `send_payment()` with valid inputs creates a `PENDING` transaction.
- `send_payment()` with invalid `command_id` raises `DarajaValidationError`.
- `send_payment()` stores `conversation_id` from response.
- Terminal status is not set by `send_payment()` — only by the callback task.

#### `test_callbacks/test_stk_callback.py`
- Valid STK success callback: transaction moves to `SUCCESS`, `mpesa_receipt_number` is set, `payment_confirmed` fires.
- Valid STK failure callback: transaction moves to `FAILED`, `payment_failed` fires.
- Callback for unknown `checkout_request_id`: logs warning, marks callback log with error, does not raise.
- Transaction already in terminal state: callback is no-op, signal does NOT fire again.
- Callback view always returns 200 even when processing raises an exception.
- IP allowlist middleware returns 403 for non-Safaricom IPs when `VERIFY_CALLBACK_SOURCE_IP=True`.

#### `test_callbacks/test_c2b_callbacks.py`
- Valid confirmation creates/updates transaction to `SUCCESS`.
- Validation view fires `c2b_validation_received` signal.
- Validation view accepts response override from signal receiver.

#### `test_callbacks/test_b2c_callbacks.py`
- Valid B2C result: transaction → `SUCCESS`, `payout_completed` fires.
- Failed B2C result: transaction → `FAILED`, `payout_failed` fires.
- Timeout: transaction → `TIMEOUT`, `payout_failed` fires.

#### `test_idempotency.py` — the critical concurrency test

```python
def test_duplicate_callback_does_not_double_settle(db):
    """
    Two threads call process_stk_callback with the same checkout_request_id
    concurrently, using a threading.Barrier to force simultaneous entry.

    Asserts:
    - transaction.status == "SUCCESS" (settled exactly once)
    - transaction.settled_at is set exactly once (not overwritten)
    - payment_confirmed signal fired exactly once (tracked via a mock receiver)
    - No exception raised by either thread
    """
```

This test must use `threading.Thread` and a `threading.Barrier(2)` to force genuine concurrency — sequential calls are not sufficient to catch the race condition.

### 17.3 Coverage requirement

- Minimum 90% line coverage on all files under `django_mpesa/`.
- Coverage measured with `pytest-cov`.
- CI blocks merge if coverage drops below 90%.
- `django_mpesa/testing/` is excluded from the coverage threshold (it's test infrastructure, not production code).

---

## 18. Packaging & Distribution

### 18.1 `pyproject.toml` — full spec

```toml
[project]
name = "django-mpesa"
version = "0.1.0"
description = "A production-hardened Django app for Safaricom's Daraja M-PESA API"
readme = "README.md"
license = { text = "MIT" }
requires-python = ">=3.10"
keywords = ["django", "mpesa", "safaricom", "daraja", "payments", "kenya"]
classifiers = [
    "Development Status :: 4 - Beta",
    "Framework :: Django",
    "Framework :: Django :: 4.2",
    "Framework :: Django :: 5.0",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Topic :: Software Development :: Libraries :: Python Modules",
]
dependencies = [
    "django>=4.2",
    "djangorestframework>=3.14",
    "requests>=2.31",
]

[project.optional-dependencies]
celery = ["celery>=5.3"]
test = [
    "pytest>=7.4",
    "pytest-django>=4.7",
    "pytest-cov>=4.1",
    "factory-boy>=3.3",
    "responses>=0.24",      # HTTP mock for requests
]
docs = ["mkdocs-material>=9.0"]
dev = ["django-mpesa[test,docs]", "pip-audit", "ruff", "mypy"]

[project.urls]
Homepage = "https://github.com/mainfinity/django-mpesa"
Documentation = "https://django-mpesa.readthedocs.io"
Repository = "https://github.com/mainfinity/django-mpesa"
Issues = "https://github.com/mainfinity/django-mpesa/issues"
Changelog = "https://github.com/mainfinity/django-mpesa/blob/main/CHANGELOG.md"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["django_mpesa"]
```

### 18.2 Versioning policy

- Semantic versioning: `MAJOR.MINOR.PATCH`.
- `0.x.y` — model/settings schema may still change without a major bump (pre-1.0 contract).
- `1.0.0` — only tagged after Zaruni has run the library in production for a full billing cycle with no hotfix to the idempotency path.
- Every release is accompanied by a `CHANGELOG.md` entry.
- Version is the single source of truth in `pyproject.toml`. `django_mpesa/__init__.py` reads it via `importlib.metadata.version("django-mpesa")`.

### 18.3 `apps.py` — `MpesaConfig`

```python
class MpesaConfig(AppConfig):
    name = "django_mpesa"
    default_auto_field = "django.db.models.BigAutoField"
    verbose_name = "M-PESA"

    def ready(self):
        # Import signal receivers (none shipped by the library — 
        # this is a hook for host apps, not wired here).
        pass
```

---

## 19. CI/CD

### 19.1 `test.yml` — PR test pipeline

**Trigger:** every push and pull request.

**Matrix:**
```
python-version: [3.10, 3.11, 3.12]
django-version: [4.2, 5.0]
```
(6 combinations total)

**Steps:**
1. Checkout code.
2. Set up Python.
3. Install dependencies: `pip install -e ".[test]" Django=={django-version}`.
4. Run `python manage.py mpesa_check_config --settings=tests.settings` against the test settings — fails build if config check fails.
5. Run `pytest --cov=django_mpesa --cov-report=xml --cov-fail-under=90`.
6. Upload coverage report to Codecov.

### 19.2 `publish.yml` — PyPI release pipeline

**Trigger:** push of a tag matching `v*.*.*`.

**Steps:**
1. Checkout code.
2. Build: `python -m build`.
3. Publish to PyPI via `pypa/gh-action-pypi-publish` using a stored PyPI API token secret.

### 19.3 Dependency audit

- `pip-audit` runs on every PR as a separate step.
- Build does not block on audit failures (warning only) — but creates an issue automatically if new vulnerabilities are found.

---

## 20. Documentation

All documentation is written in Markdown and built with MkDocs Material.

### 20.1 Required pages

| File | Contents |
|---|---|
| `docs/index.md` | What the library is, what Daraja APIs it covers, compatibility matrix, quick install snippet. |
| `docs/quickstart.md` | Step-by-step: install → add to `INSTALLED_APPS` → subclass models → configure settings → wire URLs → call `STKPushService.initiate()` → handle `payment_confirmed` signal. Target: working STK Push in < 10 minutes. |
| `docs/settings.md` | Full settings reference table (same as §4.2 of this spec). |
| `docs/models.md` | Full field reference for abstract models. Example concrete subclass. |
| `docs/callbacks.md` | How callbacks work, the log-then-acknowledge-then-process pattern, idempotency explanation. |
| `docs/signals.md` | Signal catalog, kwargs, example receivers. |
| `docs/testing.md` | How to use `MockDarajaClient`, available fixtures, how to write an idempotency test. |
| `docs/security.md` | Credential setup, `SECURITY_CREDENTIAL` generation, IP allowlist, HTTPS requirement. |
| `docs/services/stk_push.md` | Full `STKPushService` API reference with examples. |
| `docs/services/c2b.md` | Full `C2BService` API reference with examples. |
| `docs/services/b2c.md` | Full `B2CService` API reference with examples. |
| `docs/services/transaction_status.md` | Full `TransactionStatusService` reference. |
| `docs/services/account_balance.md` | Full `AccountBalanceService` reference. |
| `docs/services/reversal.md` | Full `ReversalService` reference. |

### 20.2 Quality bar

- `quickstart.md` must be tested against a real install on every release — a contributor must follow it from scratch and confirm it works in < 10 minutes.
- Code examples in docs must be copy-pasteable and functional.

---

## 21. Security Requirements

| # | Requirement |
|---|---|
| SEC-01 | Credentials (`CONSUMER_KEY`, `CONSUMER_SECRET`, `PASSKEY`, `INITIATOR_PASSWORD`) must be sourced from environment variables or a secrets manager. The library must support callable resolution so secrets are never literals in source code. |
| SEC-02 | `SECURITY_CREDENTIAL` for B2C/Reversal must be the initiator password RSA-encrypted with Safaricom's production or sandbox public certificate. The library must never accept or transmit a plaintext initiator password to Daraja. |
| SEC-03 | All registered callback URLs must be HTTPS in production. `mpesa_check_config` must fail the build if any callback URL is HTTP when `ENV == "production"`. |
| SEC-04 | Callback views must validate the source IP against Safaricom's published IP allowlist by default. This is the primary authentication mechanism for inbound callbacks (Safaricom does not send auth tokens). |
| SEC-05 | Callback views must never return stack traces, exception messages, or internal error details in the HTTP response body. Internal errors are logged and a generic `{"ResultCode": 0}` is always returned to Safaricom. |
| SEC-06 | Outbound request logs must redact sensitive fields: `Password`, `SecurityCredential`, `Passkey`, `InitiatorPassword`. Redaction must happen before the log line is written, not after. |
| SEC-07 | Phone numbers in `CallbackLog.raw_body` and `Transaction.raw_callback_payload` are stored as received from Safaricom. Logging of these fields must use DEBUG level only, not INFO/WARNING. |
| SEC-08 | `DEBUG=False` must be enforced in production. The library itself must not change the Django `DEBUG` setting but `mpesa_check_config` should warn if `DEBUG=True` in production (checked via `settings.DEBUG`). |
| SEC-09 | The dependency list must be scanned with `pip-audit` on every CI run. |
| SEC-10 | All dependencies in `pyproject.toml` must specify minimum version constraints. No unconstrained `*` dependencies. |

---

## 22. Non-Functional Requirements

### 22.1 Compatibility

| Requirement | Detail |
|---|---|
| Python versions | 3.10, 3.11, 3.12 |
| Django versions | 4.2 LTS, 5.0 |
| DRF versions | ≥ 3.14 |
| requests versions | ≥ 2.31 |
| Celery versions | ≥ 5.3 (optional dependency) |
| Database backends | Any backend supported by Django (PostgreSQL required for production — `select_for_update` behaviour is most reliable on PostgreSQL; SQLite is acceptable for tests) |

### 22.2 Performance

| Requirement | Detail |
|---|---|
| Token caching | No more than one Daraja OAuth call per token lifetime per environment, regardless of concurrent request volume. |
| Callback response time | Callback views must return a response within 200 ms under normal conditions (just logging + task dispatch — no business logic in the request path). |
| Database lock hold time | The `select_for_update` lock must be held for the minimum time: only the status check and the `txn.save()` call. Signal dispatch happens after the lock is released. |

### 22.3 Observability

- All significant events must be logged using Python's standard `logging` module under the `django_mpesa` logger namespace.
- Log levels: DEBUG for request/response bodies (redacted), INFO for transaction state transitions, WARNING for unexpected states (unknown IDs, IP rejections), ERROR for processing failures.
- No `print()` statements in library code.

### 22.4 Build order (implementation sequence)

The following sequence is required — later items depend on earlier ones:

1. `client/auth.py` + `client/base.py` + `client/http.py` — foundation layer
2. `exceptions.py`, `validators.py` — no dependencies
3. `models.py` abstract bases + test app concrete models
4. `conf.py` settings resolver + `apps.py`
5. `STKPushService` + `STKCallbackView` + `process_stk_callback` task + idempotency test
6. `C2BService` + `C2BValidationView` + `C2BConfirmationView` + `process_c2b_confirmation` task
7. `B2CService` + `B2CResultView` + `B2CTimeoutView` + `process_b2c_result` + `process_b2c_timeout`
8. `TransactionStatusService`, `AccountBalanceService`, `ReversalService`
9. `middleware.py`, `admin.py`, `management/commands/mpesa_check_config.py`
10. `testing/` module (mock client, fixtures, factories)
11. Full test suite + coverage enforcement
12. `pyproject.toml`, CI workflows, documentation

Steps 1–5 are the `v0.1.0` milestone (STK Push end-to-end). Steps 6–7 are `v0.2.0`. Steps 8–12 are `v0.3.0` / pre-`1.0.0`.

---

## 23. Out of Scope

The following are explicitly excluded from this library and belong in the host application:

- Wallet, ledger, or balance management
- User authentication, authorization, or permissions
- SMS, email, or push notification delivery
- Order or invoice management
- Frontend or mobile client code
- Multi-tenancy (multiple Safaricom shortcodes within one Django instance) — deferred post-`1.0.0`
- Webhooks or event streaming to third-party systems
- Transaction reporting, analytics, or dashboards
- Handling of M-PESA APIs not listed in §9 (e.g., M-PESA Express Query is covered; newer Daraja 2.0 APIs are deferred)

---

## 24. Constraints & Assumptions

| Constraint | Detail |
|---|---|
| No migrations | The library ships zero Django migrations. Abstract models generate no migrations. Host apps own their migrations entirely. |
| No concrete model imports | All model access in library code goes through `django.apps.apps.get_model()`. Direct imports of concrete models are forbidden in library code. |
| No URL namespace conflicts | The library's URL patterns are namespaced under `app_name = "django_mpesa"`. The host app chooses the URL prefix. |
| DRF is a hard dependency | Callback views use DRF `APIView` and `Response`. DRF is always installed. |
| Celery is optional | Removing Celery from a project must not break the library. `USE_CELERY = False` is fully supported. |
| PostgreSQL in production | `select_for_update()` is used for idempotency. SQLite supports this in WAL mode but is not recommended in production for this library. |
| Python 3.10+ | Uses `match/case` syntax, `X | Y` union types, and other 3.10+ features. |
| Safaricom API contract | The library targets Daraja 1.0 API endpoints as documented at https://developer.safaricom.co.ke. If Safaricom changes endpoint URLs or payload schemas, the library must be updated. |

---

## 25. Glossary

| Term | Definition |
|---|---|
| **Daraja** | Safaricom's API gateway for M-PESA integrations. |
| **STK Push** | "SIM Toolkit Push" — a Daraja API that triggers a payment prompt on the customer's phone. Also called "Lipa Na M-PESA Online". |
| **C2B** | Customer to Business — a Daraja API for receiving payments from customers to a business paybill or till number. |
| **B2C** | Business to Customer — a Daraja API for sending money from a business account to customer phone numbers (payouts, salaries). |
| **Idempotency** | The property that applying an operation multiple times has the same effect as applying it once. In this library: processing the same callback twice produces the same final transaction state as processing it once. |
| **Shortcode** | Safaricom's numeric identifier for a business's M-PESA account (paybill or till number). |
| **Passkey** | A secret string provided by Safaricom, used with the shortcode and a timestamp to generate the STK Push password. |
| **Security Credential** | The initiator password encrypted with Safaricom's RSA public certificate. Used for B2C and Reversal APIs. |
| **Initiator** | The API operator name configured in Safaricom's M-PESA portal, used for B2C and Reversal APIs. |
| **Terminal state** | A transaction status from which no further transitions are valid: `SUCCESS`, `FAILED`, `TIMEOUT`, `REVERSED`. |
| **Host app** | The Django project that installs and uses `django-mpesa`. |
| **Abstract model** | A Django model with `class Meta: abstract = True` — generates no database table, must be subclassed. |
| **CallbackLog** | The raw audit record of every inbound Safaricom callback, stored before any business logic runs. |
| **`select_for_update()`** | A Django ORM method that acquires a database row-level lock inside a transaction, preventing concurrent writers from reading stale data. |

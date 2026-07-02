# django-mpesa — Technical Design Document

**Version:** 1.0
**Date:** 2026-07-01
**Author:** Daniel Maina / Mainfinity
**Status:** Draft — approved for implementation after requirements sign-off

> This document describes *how* the system is built. The requirements document (`specs/requirements.md`) describes *what* it must do. Where the two conflict, the requirements document wins and this document must be updated.

---

## Table of Contents

1. [System Architecture](#1-system-architecture)
2. [Configuration System Design](#2-configuration-system-design)
3. [Data Model Design](#3-data-model-design)
4. [Client Layer Design](#4-client-layer-design)
5. [Service Layer Design](#5-service-layer-design)
6. [Callback Handling Design](#6-callback-handling-design)
7. [Middleware Design](#7-middleware-design)
8. [Signals Design](#8-signals-design)
9. [Exception Design](#9-exception-design)
10. [Validators Design](#10-validators-design)
11. [Serializers Design](#11-serializers-design)
12. [Admin Design](#12-admin-design)
13. [Testing Architecture](#13-testing-architecture)
14. [Packaging & CI/CD Design](#14-packaging--cicd-design)
15. [Documentation Site Design](#15-documentation-site-design)

---

## 1. System Architecture

### 1.1 High-level overview

`django-mpesa` sits between a host Django application and Safaricom's Daraja API. It owns two communication directions:

- **Outbound:** The host app calls a service class method (e.g. `STKPushService.initiate()`). The library authenticates, builds the request, POST to Daraja, creates a transaction record, and returns it.
- **Inbound:** Safaricom POSTs a callback to a registered URL. The library logs it raw, acknowledges immediately, and processes asynchronously — updating the transaction and firing a signal the host app listens to.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          HOST APPLICATION                               │
│                                                                         │
│   views / tasks ──► STKPushService ──► (outbound)                      │
│   signal receivers ◄── payment_confirmed / payment_failed ◄── (inbound)│
└────────────────────────────┬───────────────────────────────────────────┘
                             │  composes
                    ┌────────▼────────┐
                    │  Service Layer  │   STKPushService, C2BService,
                    │  services/      │   B2CService, TransactionStatus,
                    └────────┬────────┘   AccountBalance, ReversalService
                             │  composes
                    ┌────────▼────────┐
                    │  Client Layer   │   BaseDarajaClient, TokenManager,
                    │  client/        │   requests.Session
                    └────────┬────────┘
                             │  HTTP
                    ┌────────▼────────┐
                    │  Daraja API     │   sandbox.safaricom.co.ke
                    │  (Safaricom)    │   api.safaricom.co.ke
                    └─────────────────┘

─────────────────── inbound callback path ────────────────────────────────

    Safaricom POST
         │
    ┌────▼────────────────────────────┐
    │  MpesaCallbackIPAllowlistMiddleware  │   middleware.py
    └────┬────────────────────────────┘
         │  (403 if not in allowlist)
    ┌────▼────────────────────────────┐
    │  Callback View                  │   views.py (DRF APIView)
    │  - log raw → CallbackLog        │
    │  - dispatch task                │
    │  - return 200 immediately       │
    └────┬────────────────────────────┘
         │  async (Celery) or sync
    ┌────▼────────────────────────────┐
    │  Processing Task                │   tasks.py
    │  - select_for_update()          │
    │  - idempotency check            │
    │  - update Transaction           │
    │  - fire signal (outside lock)   │
    └─────────────────────────────────┘
```

### 1.2 Layer responsibilities

| Layer | Files | Responsibility |
|---|---|---|
| Configuration | `conf.py`, `apps.py` | Resolve settings, validate on startup |
| Client | `client/auth.py`, `client/base.py`, `client/http.py` | OAuth token lifecycle, HTTP retry/backoff, outbound request execution |
| Services | `services/*.py` | Validate inputs, build Daraja payloads, create transaction records |
| Callback | `views.py`, `tasks.py` | Receive, log, acknowledge, and idempotently settle inbound callbacks |
| Middleware | `middleware.py` | IP allowlist enforcement |
| Models | `models.py` | Abstract data structures, status state machine |
| Signals | `signals.py` | Contract between the library and the host app at settlement time |
| Support | `exceptions.py`, `validators.py`, `serializers.py`, `admin.py` | Cross-cutting concerns |
| Testing | `testing/` | Mock client, fixtures, factories for host-app and library tests |

### 1.3 Dependency graph

Arrows mean "imports / depends on":

```
conf.py          ◄── (everything)
exceptions.py    ◄── client/, services/, views/, tasks/, validators/
validators.py    ◄── services/
models.py        ◄── views/, tasks/, services/, admin/
signals.py       ◄── tasks/
client/auth.py   ◄── client/base.py
client/http.py   ◄── client/base.py
client/base.py   ◄── services/
services/        ◄── views/ (for URL building only — callback URLs from conf)
views.py         ◄── tasks/ (dispatch), serializers/, models/
tasks.py         ◄── models/, signals/
middleware.py    ◄── conf.py
```

**Critically: `tasks.py` does NOT import from `services/`.** Tasks read directly from models. Services are for initiating outbound calls; tasks are for processing inbound callbacks. They are parallel tracks that share models and signals but never call each other.

### 1.4 External dependencies and why

| Package | Why it's needed | Why alternatives were rejected |
|---|---|---|
| `djangorestframework` | Callback views use `APIView` for clean request parsing, permission composition, and `Response` objects. The `@api_view` decorator pattern is insufficient because views need class-level attribute overrides (`authentication_classes = []`). | Writing raw Django views would require reimplementing content negotiation and error formatting. |
| `requests` | Outbound HTTP to Daraja. Synchronous, battle-tested, supports session-level retry adapters. | `httpx` is async-first; since Daraja calls are made in Django views/management commands (sync context), `requests` is a better fit without requiring ASGI. |
| `celery` (optional) | Async task queue for processing callbacks after acknowledging Safaricom. | Django's built-in async views don't work here — Safaricom needs a synchronous 200 response before the task starts. Celery is the standard Django solution. Marked optional so small projects can run synchronously. |

### 1.5 What the library deliberately does NOT own

- **Django cache backend** — uses whatever `TOKEN_CACHE_ALIAS` points to. No opinion on Redis vs Memcached vs LocMemCache.
- **Database** — abstract models; host app chooses DB. PostgreSQL is recommended for `select_for_update` reliability.
- **Task broker** — Celery is optional and the broker (Redis, RabbitMQ) is entirely the host app's concern.
- **HTTPS termination** — handled by the reverse proxy (Caddy, Nginx, Cloudflare). The library only validates that callback URLs are configured as HTTPS.

---

## 2. Configuration System Design

### 2.1 Design decision: single dict, DRF-style resolver

All settings live under one top-level `MPESA` key. The resolver object `mpesa_settings` (in `conf.py`) wraps this dict and provides:

- Attribute access with defaults: `mpesa_settings.MAX_RETRIES` returns `3` if not set
- Callable resolution: if the stored value is callable, it is invoked and its return value used
- Eager validation of required keys on first access, not at import time (allows the module to be imported without a full Django setup, e.g. in the management command help text)

This pattern is copied directly from DRF's `api_settings` object (`rest_framework/settings.py`). It is the established Django community solution for library configuration — no need to invent something new.

### 2.2 `MpesaSettings` class internals

```python
# conf.py

DEFAULTS = {
    "ENV": "sandbox",
    "TOKEN_CACHE_ALIAS": "default",
    "TOKEN_CACHE_TTL_BUFFER": 60,
    "REQUEST_TIMEOUT": 30,
    "MAX_RETRIES": 3,
    "RETRY_BACKOFF_FACTOR": 0.5,
    "VERIFY_CALLBACK_SOURCE_IP": True,
    "TRUST_FORWARDED_FOR": False,
    "FORWARDED_FOR_TRUSTED_PROXIES": [],
    "CALLBACK_IP_ALLOWLIST": [...],  # Safaricom's published IPs
    "USE_CELERY": True,
    "CELERY_TASK_MAX_RETRIES": 5,
    "CELERY_TASK_RETRY_BACKOFF": True,
    # No defaults for credentials or model strings — absence must error
}

REQUIRED = {
    "CONSUMER_KEY", "CONSUMER_SECRET", "SHORTCODE",
    "TRANSACTION_MODEL", "CALLBACK_LOG_MODEL",
}

CALLABLE_SETTINGS = {
    "CONSUMER_KEY", "CONSUMER_SECRET", "SHORTCODE", "PASSKEY",
    "INITIATOR_NAME", "INITIATOR_PASSWORD", "SECURITY_CREDENTIAL",
}

class MpesaSettings:
    def __init__(self, user_settings=None, defaults=None):
        self._user_settings = user_settings or {}
        self._defaults = defaults or DEFAULTS
        self._cache = {}

    def __getattr__(self, attr):
        if attr not in DEFAULTS and attr not in REQUIRED:
            raise AttributeError(f"Invalid mpesa setting: {attr!r}")
        if attr in self._cache:
            return self._cache[attr]

        try:
            val = self._user_settings[attr]
        except KeyError:
            if attr in REQUIRED:
                raise DarajaConfigError(f"MPESA[{attr!r}] is required but not set.")
            val = self._defaults[attr]

        if attr in CALLABLE_SETTINGS and callable(val):
            val = val()

        self._cache[attr] = val
        return val

    def reload(self):
        """Clears the internal cache. Called by setting_changed signal in tests."""
        self._cache.clear()
        self._user_settings = getattr(django_settings, "MPESA", {})


mpesa_settings = MpesaSettings(
    user_settings=getattr(django_settings, "MPESA", {}),
    defaults=DEFAULTS,
)
```

### 2.3 Cache invalidation in tests

Django's test runner fires `setting_changed` when `@override_settings` is used. `conf.py` connects to this signal to call `mpesa_settings.reload()`, so test overrides are reflected immediately:

```python
from django.test.signals import setting_changed

def _reload_mpesa_settings(*, setting, **kwargs):
    if setting == "MPESA":
        mpesa_settings.reload()

setting_changed.connect(_reload_mpesa_settings)
```

### 2.4 `apps.py` — `MpesaConfig`

`MpesaConfig.ready()` is the single startup hook. It does two things:

1. Imports `django_mpesa.conf` to connect the `setting_changed` listener (the import itself registers the signal handler).
2. Does **not** run `mpesa_check_config` automatically — that is the management command's job. `ready()` must not fail silently or raise on misconfiguration; that would break the Django startup entirely if a host app misconfigures the library. The management command is the loud failure path; `ready()` is silent.

```python
class MpesaConfig(AppConfig):
    name = "django_mpesa"
    default_auto_field = "django.db.models.BigAutoField"
    verbose_name = "M-PESA"

    def ready(self):
        import django_mpesa.conf  # noqa: F401 — registers setting_changed handler
```

### 2.5 Base URL resolution

The base URL is resolved once per request from `mpesa_settings.ENV`:

```python
BASE_URLS = {
    "sandbox": "https://sandbox.safaricom.co.ke",
    "production": "https://api.safaricom.co.ke",
}

def get_base_url() -> str:
    return BASE_URLS[mpesa_settings.ENV]
```

This is a module-level function, not a class attribute, so it re-reads the setting on every call. This matters in tests where `ENV` is overridden between test cases.

---

## 3. Data Model Design

### 3.1 Abstract model strategy

The library ships zero concrete models. Every model is abstract (`class Meta: abstract = True`). The host app subclasses, adds domain fields, and runs its own `makemigrations`. The library accesses the concrete model at runtime via:

```python
from django.apps import apps

def get_transaction_model():
    app_label, model_name = mpesa_settings.TRANSACTION_MODEL.rsplit(".", 1)
    return apps.get_model(app_label, model_name)
```

This function is called at use-time (not import-time) so it works even when the Django app registry is not yet ready during import. It is defined in `models.py` and imported by `views.py`, `tasks.py`, and `services/`.

### 3.2 ER diagram

```
┌──────────────────────────────────────┐
│       AbstractMpesaTransaction       │
│──────────────────────────────────────│
│ PK  id                (UUID)         │
│     transaction_type  (CharField)    │
│     status            (CharField)    │
│ UQ  checkout_request_id (CharField)  │  ← STK Push idempotency key
│     merchant_request_id (CharField)  │
│ UQ  conversation_id   (CharField)    │  ← B2C/Reversal idempotency key
│     originator_conv_id (CharField)   │
│     mpesa_receipt_number (CharField) │
│     phone_number      (CharField)    │
│     amount            (Decimal)      │
│     account_reference (CharField)    │
│     transaction_desc  (CharField)    │
│     result_code       (IntegerField) │
│     result_desc       (TextField)    │
│     raw_callback_payload (JSONField) │
│     initiated_at      (DateTime)     │
│     settled_at        (DateTime)     │
│     idempotency_locked (BooleanField)│
└──────────────────────────────────────┘
              │  1
              │  referenced by
              │  0..*
┌──────────────────────────────────────┐
│       AbstractMpesaCallbackLog       │
│──────────────────────────────────────│
│ PK  id                (UUID)         │
│     callback_type     (CharField)    │
│     source_ip         (IPField)      │
│     raw_body          (JSONField)    │
│ FK  related_transaction (FK, null)   │  ← linked after processing
│     processed         (BooleanField) │
│     error             (TextField)    │
│     received_at       (DateTime)     │
└──────────────────────────────────────┘
```

The FK from `CallbackLog → Transaction` is nullable because:
- The log is written before the transaction is looked up (the whole point is to log unconditionally).
- If no matching transaction is found (e.g. callback arrives before initiation completes), the log still exists with `related_transaction = null`.

### 3.3 Status state machine

Transitions are enforced at the application layer (task code), not at the DB layer. There is no `FSMField` dependency — keeping the state machine explicit in the task code makes it readable and testable without extra libraries.

```
                    ┌─────────┐
          initiate()│         │
    ─────────────►  │ PENDING │
                    └────┬────┘
                         │  callback arrives
                    ┌────▼────┐
                    │PROCESSING│  (set inside select_for_update, immediately
                    └────┬─────┘   before final status write — optional fencing)
                         │
              ┌──────────┼──────────┐
              │          │          │
         ┌────▼───┐  ┌───▼───┐  ┌──▼─────┐
         │SUCCESS │  │FAILED │  │TIMEOUT │
         └────┬───┘  └───────┘  └────────┘
              │  reverse()
         ┌────▼────┐
         │REVERSED │
         └─────────┘
```

**Rules:**
- Any transition into `SUCCESS`, `FAILED`, `TIMEOUT`, or `REVERSED` is terminal — no further transitions are allowed.
- `PROCESSING` is an intermediate state set inside the `select_for_update` block before writing the final status. It serves as a fencing token: if two concurrent tasks both pass the `PENDING` check, the one that loses the race sees `PROCESSING` (not a terminal state) but the unique constraint and row lock still prevent double-settlement. In practice `select_for_update` serialises the two, so only one sees `PENDING`.
- `REVERSED` can only be reached from `SUCCESS` — you cannot reverse a failed or timed-out transaction.

### 3.4 Field design rationale

| Field | Rationale |
|---|---|
| `id` as UUID | Safaricom's own IDs (`CheckoutRequestID`, `ConversationID`) are not suitable as PKs — they contain environment-specific prefixes and could theoretically collide across environments. UUID is safer and reveals nothing about volume. |
| `amount` as `DecimalField` | Floating-point binary representation of money is a well-known bug class. `Decimal` is exact. Safaricom's API also accepts integer amounts (whole KES) — the `Decimal` type makes it explicit that precision is intentional. |
| `checkout_request_id` with `unique=True, null=True` | `unique=True` is the DB-level deduplication guard. `null=True` is required because B2C transactions don't have a `checkout_request_id`. Django allows multiple `null` values for a unique field — nulls don't violate uniqueness in SQL. |
| `raw_callback_payload` on Transaction | Storing the full callback body on the transaction row means one join-free query retrieves everything needed for audit or support. The same payload is also on `CallbackLog`, but the transaction-level copy is convenient for admin views. |
| `idempotency_locked` | A boolean fencing token. Inside the `atomic()` block, it's set to `True` before writing the terminal status, then cleared. If a second concurrent task reads `idempotency_locked=True`, it knows another task is mid-settlement and can exit safely. This is a belt-and-suspenders addition — `select_for_update` already serialises access, but this makes the intent explicit in the data. |
| `settled_at` | Set exactly once when entering a terminal state. Never overwritten. Used for SLA monitoring (time from `initiated_at` to `settled_at`) and reconciliation queries. |

### 3.5 Model access pattern in library code

All library code that needs the transaction model follows this pattern:

```python
# At the top of tasks.py, views.py, services/*.py:
from django_mpesa.models import get_transaction_model, get_callback_log_model

# Inside a function/method (never at module level):
Transaction = get_transaction_model()
CallbackLog = get_callback_log_model()

txn = Transaction.objects.get(checkout_request_id=cid)
```

**Never** do this in library code:
```python
# WRONG — direct import of a concrete model
from myapp.models import MpesaTransaction  # would hard-code the host app
```

### 3.6 Database indexes

The following indexes are defined on the abstract model and inherited by concrete subclasses:

```python
class Meta:
    abstract = True
    ordering = ["-initiated_at"]
    indexes = [
        models.Index(fields=["status"], name="%(app_label)s_%(class)s_status_idx"),
        models.Index(fields=["phone_number"], name="%(app_label)s_%(class)s_phone_idx"),
        models.Index(fields=["initiated_at"], name="%(app_label)s_%(class)s_initiated_idx"),
    ]
```

`checkout_request_id` and `conversation_id` are indexed automatically by their `unique=True` constraint.

---

## 4. Client Layer Design

### 4.1 Responsibility split across three files

| File | What it owns |
|---|---|
| `client/http.py` | A configured `requests.Session` — transport-level retry on TCP/TLS failures only |
| `client/auth.py` | OAuth token lifecycle — fetch, cache, invalidate, stampede prevention |
| `client/base.py` | Application-level HTTP execution — auth header, retry on 5xx, 401 re-auth, error mapping |

The three layers are separated so they can be tested and replaced independently. A test can inject a mock session into `BaseDarajaClient` without touching `TokenManager`, and vice versa.

### 4.2 `client/http.py` — session factory

```python
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def get_session() -> requests.Session:
    session = requests.Session()
    # Transport-level retry: connection errors and read errors only.
    # NOT on HTTP status codes — those are handled at the application layer.
    retry = Retry(
        total=2,
        connect=2,
        read=2,
        status=0,           # don't retry on HTTP errors here
        raise_on_status=False,
        backoff_factor=0.3,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({
        "User-Agent": f"django-mpesa/{get_version()}",
        "Accept": "application/json",
    })
    return session
```

**Why two retry layers?** Transport retries (in `http.py`) handle TCP resets and TLS handshake failures — conditions where no HTTP response was received at all. Application retries (in `base.py`) handle Daraja returning a 5xx — conditions where an HTTP response was received but indicated a server error. These are distinct failure modes and must not be compounded (total retry count would multiply unexpectedly).

### 4.3 `client/auth.py` — `TokenManager` flow

#### Token fetch sequence diagram

```
caller            TokenManager         Django Cache         Daraja OAuth
  │                    │                    │                    │
  │  get_token()       │                    │                    │
  │──────────────────► │                    │                    │
  │                    │  cache.get(key)    │                    │
  │                    │──────────────────► │                    │
  │                    │  hit: return token │                    │
  │                    │◄─────────────────  │                    │
  │  token             │                    │                    │
  │◄─────────────────  │                    │                    │
  │                    │                    │                    │
  │  get_token()       │   [cold start]     │                    │
  │──────────────────► │                    │                    │
  │                    │  cache.get(key)    │                    │
  │                    │──────────────────► │                    │
  │                    │  miss              │                    │
  │                    │◄─────────────────  │                    │
  │                    │  cache.add(lock)   │                    │
  │                    │──────────────────► │                    │
  │                    │  True (lock held)  │                    │
  │                    │◄─────────────────  │                    │
  │                    │                    │  GET /oauth/...    │
  │                    │────────────────────┼──────────────────► │
  │                    │                    │  {access_token,    │
  │                    │◄───────────────────┼───expires_in}      │
  │                    │  cache.set(key,    │                    │
  │                    │    token, ttl)     │                    │
  │                    │──────────────────► │                    │
  │                    │  cache.delete(lock)│                    │
  │                    │──────────────────► │                    │
  │  token             │                    │                    │
  │◄─────────────────  │                    │                    │
```

#### Stampede prevention detail

`cache.add(key, value, timeout)` is an atomic "set if not exists" operation supported by all Django cache backends. It returns `True` if the key was set (lock acquired), `False` if the key already existed (another process holds the lock). This prevents the thundering herd problem where 50 concurrent requests all miss the cache simultaneously and each fires an OAuth request.

The loser processes sleep and retry `get_token()`. By the time they retry, the winner has stored the token in cache and they get a cache hit. If the lock holder crashes (uncaught exception), the lock expires automatically after 10 seconds — the next caller will acquire it and fetch a fresh token.

#### TTL calculation

```python
effective_ttl = expires_in - TOKEN_CACHE_TTL_BUFFER
# expires_in is typically 3599 seconds from Safaricom
# default buffer is 60 seconds
# effective_ttl = 3539 seconds ≈ 59 minutes
```

The buffer prevents using a token that expires between the cache check and the API call. Without the buffer, a token cached for exactly `expires_in` seconds could be valid at cache-read time but expired by the time Daraja processes the request.

### 4.4 `client/base.py` — `BaseDarajaClient` flow

#### `post()` method decision tree

```
post(path, payload)
    │
    ├── get token from TokenManager
    │
    ├── build URL = base_url + path
    │
    ├── log DEBUG: POST {url} payload={redacted}
    │
    ├── execute session.post(url, json=payload, timeout=REQUEST_TIMEOUT)
    │
    ├── response.status_code == 401?
    │   ├── YES (first time): token_manager.invalidate() → retry once
    │   └── YES (second time): raise DarajaAuthError
    │
    ├── response.status_code == 429?
    │   └── raise DarajaRateLimitError
    │
    ├── response.status_code >= 500?
    │   ├── attempt < MAX_RETRIES: sleep(backoff) → retry
    │   └── exhausted: raise DarajaAPIError
    │
    ├── response.status_code >= 400 (not 401, 429)?
    │   └── raise DarajaAPIError immediately — no retry
    │
    ├── requests.Timeout raised?
    │   └── raise DarajaTimeoutError
    │
    ├── response.status_code 2xx:
    │   ├── parse JSON
    │   ├── response contains "errorCode"? → raise DarajaAPIError
    │   └── return parsed dict
    │
    └── log DEBUG: Response {status}: {body[:500]}
```

#### Payload redaction

```python
SENSITIVE_KEYS = frozenset({
    "Password", "SecurityCredential", "Passkey", "InitiatorPassword"
})

def _redact(payload: dict) -> dict:
    return {
        k: "***" if k in SENSITIVE_KEYS else v
        for k, v in payload.items()
    }
```

Redaction is applied only to the log line — the actual outbound payload is never modified.

#### Composition over inheritance

Services do not subclass `BaseDarajaClient`. They hold a reference to it:

```python
class STKPushService:
    def __init__(self, client: BaseDarajaClient = None):
        self.client = client or BaseDarajaClient()
```

This means:
- A test can pass a `MockDarajaClient` without any `unittest.mock.patch`.
- `BaseDarajaClient` can be replaced entirely for a different HTTP library without touching the service classes.
- `BaseDarajaClient` is independently unit-testable with a mock `requests.Session`.

---

## 5. Service Layer Design

### 5.1 Common service pattern

Every service class follows the same structural pattern. This makes them predictable for contributors and testable in isolation:

```python
class XxxService:
    def __init__(self, client: BaseDarajaClient = None):
        # Client is injectable for testing. Default creates a real client.
        self.client = client or BaseDarajaClient()

    def some_method(self, ...):
        # 1. Validate all inputs — raise DarajaValidationError before touching network
        # 2. Build the Daraja payload dict
        # 3. Call self.client.post(path, payload)
        # 4. Parse the response
        # 5. Create/return a Transaction record if this is an initiating call
        # 6. Return raw dict if this is a query call
```

Services never import each other. They are parallel, independent modules.

### 5.2 `STKPushService` — detailed design

#### Password generation

The Daraja STK Push password is documented as:

> `base64(BusinessShortCode + Passkey + Timestamp)`

where Timestamp is `YYYYMMDDHHmmss` in the Africa/Nairobi timezone.

```python
import base64
from datetime import datetime
import pytz  # or zoneinfo (stdlib in Python 3.9+)

def _build_password(shortcode: str, passkey: str) -> tuple[str, str]:
    tz = pytz.timezone("Africa/Nairobi")
    timestamp = datetime.now(tz).strftime("%Y%m%d%H%M%S")
    raw = f"{shortcode}{passkey}{timestamp}"
    password = base64.b64encode(raw.encode()).decode()
    return password, timestamp
```

Both `password` and `timestamp` must use the same moment — they are sent together in the payload and Daraja validates them against each other.

#### `initiate()` payload construction

```python
payload = {
    "BusinessShortCode": mpesa_settings.SHORTCODE,
    "Password": password,
    "Timestamp": timestamp,
    "TransactionType": "CustomerPayBillOnline",
    "Amount": int(amount),          # Daraja rejects decimal amounts for STK Push
    "PartyA": phone_number,
    "PartyB": mpesa_settings.SHORTCODE,
    "PhoneNumber": phone_number,
    "CallBackURL": mpesa_settings.STK_CALLBACK_URL,
    "AccountReference": account_reference,
    "TransactionDesc": transaction_desc,
}
```

`Amount` is cast to `int` because Safaricom rejects amounts with decimal places (e.g. `"100.00"` fails, `"100"` succeeds). The validated `Decimal` input is already verified to have no fractional part by the amount validator.

#### Transaction creation

The transaction record is created **only after** a successful Daraja response (non-error `ResponseCode`). Creating it before would leave orphan `PENDING` rows if the network fails mid-request. This is an intentional trade-off: if the response arrives but DB write fails, the transaction is lost — but that is recoverable via STK Query. Orphan rows from pre-creation are not recoverable without a separate cleanup job.

```python
Transaction = get_transaction_model()
txn = Transaction.objects.create(
    transaction_type="STK_PUSH",
    status="PENDING",
    checkout_request_id=response["CheckoutRequestID"],
    merchant_request_id=response["MerchantRequestID"],
    phone_number=phone_number,
    amount=amount,
    account_reference=account_reference,
    transaction_desc=transaction_desc,
)
return txn
```

### 5.3 `C2BService` — design notes

`register_urls()` is a one-time infrastructure call. It should be called once during deployment setup, not on every request. The library does not call it automatically — that would be presumptuous about when URLs need to be registered. Host apps call it from a management command or a deployment script.

`simulate()` is sandbox-only and guarded by an environment check at the top of the method — not by a decorator, because the guard needs to be explicit and readable in the method body:

```python
def simulate(self, phone_number, amount, bill_ref):
    if mpesa_settings.ENV == "production":
        raise DarajaConfigError(
            "C2BService.simulate() is not available in production. "
            "This method is for sandbox testing only."
        )
    # ... rest of method
```

### 5.4 `B2CService` — design notes

B2C is the most security-sensitive service because it sends money out. Two design decisions:

**1. `SECURITY_CREDENTIAL` is never generated by the library at call time.**

Generating the RSA-encrypted credential requires Safaricom's public certificate, which differs between sandbox and production. If the library generated it, it would need to ship both certificates and handle certificate expiry. Instead, the operator pre-generates it (using Safaricom's portal or the `openssl` command documented in the security guide) and stores it in settings. The library sends it as-is.

**2. Terminal status is never set by `send_payment()`.**

The synchronous Daraja response to a B2C call only confirms the request was accepted for processing — it does not confirm the money was sent. The actual result arrives via `B2C_RESULT_URL` callback minutes later. Setting status to `SUCCESS` on the initiation response would be factually wrong.

### 5.5 `TransactionStatusService`, `AccountBalanceService`, `ReversalService` — design notes

These three services are query/action services that return raw Daraja response dicts. They do not create transaction records because:

- `TransactionStatusService.query()` is a reconciliation tool — the transaction already exists.
- `AccountBalanceService.query()` has no transaction concept — it queries a business account.
- `ReversalService.reverse()` modifies an existing transaction's status, but only via callback, not immediately.

All three follow the same pattern: validate → build payload → `client.post()` → return raw dict. The host app decides what to do with the response.

### 5.6 Service instantiation in host app code

Recommended usage pattern:

```python
# Direct instantiation — fine for simple cases
from django_mpesa.services.stk_push import STKPushService

service = STKPushService()
txn = service.initiate(...)
```

For dependency injection in host app views/tasks:

```python
# Inject a mock in tests by passing client= parameter
def trigger_payment(phone, amount, client=None):
    service = STKPushService(client=client)
    return service.initiate(phone, amount, ...)
```

The library does not ship a service registry, factory, or singleton accessor. Instantiation is cheap (just stores a reference to the client). If the host app wants a shared client instance, that is their responsibility.

---

## 6. Callback Handling Design

### 6.1 Why this section exists separately

The callback path is the highest-risk part of the library. Getting it wrong means:
- Double-crediting a wallet (financial loss)
- Missing a payment (revenue loss)
- Holding a DB row lock during slow business logic (lock contention under load)

Every design decision in this section exists to prevent one of those three outcomes. Each decision is explained with its rationale.

### 6.2 The non-negotiable rule: log-first, acknowledge-immediately, process-async

```
Safaricom POST arrives
      │
      ▼
[1] Write raw body to CallbackLog (unconditional — even if malformed)
      │
      ▼
[2] Dispatch Celery task (or call synchronously)
      │
      ▼
[3] Return HTTP 200 {"ResultCode": 0, "ResultDesc": "Accepted"}
      │
     (request ends here — Safaricom's HTTP client is satisfied)
      │
      ▼ (async, in Celery worker)
[4] Process: lock row, check idempotency, settle, fire signal
```

**Why step [1] before step [2]?** If the Celery broker is down, the task dispatch fails. But the raw payload is already persisted — it can be replayed manually or by a separate recovery job. Without step [1] first, a broker outage means the callback is gone forever.

**Why return 200 before step [4] completes?** Safaricom's callback delivery has its own timeout. If the callback endpoint takes > ~10 seconds, Safaricom marks it as failed and retries. If wallet-crediting, SMS sending, or any slow downstream call happens in the request, it will occasionally exceed that timeout and cause duplicate deliveries. The async model converts an occasional problem into a non-problem: Safaricom always gets its 200 immediately.

**Why log even malformed payloads?** When Safaricom support asks "did you receive our callback at 14:32:07?", you need to be able to say yes or no with evidence. Malformed payloads, duplicate payloads, and payloads from unexpected IPs all belong in the forensic trail.

### 6.3 View design

All callback views share the same skeleton:

```python
class STKCallbackView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        # Step 1: Get source IP (middleware may have already checked it,
        # but we record it regardless for the log)
        source_ip = _get_client_ip(request)

        # Step 2: Parse body — don't fail if malformed, just store raw
        try:
            body = request.data  # DRF already parsed JSON
        except Exception:
            body = {}  # store empty dict; error is implicit in the log

        # Step 3: Log unconditionally
        CallbackLog = get_callback_log_model()
        log = CallbackLog.objects.create(
            callback_type="STK",
            source_ip=source_ip,
            raw_body=body,
        )

        # Step 4: Dispatch — wrapped in try/except so a broker failure
        # never causes a non-200 response to Safaricom
        try:
            if mpesa_settings.USE_CELERY:
                process_stk_callback.delay(str(log.id))
            else:
                process_stk_callback(str(log.id))
        except Exception:
            logger.exception(f"Failed to dispatch STK callback task for log {log.id}")

        # Step 5: Always return 200
        return Response({"ResultCode": 0, "ResultDesc": "Accepted"})
```

The `C2BValidationView` is the only exception — it may return a non-zero `ResultCode` to reject a transaction. All other views always return 200.

### 6.4 Idempotency mechanism — layered defence

Four independent mechanisms work together. Any single one failing is not enough to cause double-settlement.

#### Layer 1: Unique constraint (DB)
`checkout_request_id UNIQUE NOT NULL (when set)` at the database level. Prevents two rows for the same transaction from ever existing.

#### Layer 2: `select_for_update()` row lock
```python
with transaction.atomic():
    txn = Transaction.objects.select_for_update().get(
        checkout_request_id=checkout_request_id
    )
```
When two Celery workers process the same callback simultaneously, both reach `select_for_update()`. One acquires the lock; the other blocks. The blocking worker waits until the first commits, then reads the now-terminal row.

#### Layer 3: Terminal state check (explicit guard)
```python
    if txn.status in TERMINAL_STATES:
        log.processed = True
        log.save(update_fields=["processed"])
        return  # idempotency no-op — silent exit
```
The worker that unblocks after the first worker commits sees `status=SUCCESS` (a terminal state) and exits without doing anything. This is the line that directly prevents double-crediting.

#### Layer 4: Celery task retry safety
If the task crashes after updating `txn.status` but before calling `txn.save()` (e.g. DB connection lost), Celery will retry it. The retry will find the row still `PENDING` (the failed write didn't commit) and settle it. If the task crashes *after* `txn.save()` commits, the retry will find `status=SUCCESS` and exit via Layer 3. Either way: correct.

### 6.5 Task implementation — `process_stk_callback`

```python
@shared_task(bind=True, max_retries=settings.CELERY_TASK_MAX_RETRIES,
             retry_backoff=settings.CELERY_TASK_RETRY_BACKOFF)
def process_stk_callback(self, callback_log_id: str):
    CallbackLog = get_callback_log_model()
    Transaction = get_transaction_model()

    # Load the log — if missing, don't retry (nothing to process)
    try:
        log = CallbackLog.objects.get(id=callback_log_id)
    except CallbackLog.DoesNotExist:
        logger.error(f"CallbackLog {callback_log_id} not found")
        return

    body = log.raw_body
    stk = body.get("Body", {}).get("stkCallback", {})
    checkout_request_id = stk.get("CheckoutRequestID")
    result_code = stk.get("ResultCode")
    result_desc = stk.get("ResultDesc", "")

    # Parse receipt number from metadata (only present on success)
    receipt = None
    if result_code == 0:
        for item in stk.get("CallbackMetadata", {}).get("Item", []):
            if item.get("Name") == "MpesaReceiptNumber":
                receipt = item.get("Value")
                break

    # Settle inside atomic block with row lock
    txn = None
    try:
        with db_transaction.atomic():
            try:
                txn = Transaction.objects.select_for_update().get(
                    checkout_request_id=checkout_request_id
                )
            except Transaction.DoesNotExist:
                logger.warning(
                    f"STK callback for unknown checkout_request_id: {checkout_request_id}"
                )
                log.error = f"No transaction found for {checkout_request_id}"
                log.save(update_fields=["error"])
                return

            # Idempotency check — Layer 3
            if txn.status in TERMINAL_STATES:
                log.processed = True
                log.save(update_fields=["processed"])
                return

            # Settle
            txn.status = "SUCCESS" if result_code == 0 else "FAILED"
            txn.result_code = result_code
            txn.result_desc = result_desc
            txn.settled_at = timezone.now()
            txn.raw_callback_payload = body
            if receipt:
                txn.mpesa_receipt_number = receipt
            txn.save()

            log.related_transaction = txn
            log.processed = True
            log.save(update_fields=["related_transaction", "processed"])

    except Exception as exc:
        logger.exception(f"Error processing STK callback {callback_log_id}")
        raise self.retry(exc=exc)

    # Fire signal OUTSIDE the atomic block — lock is released, slow
    # receivers don't hold the row lock open
    if txn:
        if result_code == 0:
            payment_confirmed.send(sender=Transaction, transaction=txn)
        else:
            payment_failed.send(
                sender=Transaction,
                transaction=txn,
                result_code=result_code,
                result_desc=result_desc,
            )
```

### 6.6 Why signals fire outside the lock

If a signal receiver does anything slow — sends an HTTP request, triggers a secondary DB write, dispatches another Celery task — and that code runs while the row lock is held, any other query that needs to read or write the same transaction row will block until the receiver returns. Under load, with N concurrent callbacks and slow receivers, this creates a lock queue that can starve the DB.

By firing signals after `atomic()` exits:
- The row lock is released before any receiver code runs
- Receiver exceptions cannot roll back the transaction settlement (already committed)
- Receivers see a fully committed, readable transaction state

The only risk: if the task crashes between `atomic()` exiting and the signal firing (e.g. process killed), the signal is lost. This is acceptable — the transaction is already settled correctly in the DB. The host app can always re-derive state from the DB if needed.

### 6.7 `C2BConfirmationView` — create-or-update pattern

C2B is different from STK Push because a customer can pay directly via paybill without the host app ever calling `C2BService` first. There is no prior `PENDING` transaction row to update. The confirmation callback is the first signal that the payment happened.

The task therefore uses a `get_or_create` pattern:

```python
txn, created = Transaction.objects.get_or_create(
    account_reference=bill_ref_number,
    status="PENDING",
    defaults={
        "transaction_type": "C2B",
        "phone_number": msisdn,
        "amount": Decimal(amount),
        ...
    }
)
```

If a matching `PENDING` row exists (host app pre-created it), it's updated. If not, a new `SUCCESS` row is created directly.

---

## 7. Middleware, Signals, Exceptions, Validators, Serializers, Admin

### 7.1 Middleware design — `MpesaCallbackIPAllowlistMiddleware`

#### Scope limiting

The middleware must not inspect every request — only callback paths. It checks the request path before doing any IP work:

```python
class MpesaCallbackIPAllowlistMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        # Pre-compute the URL prefix at startup, not per-request
        self._prefix = "/mpesa/"  # default; resolved from URL config

    def __call__(self, request):
        if not self._is_callback_path(request.path):
            return self.get_response(request)  # zero-cost passthrough

        if not mpesa_settings.VERIFY_CALLBACK_SOURCE_IP:
            return self.get_response(request)  # dev mode passthrough

        ip = self._resolve_ip(request)
        if ip not in mpesa_settings.CALLBACK_IP_ALLOWLIST:
            logger.warning(f"Blocked callback from {ip} — not in allowlist")
            return HttpResponse(status=403)

        return self.get_response(request)
```

#### IP resolution

Two modes, controlled by `TRUST_FORWARDED_FOR`:

```
TRUST_FORWARDED_FOR = False (default):
    ip = request.META["REMOTE_ADDR"]
    # Simple. Correct when Nginx/Caddy terminates TLS and Django
    # sees the real client IP directly in REMOTE_ADDR.

TRUST_FORWARDED_FOR = True:
    raw = request.META.get("HTTP_X_FORWARDED_FOR", "")
    ips = [x.strip() for x in raw.split(",")]
    # X-Forwarded-For is appended left-to-right as the request
    # passes through proxies: [client, proxy1, proxy2]
    # We want the leftmost IP that is NOT a trusted proxy.
    trusted = set(mpesa_settings.FORWARDED_FOR_TRUSTED_PROXIES)
    ip = next((x for x in reversed(ips) if x not in trusted),
               request.META["REMOTE_ADDR"])
```

`TRUST_FORWARDED_FOR` is `False` by default because trusting `X-Forwarded-For` blindly is a security vulnerability — any client can spoof it. Only enable it when the deployment architecture guarantees that only a trusted proxy sets this header.

#### Path matching

Rather than hard-coding `/mpesa/`, the middleware resolves the correct prefix at startup by inspecting the URL configuration. If the host app mounts the URLs at a different prefix, the middleware still works:

```python
from django.urls import reverse

def _get_mpesa_prefix():
    try:
        # Resolve any known mpesa URL to extract the prefix
        url = reverse("django_mpesa:stk-callback")
        return url.rsplit("stk/", 1)[0]
    except Exception:
        return "/mpesa/"  # safe fallback
```

### 7.2 Signals design — `signals.py`

#### Signal definitions and sender conventions

```python
from django.dispatch import Signal

payment_confirmed    = Signal()
payment_failed       = Signal()
c2b_validation_received = Signal()
payout_completed     = Signal()
payout_failed        = Signal()
reversal_completed   = Signal()
balance_received     = Signal()
```

The `sender` argument in `signal.send(sender=...)` is always the Transaction model class (not an instance). This matches Django's own convention (`post_save`, `pre_delete` etc. all use the model class as sender). It allows host apps to connect receivers to a specific model class:

```python
@receiver(payment_confirmed, sender=MpesaTransaction)
def on_payment(sender, transaction, **kwargs): ...
```

#### Signal receiver exception isolation

Signal receivers run synchronously inside the task (after the DB lock is released). If a receiver raises, the exception must not crash the task or unsettle the transaction. The task wraps signal dispatch in a try/except:

```python
try:
    payment_confirmed.send(sender=Transaction, transaction=txn)
except Exception:
    logger.exception(
        f"Signal receiver raised for transaction {txn.id} — "
        f"transaction is settled but receiver failed"
    )
```

This is a deliberate design choice: the transaction is settled (persisted in DB) before the signal fires. Losing the signal notification is recoverable (the host app can query the DB); losing the settlement is not.

#### `c2b_validation_received` — response override pattern

This signal is the only one that affects the HTTP response. The view calls `signal.send()` and checks return values:

```python
responses = c2b_validation_received.send(
    sender=C2BValidationView,
    raw_payload=body,
)
# responses = [(receiver_func, return_value), ...]
# If any receiver returns a dict with "ResultCode", use it
for _, retval in responses:
    if isinstance(retval, dict) and "ResultCode" in retval:
        return Response(retval)

# Default: accept
return Response({"ResultCode": 0, "ResultDesc": "Accepted"})
```

Host app validation receiver:

```python
@receiver(c2b_validation_received)
def validate_c2b(sender, raw_payload, **kwargs):
    bill_ref = raw_payload.get("BillRefNumber", "")
    if not Order.objects.filter(reference=bill_ref, status="OPEN").exists():
        return {"ResultCode": "C2B00012", "ResultDesc": "Invalid bill reference"}
    return {"ResultCode": 0, "ResultDesc": "Accepted"}
```

### 7.3 Exception design — `exceptions.py`

#### Hierarchy implementation

```python
class MpesaError(Exception):
    def __init__(self, message="", result_code=None, result_desc=None):
        super().__init__(message)
        self.message = message
        self.result_code = result_code
        self.result_desc = result_desc

    def __repr__(self):
        return (
            f"{self.__class__.__name__}("
            f"message={self.message!r}, "
            f"result_code={self.result_code!r})"
        )

class DarajaConfigError(MpesaError): pass
class DarajaAuthError(MpesaError): pass
class DarajaValidationError(MpesaError): pass

class DarajaAPIError(MpesaError):
    def __init__(self, message="", result_code=None, result_desc=None,
                 status_code=None, response_body=None):
        super().__init__(message, result_code, result_desc)
        self.status_code = status_code      # HTTP status code from Daraja
        self.response_body = response_body  # raw response body for debugging

class DarajaRateLimitError(DarajaAPIError): pass
class DarajaTimeoutError(DarajaAPIError): pass
class InvalidCallbackError(MpesaError): pass
```

#### Why `result_code` on base class

Callers often need to branch on Safaricom's error taxonomy. Without a typed attribute they resort to string matching on the message, which is fragile. With `result_code` on the base class, a caller can do:

```python
try:
    txn = service.initiate(...)
except DarajaAPIError as e:
    if e.result_code == 400002:
        # Bad request — log and surface to user
    elif e.result_code == 500001:
        # Daraja internal error — retry later
```

### 7.4 Validators design — `validators.py`

Validators are plain functions — no classes, no Django field validators. They are called explicitly by service methods and return the normalised value or raise `DarajaValidationError`.

#### Phone number normalisation flowchart

```
Input string
    │
    ├── Strip whitespace
    ├── Strip leading "+"
    │
    ├── Starts with "254" and len == 12?  ──► return as-is
    │
    ├── Starts with "07" and len == 10?   ──► "254" + input[1:]
    │
    ├── Starts with "7" and len == 9?     ──► "254" + input
    │
    └── anything else                     ──► raise DarajaValidationError
```

#### Amount validator design decision

The validator accepts `int`, `float`, and `Decimal` but always returns `Decimal`. The conversion path for `float` uses `Decimal(str(value))` — NOT `Decimal(value)`. This is critical:

```python
# Wrong — float binary representation leaks in
Decimal(100.5)   # → Decimal('100.4999999999999928945726423989....')

# Correct — string conversion is exact
Decimal(str(100.5))  # → Decimal('100.5')
```

The library converts float inputs safely, but the documented best practice for host apps is to pass `Decimal` directly.

### 7.5 Serializers design — `serializers.py`

Serializers are used by Celery tasks to parse already-logged callback payloads — not by views for request validation. This separation means:

- Views never reject a callback based on payload shape (they always log it raw and return 200)
- Tasks parse the logged payload with a serializer to extract fields cleanly
- Parsing failures in tasks trigger retries, not lost payloads

```python
class STKCallbackSerializer(serializers.Serializer):
    class StkCallbackSerializer(serializers.Serializer):
        MerchantRequestID = serializers.CharField()
        CheckoutRequestID = serializers.CharField()
        ResultCode = serializers.IntegerField()
        ResultDesc = serializers.CharField()
        CallbackMetadata = serializers.DictField(required=False)

    class BodySerializer(serializers.Serializer):
        stkCallback = STKCallbackSerializer.StkCallbackSerializer()

    Body = BodySerializer()
```

If the serializer fails validation (malformed callback), the task logs the error on the `CallbackLog.error` field and does not retry — a malformed payload will never become valid on retry.

### 7.6 Admin design — `admin.py`

The library provides opt-in admin mixins. Nothing is auto-registered. The host app explicitly registers:

```python
# myapp/admin.py
from django.contrib import admin
from django_mpesa.admin import MpesaTransactionAdminMixin, MpesaCallbackLogAdminMixin
from myapp.models import MpesaTransaction, MpesaCallbackLog

@admin.register(MpesaTransaction)
class MpesaTransactionAdmin(MpesaTransactionAdminMixin, admin.ModelAdmin):
    pass

@admin.register(MpesaCallbackLog)
class MpesaCallbackLogAdmin(MpesaCallbackLogAdminMixin, admin.ModelAdmin):
    pass
```

#### Why all fields are `readonly_fields`

Transaction records are the system's source of financial truth. Allowing admin users to edit them would undermine audit integrity. The admin is a read-only forensic view. If a record needs correction, it must happen through a controlled code path (a management command or a dedicated reconciliation API), not through the Django admin form.

#### `MpesaTransactionAdminMixin` extras

- Custom `status_badge` column that renders coloured HTML badges (green for SUCCESS, red for FAILED, orange for PENDING) using `format_html`. Displayed in `list_display`.
- `get_queryset` uses `select_related()` on `related_transaction` to avoid N+1 in the callback log list view.
- `date_hierarchy = "initiated_at"` on the transaction admin for date-based drill-down.

---

## 8. Testing Architecture

### 8.1 Design goals for the test layer

1. **No network required.** Every test must pass with `PYTHONHTTPSVERIFY=0 DJANGO_SETTINGS_MODULE=tests.settings pytest` and zero external access.
2. **No patching required by host apps.** The `MockDarajaClient` is injected via constructor, not via `unittest.mock.patch`. Host apps test their signal receivers by calling `process_stk_callback` directly with a factory-created log.
3. **The concurrency test is not optional.** It must run on every CI push. It is the primary regression guard for the most expensive bug class.

### 8.2 `MockDarajaClient` design

The mock must behave like `BaseDarajaClient` from the caller's perspective — same `post(path, payload) -> dict` interface. Internally it is a simple lookup table.

```python
class MockDarajaClient:
    # Default canned responses for all known Daraja paths
    _DEFAULT_RESPONSES = {
        "/mpesa/stkpush/v1/processrequest": {
            "ResponseCode": "0",
            "CheckoutRequestID": "ws_CO_test_123",
            "MerchantRequestID": "test_merchant_456",
            "ResponseDescription": "Success. Request accepted for processing",
            "CustomerMessage": "Success. Request accepted for processing",
        },
        "/mpesa/stkpushquery/v1/query": {
            "ResponseCode": "0",
            "ResultCode": "0",
            "ResultDesc": "The service request is processed successfully.",
        },
        "/mpesa/c2b/v1/registerurl": {
            "ResponseCode": "0",
            "ResponseDescription": "Success",
        },
        "/mpesa/c2b/v1/simulate": {
            "ResponseCode": "0",
            "ResponseDescription": "Accept the service request successfully.",
            "OriginatorConversationID": "test_sim_123",
        },
        "/mpesa/b2c/v1/paymentrequest": {
            "ResponseCode": "0",
            "ConversationID": "test_conv_123",
            "OriginatorConversationID": "test_orig_123",
            "ResponseDescription": "Accept the service request successfully.",
        },
        "/mpesa/transactionstatus/v1/query": {
            "ResponseCode": "0",
            "ResponseDescription": "Accept the service request successfully.",
        },
        "/mpesa/accountbalance/v1/query": {
            "ResponseCode": "0",
            "ResponseDescription": "Accept the service request successfully.",
        },
        "/mpesa/reversal/v1/request": {
            "ResponseCode": "0",
            "ResponseDescription": "Accept the service request successfully.",
        },
    }

    def __init__(self, responses=None, raise_on=None):
        self._responses = {**self._DEFAULT_RESPONSES, **(responses or {})}
        self._raise_on = raise_on or {}
        self._calls = []

    def post(self, path: str, payload: dict) -> dict:
        self._calls.append({"path": path, "payload": payload})
        if path in self._raise_on:
            raise self._raise_on[path]
        if path in self._responses:
            return self._responses[path]
        raise DarajaAPIError(f"MockDarajaClient: no response configured for {path!r}")

    def set_response(self, path: str, response: dict):
        self._responses[path] = response

    def set_raise(self, path: str, exception: Exception):
        self._raise_on[path] = exception

    def reset(self):
        self._responses = {**self._DEFAULT_RESPONSES}
        self._raise_on = {}
        self._calls = []

    @property
    def calls(self):
        return list(self._calls)

    def assert_called_once_with_path(self, path: str):
        matching = [c for c in self._calls if c["path"] == path]
        assert len(matching) == 1, (
            f"Expected exactly one call to {path!r}, got {len(matching)}"
        )
```

### 8.3 pytest fixtures design

All fixtures live in `django_mpesa/testing/fixtures.py` and are importable as a pytest plugin via `conftest.py`:

```python
# tests/conftest.py
from django_mpesa.testing.fixtures import *  # noqa
```

Or selectively:
```python
from django_mpesa.testing.fixtures import mock_daraja, pending_stk_transaction
```

#### `mock_daraja` fixture

```python
@pytest.fixture
def mock_daraja():
    client = MockDarajaClient()
    yield client
    client.reset()
```

Scoped to `function` — each test gets a fresh client with no recorded calls and default responses.

#### Callback payload fixtures

These return realistic payloads that match Safaricom's actual response schema — not simplified stubs. The exact field names and nesting matter because the task code parses them by key name.

```python
@pytest.fixture
def stk_success_callback():
    return {
        "Body": {
            "stkCallback": {
                "MerchantRequestID": "test_merchant_456",
                "CheckoutRequestID": "ws_CO_test_123",
                "ResultCode": 0,
                "ResultDesc": "The service request is processed successfully.",
                "CallbackMetadata": {
                    "Item": [
                        {"Name": "Amount", "Value": 100},
                        {"Name": "MpesaReceiptNumber", "Value": "NLJ7RT61SV"},
                        {"Name": "TransactionDate", "Value": 20191219102115},
                        {"Name": "PhoneNumber", "Value": 254712345678},
                    ]
                },
            }
        }
    }

@pytest.fixture
def stk_failure_callback():
    return {
        "Body": {
            "stkCallback": {
                "MerchantRequestID": "test_merchant_456",
                "CheckoutRequestID": "ws_CO_test_123",
                "ResultCode": 1032,
                "ResultDesc": "Request cancelled by user.",
            }
        }
    }
```

#### Transaction fixtures

```python
@pytest.fixture
def pending_stk_transaction(db):
    """A PENDING STK Push transaction ready to receive a callback."""
    return MpesaTransactionFactory(
        transaction_type="STK_PUSH",
        status="PENDING",
        checkout_request_id="ws_CO_test_123",
        merchant_request_id="test_merchant_456",
        phone_number="254712345678",
        amount=Decimal("100.00"),
    )

@pytest.fixture
def pending_b2c_transaction(db):
    """A PENDING B2C transaction ready to receive a result callback."""
    return MpesaTransactionFactory(
        transaction_type="B2C",
        status="PENDING",
        conversation_id="test_conv_123",
        originator_conversation_id="test_orig_123",
        phone_number="254712345678",
        amount=Decimal("500.00"),
    )
```

### 8.4 The concurrency test — design in full

This is the most important test in the suite. It must be run on every CI push and must never be skipped.

```python
# tests/test_idempotency.py
import threading
from decimal import Decimal
import pytest
from django_mpesa.tasks import process_stk_callback
from django_mpesa.signals import payment_confirmed
from django_mpesa.testing.factories import MpesaTransactionFactory, MpesaCallbackLogFactory

@pytest.mark.django_db(transaction=True)  # transaction=True required for threading + DB
def test_duplicate_stk_callback_settles_exactly_once():
    """
    Two threads call process_stk_callback for the same checkout_request_id
    simultaneously. Asserts the transaction is settled exactly once and the
    signal fires exactly once.
    """
    # Setup: one PENDING transaction, two callback logs for the same event
    txn = MpesaTransactionFactory(
        status="PENDING",
        checkout_request_id="ws_CO_concurrent_test",
        amount=Decimal("100.00"),
    )
    success_payload = {
        "Body": {"stkCallback": {
            "CheckoutRequestID": "ws_CO_concurrent_test",
            "ResultCode": 0,
            "ResultDesc": "The service request is processed successfully.",
            "CallbackMetadata": {"Item": [
                {"Name": "MpesaReceiptNumber", "Value": "NLJ7RT61SV"},
                {"Name": "Amount", "Value": 100},
            ]},
        }}
    }
    log1 = MpesaCallbackLogFactory(callback_type="STK", raw_body=success_payload)
    log2 = MpesaCallbackLogFactory(callback_type="STK", raw_body=success_payload)

    # Track signal fires
    signal_fire_count = []

    def on_payment_confirmed(sender, transaction, **kwargs):
        signal_fire_count.append(transaction.id)

    payment_confirmed.connect(on_payment_confirmed)

    # Use a barrier to force both threads to reach task entry simultaneously
    barrier = threading.Barrier(2)
    errors = []

    def run_task(log_id):
        try:
            barrier.wait()  # Both threads start at the same moment
            process_stk_callback(str(log_id))
        except Exception as e:
            errors.append(e)

    t1 = threading.Thread(target=run_task, args=(log1.id,))
    t2 = threading.Thread(target=run_task, args=(log2.id,))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    payment_confirmed.disconnect(on_payment_confirmed)

    # Assertions
    assert errors == [], f"Threads raised exceptions: {errors}"

    txn.refresh_from_db()
    assert txn.status == "SUCCESS"
    assert txn.mpesa_receipt_number == "NLJ7RT61SV"
    assert txn.settled_at is not None

    # The critical assertion: signal fired exactly once
    assert len(signal_fire_count) == 1, (
        f"payment_confirmed fired {len(signal_fire_count)} times — "
        f"expected exactly 1"
    )
```

#### Why `transaction=True` on `@pytest.mark.django_db`

By default, `pytest-django` wraps each test in a transaction that is rolled back at the end. This means all DB operations see the same transaction and `select_for_update()` has no real effect (you can't lock rows within the same transaction that created them, in the way that matters for concurrency). `transaction=True` uses real commits so the two threads see each other's writes — which is what we need to test the actual race condition.

#### What this test catches

If the `select_for_update()` call is removed or the terminal state check is removed, both threads will read `status=PENDING`, both will set `status=SUCCESS`, both will save, and `signal_fire_count` will be `[txn.id, txn.id]` — length 2. The assertion will fail. This is the exact regression we're guarding against.

### 8.5 Test app — `tests/testapp/`

The library needs a concrete model to run tests against. A minimal test app lives inside `tests/`:

```
tests/
└── testapp/
    ├── __init__.py
    ├── apps.py
    └── models.py
```

```python
# tests/testapp/models.py
from django_mpesa.models import AbstractMpesaTransaction, AbstractMpesaCallbackLog

class MpesaTransaction(AbstractMpesaTransaction):
    class Meta(AbstractMpesaTransaction.Meta):
        app_label = "testapp"

class MpesaCallbackLog(AbstractMpesaCallbackLog):
    class Meta(AbstractMpesaCallbackLog.Meta):
        app_label = "testapp"
```

This is registered in `tests/settings.py` via `MPESA["TRANSACTION_MODEL"] = "testapp.MpesaTransaction"`. It has no extra fields — the tests exercise the abstract model's own fields only. Host app-specific field behaviour is the host app's test responsibility.

---

## 9. Packaging, CI/CD Design, and Documentation Site

### 9.1 Package layout and Hatchling build

The build backend is Hatchling. It reads the package from the `django_mpesa/` directory only — `tests/`, `docs/`, `plan/`, and `specs/` are excluded from the wheel.

```toml
# pyproject.toml (build section)
[tool.hatch.build.targets.wheel]
packages = ["django_mpesa"]

[tool.hatch.build.targets.sdist]
include = [
    "django_mpesa/",
    "pyproject.toml",
    "README.md",
    "LICENSE",
    "CHANGELOG.md",
]
```

`django_mpesa/__init__.py` reads its own version from package metadata at runtime — no hardcoded version string to keep in sync:

```python
from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("django-mpesa")
except PackageNotFoundError:
    __version__ = "0.0.0-dev"  # running from source without install
```

### 9.2 `pyproject.toml` — dependency pinning strategy

Runtime dependencies use minimum version pins, not exact pins:

```toml
dependencies = [
    "django>=4.2",
    "djangorestframework>=3.14",
    "requests>=2.31",
]
```

**Rationale:** The library is installed alongside a host app's own dependencies. Exact pins would cause conflicts when the host app requires a newer version of the same package. Minimum version pins express "we need at least this" while letting pip resolve the highest compatible version. This is the standard practice for library packages (as opposed to application packages, which should pin exactly).

Optional dependencies:

```toml
[project.optional-dependencies]
celery  = ["celery>=5.3"]
test    = ["pytest>=7.4", "pytest-django>=4.7", "pytest-cov>=4.1",
           "factory-boy>=3.3", "responses>=0.24"]
docs    = ["mkdocs-material>=9.4"]
dev     = ["django-mpesa[celery,test,docs]", "pip-audit>=2.6", "ruff>=0.1", "mypy>=1.5"]
```

### 9.3 Version management and release process

#### Version bumping

Version lives only in `pyproject.toml`. The release process:

1. Update `version = "X.Y.Z"` in `pyproject.toml`.
2. Update `CHANGELOG.md` with release notes under the new version heading.
3. Commit: `git commit -m "Release vX.Y.Z"`.
4. Tag: `git tag vX.Y.Z`.
5. Push tag: `git push origin vX.Y.Z` — triggers the publish workflow.

No manual PyPI upload. The CI workflow owns publication.

#### Milestone versioning

| Version | Milestone |
|---|---|
| `0.1.0` | STK Push end-to-end (services + callback + idempotency) |
| `0.2.0` | C2B + B2C |
| `0.3.0` | Transaction Status, Account Balance, Reversal |
| `0.4.0` | Full test suite, docs site, `mpesa_check_config` |
| `1.0.0` | After Zaruni production billing cycle completes with no hotfix |

### 9.4 CI pipeline design

#### `test.yml` — structure

```yaml
name: Test

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false   # run all matrix combos even if one fails
      matrix:
        python-version: ["3.10", "3.11", "3.12"]
        django-version: ["4.2", "5.0"]

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install dependencies
        run: |
          pip install -e ".[test,celery]" \
            "Django==${{ matrix.django-version }}.*"

      - name: Validate config command
        run: |
          python -m pytest tests/ -x -q \
            --ds=tests.settings \
            --ignore=tests/test_idempotency.py   # runs separately below

      - name: Run tests with coverage
        run: |
          pytest --cov=django_mpesa \
                 --cov-report=xml \
                 --cov-report=term-missing \
                 --cov-fail-under=90 \
                 -v

      - name: Run concurrency test (transaction=True, separate step)
        run: |
          pytest tests/test_idempotency.py -v --ds=tests.settings

      - name: Dependency audit
        run: pip-audit --strict
        continue-on-error: true   # warn but don't block on audit findings

      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          file: coverage.xml
```

#### `publish.yml` — structure

```yaml
name: Publish to PyPI

on:
  push:
    tags: ["v*.*.*"]

jobs:
  publish:
    runs-on: ubuntu-latest
    environment: pypi   # requires manual approval in GitHub environments

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install build tools
        run: pip install hatchling build

      - name: Build
        run: python -m build

      - name: Publish to PyPI
        uses: pypa/gh-action-pypi-publish@release/v1
        with:
          password: ${{ secrets.PYPI_API_TOKEN }}
```

The `environment: pypi` setting requires a manual approval step in GitHub's deployment environments before the publish job runs. This prevents accidental publishes from mis-tagged commits.

### 9.5 Code quality tooling

```toml
# pyproject.toml

[tool.ruff]
line-length = 100
select = ["E", "F", "I", "UP", "B", "SIM"]
ignore = ["E501"]   # line length handled separately

[tool.mypy]
python_version = "3.10"
strict = false       # start permissive, tighten over time
ignore_missing_imports = true
warn_unused_ignores = true

[tool.pytest.ini_options]
DJANGO_SETTINGS_MODULE = "tests.settings"
python_files = ["test_*.py"]
addopts = "--tb=short"

[tool.coverage.run]
source = ["django_mpesa"]
omit = ["django_mpesa/testing/*"]   # test helpers excluded from threshold

[tool.coverage.report]
fail_under = 90
show_missing = true
```

### 9.6 Documentation site design

Built with MkDocs Material. Hosted on Read the Docs (auto-builds on push to `main`).

#### `mkdocs.yml` structure

```yaml
site_name: django-mpesa
site_url: https://django-mpesa.readthedocs.io
repo_url: https://github.com/mainfinity/django-mpesa
repo_name: mainfinity/django-mpesa

theme:
  name: material
  palette:
    primary: green
  features:
    - navigation.tabs
    - navigation.sections
    - content.code.copy
    - search.suggest

nav:
  - Home: index.md
  - Getting Started: quickstart.md
  - Configuration: settings.md
  - Services:
    - STK Push: services/stk_push.md
    - C2B: services/c2b.md
    - B2C: services/b2c.md
    - Transaction Status: services/transaction_status.md
    - Account Balance: services/account_balance.md
    - Reversal: services/reversal.md
  - Reference:
    - Models: models.md
    - Callbacks: callbacks.md
    - Signals: signals.md
    - Testing: testing.md
    - Security: security.md

markdown_extensions:
  - pymdownx.highlight
  - pymdownx.superfences
  - admonition
  - tables
```

#### `quickstart.md` design

The quickstart is the most important documentation page. Its quality bar: a developer who has never used the library should reach a working STK Push in under 10 minutes. It is structured as a numbered recipe:

1. `pip install django-mpesa[celery]`
2. Add to `INSTALLED_APPS`
3. Subclass models — minimal code example, copy-pasteable
4. Add `MPESA` settings block — minimal sandbox config, copy-pasteable
5. Wire URLs — one `path()` line
6. Run migrations
7. Call `STKPushService.initiate()` — minimal working example
8. Wire the `payment_confirmed` signal — minimal receiver example
9. Run `mpesa_check_config` to verify setup

Each step is one small code block. No theory, no deep explanation on the quickstart page — those live in the reference pages. The quickstart is a recipe, not a tutorial.

#### Documentation versioning

Read the Docs is configured to build both `latest` (from `main` branch) and versioned builds (from tags). The version switcher in the docs lets users pin to a specific library version's docs.

---

*End of design document. Proceed to the task breakdown in `specs/tasks.md`.*

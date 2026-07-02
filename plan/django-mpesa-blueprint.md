# django-mpesa — full technical blueprint

**Status:** Design spec, pre-implementation
**Author:** Daniel Maina / Mainfinity
**Purpose:** A reusable, open-source Django app wrapping Safaricom's Daraja API (STK Push, C2B, B2C, Transaction Status, Account Balance, Reversal). Extracted from production logic in Zaruni. This document is written so that any contributor can implement any module in isolation without needing to consult the author.

---

## 1. Design goals

1. **Idempotent by default.** Safaricom retries callbacks. The library must guarantee a transaction is settled exactly once, even under concurrent callback delivery.
2. **Host-agnostic.** No project-specific assumptions. Wallet logic, notifications, user models — all live in the host app, not the library.
3. **Swappable models.** Host apps subclass abstract base models, the same pattern Django uses for `AUTH_USER_MODEL`.
4. **Sandbox-safe testing.** No test should require Safaricom's sandbox to be up. A mock client ships with the package.
5. **Secure by default.** Credentials never hardcoded. Callback endpoints verify source IP. Sensitive fields encrypted at rest.
6. **One responsibility per module.** Each Daraja API (STK Push, B2C, etc.) is a separate service class. No god-object client.

---

## 2. Full package structure

```
django-mpesa/
├── pyproject.toml
├── LICENSE                          # MIT
├── README.md
├── CONTRIBUTING.md
├── CODE_OF_CONDUCT.md
├── CHANGELOG.md
├── .github/
│   ├── workflows/
│   │   ├── test.yml                 # pytest matrix: Django 4.2/5.0, Python 3.10-3.12
│   │   └── publish.yml              # PyPI publish on tag push
│   └── ISSUE_TEMPLATE/
│       ├── bug_report.md
│       └── feature_request.md
├── docs/
│   ├── index.md
│   ├── quickstart.md
│   ├── settings.md
│   ├── services/
│   │   ├── stk_push.md
│   │   ├── c2b.md
│   │   ├── b2c.md
│   │   ├── transaction_status.md
│   │   ├── account_balance.md
│   │   └── reversal.md
│   ├── models.md
│   ├── callbacks.md
│   ├── signals.md
│   ├── testing.md
│   └── security.md
├── django_mpesa/
│   ├── __init__.py                  # __version__
│   ├── apps.py                      # MpesaConfig(AppConfig)
│   ├── conf.py                      # settings resolver (see §3)
│   ├── exceptions.py                # exception hierarchy (see §8)
│   ├── models.py                    # abstract base models (see §4)
│   ├── signals.py                   # signal catalog (see §7)
│   ├── views.py                     # callback endpoints (see §6)
│   ├── urls.py                      # includeable URL patterns
│   ├── tasks.py                     # Celery tasks (see §6.4)
│   ├── middleware.py                # Safaricom IP allowlist middleware
│   ├── validators.py                # phone number, amount, account reference validators
│   ├── client/
│   │   ├── __init__.py
│   │   ├── auth.py                  # TokenManager (see §5.1)
│   │   ├── base.py                  # BaseDarajaClient (see §5.2)
│   │   └── http.py                  # requests session w/ retry/backoff config
│   ├── services/
│   │   ├── __init__.py
│   │   ├── stk_push.py              # STKPushService (see §5.3)
│   │   ├── c2b.py                   # C2BService (see §5.4)
│   │   ├── b2c.py                   # B2CService (see §5.5)
│   │   ├── transaction_status.py    # TransactionStatusService (see §5.6)
│   │   ├── account_balance.py       # AccountBalanceService (see §5.7)
│   │   └── reversal.py              # ReversalService (see §5.8)
│   ├── serializers.py               # DRF serializers for callback payload validation
│   ├── admin.py                     # Django admin registration (optional mixin)
│   ├── management/
│   │   └── commands/
│   │       └── mpesa_check_config.py  # sanity-checks settings on deploy
│   └── testing/
│       ├── __init__.py
│       ├── mock_client.py           # MockDarajaClient (see §9.1)
│       ├── fixtures.py              # pytest fixtures (see §9.2)
│       └── factories.py             # factory_boy factories for test transactions
└── tests/
    ├── conftest.py
    ├── test_client/
    ├── test_services/
    ├── test_callbacks/
    ├── test_models/
    └── test_idempotency.py          # the concurrency test that matters most
```

---

## 3. Settings schema (`conf.py`)

All settings live under a single `MPESA` dict in the host app's `settings.py`. `conf.py` exposes a resolver object `mpesa_settings` (pattern copied from DRF's `api_settings`) so defaults apply when a key is omitted.

```python
MPESA = {
    # Environment
    "ENV": "sandbox",  # "sandbox" | "production"

    # Credentials — resolved via callables so secrets can come from
    # env vars, AWS Secrets Manager, Vault, etc. Never hardcode.
    "CONSUMER_KEY": lambda: os.environ["MPESA_CONSUMER_KEY"],
    "CONSUMER_SECRET": lambda: os.environ["MPESA_CONSUMER_SECRET"],
    "SHORTCODE": lambda: os.environ["MPESA_SHORTCODE"],
    "PASSKEY": lambda: os.environ["MPESA_PASSKEY"],              # STK Push
    "INITIATOR_NAME": lambda: os.environ.get("MPESA_INITIATOR_NAME"),
    "INITIATOR_PASSWORD": lambda: os.environ.get("MPESA_INITIATOR_PASSWORD"),  # B2C/reversal
    "SECURITY_CREDENTIAL": lambda: os.environ.get("MPESA_SECURITY_CREDENTIAL"),  # pre-encrypted

    # Callback URLs — must be publicly reachable HTTPS
    "STK_CALLBACK_URL": "https://yourapp.com/mpesa/stk/callback/",
    "C2B_VALIDATION_URL": "https://yourapp.com/mpesa/c2b/validate/",
    "C2B_CONFIRMATION_URL": "https://yourapp.com/mpesa/c2b/confirm/",
    "B2C_RESULT_URL": "https://yourapp.com/mpesa/b2c/result/",
    "B2C_TIMEOUT_URL": "https://yourapp.com/mpesa/b2c/timeout/",

    # Behaviour
    "TOKEN_CACHE_ALIAS": "default",         # Django cache alias for OAuth token
    "TOKEN_CACHE_TTL_BUFFER": 60,           # seconds subtracted from Safaricom's expiry
    "REQUEST_TIMEOUT": 30,                   # seconds
    "MAX_RETRIES": 3,
    "RETRY_BACKOFF_FACTOR": 0.5,
    "VERIFY_CALLBACK_SOURCE_IP": True,       # enforce Safaricom IP allowlist
    "CALLBACK_IP_ALLOWLIST": [               # Safaricom's published ranges; override if they change
        "196.201.214.200", "196.201.214.206", "196.201.213.114",
        "196.201.214.207", "196.201.214.208", "196.201.213.44",
        "196.201.212.127", "196.201.212.128", "196.201.212.129",
        "196.201.212.132", "196.201.212.136",
    ],

    # Model overrides (see §4)
    "TRANSACTION_MODEL": "myapp.MpesaTransaction",
    "CALLBACK_LOG_MODEL": "myapp.MpesaCallbackLog",

    # Celery
    "USE_CELERY": True,                      # False = process callbacks synchronously (small apps)
    "CELERY_TASK_MAX_RETRIES": 5,
    "CELERY_TASK_RETRY_BACKOFF": True,
}
```

`django_mpesa.management.commands.mpesa_check_config` runs on deploy (or manually) and fails loudly if required keys are missing for the selected `ENV`, if callback URLs aren't HTTPS, or if `TRANSACTION_MODEL` doesn't resolve.

---

## 4. Data models (`models.py`)

Ship **abstract** base models. Host apps subclass and register via `AUTH_USER_MODEL`-style string settings (`TRANSACTION_MODEL`, `CALLBACK_LOG_MODEL`). This is what makes the library actually reusable across Zaruni, ShuleSafi, Mainfinity TV, etc. without forking it.

### 4.1 `AbstractMpesaTransaction`

| Field | Type | Notes |
|---|---|---|
| `id` | UUID, PK | Never expose Safaricom's own IDs as your PK |
| `transaction_type` | CharField, choices | `STK_PUSH`, `C2B`, `B2C`, `REVERSAL` |
| `status` | CharField, choices | `PENDING`, `PROCESSING`, `SUCCESS`, `FAILED`, `TIMEOUT`, `REVERSED` |
| `checkout_request_id` | CharField, unique, null | STK Push idempotency key |
| `merchant_request_id` | CharField, null | STK Push, for cross-reference |
| `conversation_id` | CharField, unique, null | B2C/reversal idempotency key |
| `originator_conversation_id` | CharField, null | B2C/reversal, set at request time |
| `mpesa_receipt_number` | CharField, null | Populated only on success |
| `phone_number` | CharField | Validated E.164/254 format via `validators.py` |
| `amount` | DecimalField(12,2) | Never float — money is always Decimal |
| `account_reference` | CharField | For C2B/STK — free text tied to host order/invoice |
| `transaction_desc` | CharField | Human-readable description |
| `result_code` | IntegerField, null | Raw Safaricom result code |
| `result_desc` | TextField, null | Raw Safaricom result description |
| `raw_callback_payload` | JSONField, null | Full callback body, for audit/debug |
| `initiated_at` | DateTimeField, auto_now_add | |
| `settled_at` | DateTimeField, null | Set when status moves to a terminal state |
| `idempotency_locked` | BooleanField, default False | See §6.3 — flips inside the row lock |

**Class-level contract:**
- `checkout_request_id` and `conversation_id` are the two idempotency keys the library relies on — both must carry `unique=True` (nulls allowed, since only one applies per transaction type).
- Host apps add their own FKs (`order`, `user`, `wallet`, etc.) on the concrete subclass — the abstract model stays domain-free.

### 4.2 `AbstractMpesaCallbackLog`

Every raw callback (even duplicates, even malformed ones) gets logged here before any business logic runs. This is your forensic trail when Safaricom support asks "did you receive our callback."

| Field | Type | Notes |
|---|---|---|
| `id` | UUID, PK | |
| `callback_type` | CharField, choices | `STK`, `C2B_VALIDATION`, `C2B_CONFIRMATION`, `B2C_RESULT`, `B2C_TIMEOUT` |
| `source_ip` | GenericIPAddressField | |
| `raw_body` | JSONField | Unparsed request body |
| `related_transaction` | FK to `TRANSACTION_MODEL`, null | Linked after matching by idempotency key |
| `processed` | BooleanField, default False | |
| `received_at` | DateTimeField, auto_now_add | |

### 4.3 Example host-app implementation

```python
# myapp/models.py
from django_mpesa.models import AbstractMpesaTransaction, AbstractMpesaCallbackLog

class MpesaTransaction(AbstractMpesaTransaction):
    order = models.ForeignKey("orders.Order", on_delete=models.PROTECT, null=True)
    initiated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

class MpesaCallbackLog(AbstractMpesaCallbackLog):
    pass
```

```python
# settings.py
MPESA = {
    ...,
    "TRANSACTION_MODEL": "myapp.MpesaTransaction",
    "CALLBACK_LOG_MODEL": "myapp.MpesaCallbackLog",
}
```

---

## 5. Client and service layer

### 5.1 `client/auth.py` — `TokenManager`

Handles Daraja's OAuth token — a base64(consumer_key:consumer_secret) Basic Auth request that returns a bearer token valid for ~3600s.

```python
class TokenManager:
    def get_token(self) -> str:
        """
        Returns a valid bearer token. Checks Django cache first
        (key: f"mpesa:token:{env}"), fetches a fresh one from Daraja
        if missing or within TOKEN_CACHE_TTL_BUFFER seconds of expiry.
        Thread-safe via cache.add() as a lock (avoids stampede on
        concurrent first-request cold starts).
        """

    def _fetch_new_token(self) -> tuple[str, int]:
        """Calls GET /oauth/v1/generate?grant_type=client_credentials.
        Returns (token, expires_in). Raises DarajaAuthError on failure."""

    def invalidate(self) -> None:
        """Clears cached token — call after a 401 from any service call."""
```

**Design note:** token caching is the single highest-impact optimization — without it, every API call does a redundant OAuth round-trip. Use `cache.get_or_set` with the buffer subtracted from Safaricom's `expires_in`.

### 5.2 `client/base.py` — `BaseDarajaClient`

Every service class composes this rather than inheriting it (composition over inheritance — makes services independently testable).

```python
class BaseDarajaClient:
    def __init__(self, token_manager: TokenManager, session: requests.Session = None):
        ...

    def post(self, path: str, payload: dict) -> dict:
        """
        - Prepends base URL (sandbox vs production, from conf.py)
        - Attaches Authorization: Bearer {token}
        - Applies MAX_RETRIES with exponential backoff (RETRY_BACKOFF_FACTOR)
          on 5xx and connection errors only — never retries on 4xx,
          since Safaricom is telling you the request itself is wrong
        - On 401: invalidates cached token once, retries once, then raises
        - Raises DarajaAPIError with the parsed error body on failure
        - Logs every outbound request/response at DEBUG level with
          sensitive fields (PIN, security credential) redacted
        """
```

`client/http.py` configures the underlying `requests.Session` with `urllib3.Retry` for transport-level retry, kept separate from the application-level retry in `base.py` so the two don't compound unpredictably.

### 5.3 `services/stk_push.py` — `STKPushService`

Maps to Daraja's **Lipa Na M-Pesa Online** API.

```python
class STKPushService:
    def initiate(
        self,
        phone_number: str,       # validated to 2547XXXXXXXX format
        amount: Decimal,
        account_reference: str,  # max 12 chars per Daraja spec
        transaction_desc: str,   # max 13 chars per Daraja spec
    ) -> "MpesaTransaction":
        """
        1. Validates inputs via validators.py
        2. Builds the Password field: base64(shortcode + passkey + timestamp)
        3. POSTs to /mpesa/stkpush/v1/processrequest
        4. Creates a PENDING MpesaTransaction row, storing
           checkout_request_id + merchant_request_id from the response
        5. Returns the created transaction instance
        Raises DarajaValidationError before any network call if
        inputs are malformed — never send an invalid request to Daraja.
        """

    def query(self, checkout_request_id: str) -> dict:
        """
        POSTs to /mpesa/stkpushquery/v1/query — useful when the
        callback hasn't arrived within a reasonable window (Daraja
        doesn't guarantee callback delivery time). Does NOT mutate
        the transaction — caller decides whether to reconcile.
        """
```

### 5.4 `services/c2b.py` — `C2BService`

```python
class C2BService:
    def register_urls(self, response_type: str = "Completed") -> dict:
        """One-time setup call — POSTs to /mpesa/c2b/v1/registerurl
        with ValidationURL and ConfirmationURL from settings."""

    def simulate(self, phone_number: str, amount: Decimal, bill_ref: str) -> dict:
        """Sandbox-only — POSTs to /mpesa/c2b/v1/simulate.
        Raises DarajaConfigError if ENV == 'production'."""
```

Validation and confirmation are **not** methods here — they're callback views (§6), since C2B is Safaricom pushing data to you, not you initiating a request.

### 5.5 `services/b2c.py` — `B2CService`

Maps to **Business to Customer** payouts — what Zaruni already uses for seller payouts.

```python
class B2CService:
    def send_payment(
        self,
        phone_number: str,
        amount: Decimal,
        remarks: str,
        occasion: str = "",
        command_id: str = "BusinessPayment",  # or "SalaryPayment", "PromotionPayment"
    ) -> "MpesaTransaction":
        """
        POSTs to /mpesa/b2c/v1/paymentrequest with SecurityCredential
        (pre-encrypted initiator password — see §10.2 on generating this).
        Creates a PENDING transaction, stores conversation_id +
        originator_conversation_id from the synchronous response.
        Terminal status arrives via B2C_RESULT_URL callback, not here.
        """
```

### 5.6 `services/transaction_status.py` — `TransactionStatusService`

```python
class TransactionStatusService:
    def query(self, transaction_id: str, identifier_type: str = "1") -> dict:
        """POSTs to /mpesa/transactionstatus/v1/query.
        Used for reconciliation when a transaction is stuck PENDING
        past a reasonable SLA (e.g. 5 minutes for STK Push)."""
```

### 5.7 `services/account_balance.py` — `AccountBalanceService`

```python
class AccountBalanceService:
    def query(self, identifier_type: str = "4") -> dict:
        """POSTs to /mpesa/accountbalance/v1/query.
        Result arrives via callback — this call only confirms
        the query was accepted, per Daraja's async pattern."""
```

### 5.8 `services/reversal.py` — `ReversalService`

```python
class ReversalService:
    def reverse(
        self,
        transaction_id: str,
        amount: Decimal,
        remarks: str,
        receiver_party: str,
    ) -> dict:
        """POSTs to /mpesa/reversal/v1/request.
        Updates the original MpesaTransaction status to REVERSED
        only once the reversal RESULT callback confirms success —
        never optimistically on the initiate response."""
```

---

## 6. Callback handling (`views.py`, `tasks.py`, `middleware.py`)

This is the layer that matters most for correctness. Design it exactly like this:

### 6.1 Request path

```
Safaricom → HTTPS POST → middleware.py (IP allowlist check)
          → views.py (parse + log raw payload to CallbackLog, return 200 immediately)
          → tasks.py (Celery task does the actual settlement, async)
```

**Critical rule: the view always returns Safaricom's expected `{"ResultCode": 0, "ResultDesc": "Accepted"}` within the request, even before processing completes.** Safaricom's callback delivery has its own timeout and retry behavior — if your view hangs waiting on business logic (sending SMS, updating a wallet, hitting another API), Safaricom may consider it failed and retry, causing duplicate callbacks. Log-then-acknowledge-then-process-async is non-negotiable.

### 6.2 `middleware.py` — `MpesaCallbackIPAllowlistMiddleware`

```python
class MpesaCallbackIPAllowlistMiddleware:
    """
    Applied only to paths matching django_mpesa's URL patterns.
    Compares request.META['REMOTE_ADDR'] (accounting for
    X-Forwarded-For if behind Cloudflare/Caddy — configurable)
    against MPESA['CALLBACK_IP_ALLOWLIST'].
    Returns 403 immediately for non-Safaricom sources.
    No-op if VERIFY_CALLBACK_SOURCE_IP is False (useful for local dev).
    """
```

### 6.3 `views.py` — callback endpoints

```python
class STKCallbackView(APIView):
    def post(self, request):
        """
        1. Log raw payload to CallbackLog immediately, unconditionally
        2. Extract checkout_request_id from payload
        3. Dispatch process_stk_callback.delay(callback_log_id)
           (or call synchronously if USE_CELERY is False)
        4. Return {"ResultCode": 0, "ResultDesc": "Accepted"}, 200
           — always, even if step 2/3 fails; log the error separately,
           never let Safaricom see a non-200 for a delivery problem
        """
```

Equivalent views: `C2BValidationView`, `C2BConfirmationView`, `B2CResultView`, `B2CTimeoutView`. `C2BValidationView` is the one exception that can return a rejection (`ResultCode != 0`) — it's a pre-transaction check, not a settlement callback.

### 6.4 `tasks.py` — the idempotency-critical task

```python
@shared_task(bind=True, max_retries=5, retry_backoff=True)
def process_stk_callback(self, callback_log_id: str):
    """
    1. Load the CallbackLog row, extract checkout_request_id
    2. with transaction.atomic():
           txn = Transaction.objects.select_for_update().get(
               checkout_request_id=checkout_request_id
           )
           if txn.status in TERMINAL_STATES:
               # Already settled by a prior callback delivery — no-op.
               # This is the line that prevents double-crediting.
               callback_log.processed = True
               callback_log.save(update_fields=["processed"])
               return
           # parse result_code from payload, update txn.status,
           # txn.mpesa_receipt_number, txn.settled_at
           txn.save()
    3. Outside the atomic block: fire the appropriate signal
       (payment_confirmed / payment_failed) — signal receivers run
       host app logic (credit wallet, send SMS) with the lock released,
       so a slow receiver doesn't hold the row lock open.
    4. Mark callback_log.processed = True, link callback_log.related_transaction
    """
```

**Why the signal fires outside the lock:** if wallet-crediting logic in the host app is slow or itself opens a nested transaction, holding the DB row lock through that would create lock contention under load. Settle first, release the lock, then notify.

**Why `select_for_update` and not a unique constraint alone:** a unique constraint prevents duplicate *rows*, but here you have one row that two concurrent callback deliveries both want to *update*. The row lock serializes the two updates so the second one sees the already-terminal status and skips.

### 6.5 `urls.py`

```python
urlpatterns = [
    path("stk/callback/", STKCallbackView.as_view(), name="mpesa-stk-callback"),
    path("c2b/validate/", C2BValidationView.as_view(), name="mpesa-c2b-validate"),
    path("c2b/confirm/", C2BConfirmationView.as_view(), name="mpesa-c2b-confirm"),
    path("b2c/result/", B2CResultView.as_view(), name="mpesa-b2c-result"),
    path("b2c/timeout/", B2CTimeoutView.as_view(), name="mpesa-b2c-timeout"),
]
```

Host app includes with `path("mpesa/", include("django_mpesa.urls"))` — and those exact paths must match what's registered in `MPESA["STK_CALLBACK_URL"]` etc., since Safaricom calls the URL you registered, not whatever Django resolves.

---

## 7. Signal catalog (`signals.py`)

```python
payment_confirmed = Signal()   # sender: transaction class, kwargs: transaction
payment_failed = Signal()      # kwargs: transaction, result_code, result_desc
payout_completed = Signal()    # B2C success — kwargs: transaction
payout_failed = Signal()       # kwargs: transaction, result_code, result_desc
reversal_completed = Signal()  # kwargs: transaction
balance_received = Signal()    # kwargs: raw_payload (no transaction model involved)
```

Host app usage:

```python
# myapp/receivers.py
from django.dispatch import receiver
from django_mpesa.signals import payment_confirmed

@receiver(payment_confirmed)
def credit_wallet(sender, transaction, **kwargs):
    order = transaction.order
    order.mark_paid()
    Wallet.objects.credit(order.user, transaction.amount)
```

---

## 8. Exception hierarchy (`exceptions.py`)

```
MpesaError (base)
├── DarajaConfigError        # missing/invalid settings, wrong env for method called
├── DarajaAuthError          # OAuth token fetch failed
├── DarajaValidationError    # bad input caught before any network call
├── DarajaAPIError           # Safaricom returned a non-2xx or error ResultCode
│   ├── DarajaRateLimitError
│   └── DarajaTimeoutError
└── InvalidCallbackError     # callback payload malformed or from disallowed IP
```

Every exception carries `.result_code` and `.result_desc` where applicable, so callers can branch on Safaricom's own error taxonomy rather than string-matching messages.

---

## 9. Testing strategy

### 9.1 `testing/mock_client.py` — `MockDarajaClient`

A drop-in replacement for `BaseDarajaClient` that returns canned, schema-accurate responses without any network call. Configurable per-test to simulate success, specific error codes, or timeouts.

```python
class MockDarajaClient:
    def __init__(self, responses: dict[str, dict] = None):
        """responses maps path -> canned response dict.
        Defaults to realistic success responses for every known path."""

    def post(self, path: str, payload: dict) -> dict:
        """Returns the configured response, or raises the configured
        exception if the test set one up for that path."""
```

Usage:

```python
def test_stk_push_creates_pending_transaction(mock_daraja):
    mock_daraja.set_response("/mpesa/stkpush/v1/processrequest", {
        "CheckoutRequestID": "ws_CO_123", "MerchantRequestID": "29115-...",
        "ResponseCode": "0", "ResponseDescription": "Success",
    })
    service = STKPushService(client=mock_daraja)
    txn = service.initiate(phone_number="254712345678", amount=Decimal("100"), ...)
    assert txn.status == "PENDING"
    assert txn.checkout_request_id == "ws_CO_123"
```

### 9.2 `testing/fixtures.py` — pytest fixtures

- `mock_daraja` — injects `MockDarajaClient` in place of the real client
- `sample_stk_callback_payload` — realistic Daraja callback JSON, both success and failure variants
- `pending_transaction` — factory-created transaction in `PENDING` state, ready for a callback test

### 9.3 The concurrency test that matters most

```python
# tests/test_idempotency.py
def test_duplicate_callback_does_not_double_settle(django_db_blocker):
    """
    Simulates two threads calling process_stk_callback for the same
    checkout_request_id concurrently. Asserts:
    - The transaction's settled_at is set exactly once
    - payment_confirmed signal fires exactly once
    - Second call exits via the terminal-state no-op path
    Uses threading + a barrier to force genuine concurrency,
    not just two sequential calls.
    """
```

This single test is the one you should never let regress — it's the direct regression test for the exact bug class Zaruni hit in production.

---

## 10. Security checklist

- [ ] Credentials sourced from env vars / secrets manager — never committed, never in `settings.py` literals
- [ ] `SECURITY_CREDENTIAL` for B2C/reversal is the RSA-encrypted initiator password, encrypted with Safaricom's public certificate — never the plaintext password
- [ ] All callback URLs are HTTPS — enforced by `mpesa_check_config`
- [ ] `VERIFY_CALLBACK_SOURCE_IP` enabled in production — Safaricom's published IP ranges only
- [ ] Callback views never log full payloads at INFO level in a way that leaks phone numbers into shared log aggregators without access control
- [ ] Rate limiting on callback endpoints at the reverse-proxy layer (Caddy/Cloudflare) as defense-in-depth beyond the IP allowlist
- [ ] `DEBUG=False` responses never leak stack traces to Safaricom's callback (return generic 200 regardless of internal error, log internally)
- [ ] Dependency scanning (`pip-audit` or `safety`) in CI on every PR

---

## 11. Packaging and open-source readiness

### 11.1 `pyproject.toml` (essentials)

```toml
[project]
name = "django-mpesa"
version = "0.1.0"
description = "A production-hardened Django app for Safaricom's Daraja M-PESA API"
requires-python = ">=3.10"
dependencies = ["django>=4.2", "djangorestframework>=3.14", "requests>=2.31", "celery>=5.3"]
license = {text = "MIT"}

[project.optional-dependencies]
test = ["pytest", "pytest-django", "factory-boy", "pytest-cov"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

### 11.2 CI (`.github/workflows/test.yml`)

Matrix across Python 3.10–3.12 × Django 4.2/5.0. Runs `pytest --cov`, fails under 90% coverage on `django_mpesa/`. Runs `mpesa_check_config` against a dummy sandbox settings file to catch config-resolution regressions.

### 11.3 Versioning

Semantic versioning. `0.x` while the model/settings schema may still change; `1.0.0` once a project (Zaruni) has run it in production for a full billing cycle without a hotfix to the idempotency path.

### 11.4 Documentation site

`docs/` built with MkDocs Material, published to Read the Docs or GitHub Pages. `quickstart.md` should get a new contributor from `pip install django-mpesa` to a working STK Push in under 10 minutes — that's the bar.

### 11.5 Contribution scaffolding

`CONTRIBUTING.md` covers: local sandbox credential setup (with a note that sandbox credentials are free and instant from Safaricom's developer portal), running the test suite, the idempotency test requirement for any change touching `tasks.py`, and PR checklist. `CODE_OF_CONDUCT.md` — standard Contributor Covenant.

---

## 12. Build order (unchanged from prior discussion, restated for completeness)

1. `client/auth.py` + `client/base.py` — the foundation
2. `models.py` abstract bases + migrations
3. `STKPushService` end-to-end, including callback view + task + idempotency test
4. `C2BService` + its two callback views
5. `B2CService` + result/timeout callbacks (port from Zaruni's existing logic)
6. `TransactionStatusService`, `AccountBalanceService`, `ReversalService`
7. `testing/` module, docs, PyPI packaging, CI

Steps 1–3 alone are enough to open-source as `v0.1.0` — STK Push is what 90% of adopters want first. The rest can land as `v0.2.0`, `v0.3.0` incrementally, which also keeps early community contributions focused.

---

*End of blueprint. Any section here should be buildable independently by a contributor who has read only that section plus §2 and §3.*

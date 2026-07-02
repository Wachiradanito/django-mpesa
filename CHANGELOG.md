# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] — 2026-07-02

### Added

- **STK Push end-to-end**: `STKPushService.initiate()` and `STKPushService.query()` with idempotent callback handling
- **C2B**: `C2BService.register_urls()` and `C2BService.simulate()` with validation and confirmation callbacks
- **B2C**: `B2CService.send_payment()` with result and timeout callbacks
- **Transaction Status**: `TransactionStatusService.query()` for reconciliation
- **Account Balance**: `AccountBalanceService.query()`
- **Reversal**: `ReversalService.reverse()`
- **Abstract models**: `AbstractMpesaTransaction` and `AbstractMpesaCallbackLog` — zero migrations shipped
- **Idempotent callbacks**: `select_for_update()` + terminal state check prevents double-settlement under concurrent delivery
- **IP allowlist middleware**: `MpesaCallbackIPAllowlistMiddleware` rejects non-Safaricom callback sources
- **Django signals**: `payment_confirmed`, `payment_failed`, `payout_completed`, `payout_failed`, `reversal_completed`, `balance_received`, `c2b_validation_received`
- **Exception hierarchy**: `MpesaError` → `DarajaConfigError`, `DarajaAuthError`, `DarajaValidationError`, `DarajaAPIError`, `DarajaRateLimitError`, `DarajaTimeoutError`, `InvalidCallbackError`
- **Testing module**: `MockDarajaClient`, `MpesaTransactionFactory`, `MpesaCallbackLogFactory`, pytest fixtures
- **Management command**: `mpesa_check_config` validates all settings at deploy time
- **Optional Celery**: `USE_CELERY=False` for synchronous processing in simple deployments
- **OAuth token caching**: stampede-safe token cache with configurable TTL buffer

### Security

- Credentials support callable resolution — never hardcoded
- `SECURITY_CREDENTIAL` for B2C/Reversal must be RSA-encrypted; plaintext password is never sent to Daraja
- All callback URLs validated as HTTPS in production by `mpesa_check_config`
- Sensitive fields (`Password`, `SecurityCredential`, `Passkey`) redacted from DEBUG logs

### Known limitations

- Multi-tenancy (multiple shortcodes per Django instance) is not yet supported — deferred post-1.0.0
- Concurrent idempotency tests require PostgreSQL; SQLite's single-writer model is insufficient for the threading test

[0.1.0]: https://github.com/mainfinity/django-mpesa/releases/tag/v0.1.0

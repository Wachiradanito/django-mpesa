# Configuration Reference

All settings live under a single `MPESA` dict in your Django `settings.py`.

## Full settings reference

| Key | Required | Default | Description |
|---|---|---|---|
| `ENV` | Yes | `"sandbox"` | `"sandbox"` or `"production"` |
| `CONSUMER_KEY` | Yes | — | Daraja consumer key. Supports callable. |
| `CONSUMER_SECRET` | Yes | — | Daraja consumer secret. Supports callable. |
| `SHORTCODE` | Yes | — | Your M-PESA business shortcode. |
| `PASSKEY` | Yes (STK) | — | Lipa Na M-PESA passkey. Supports callable. |
| `INITIATOR_NAME` | Yes (B2C/Reversal) | `None` | API operator name from Safaricom portal. |
| `SECURITY_CREDENTIAL` | Yes (B2C/Reversal) | `None` | RSA-encrypted initiator password. |
| `STK_CALLBACK_URL` | Yes (STK) | — | HTTPS URL for STK Push callbacks. |
| `C2B_VALIDATION_URL` | Yes (C2B) | — | HTTPS URL for C2B validation. |
| `C2B_CONFIRMATION_URL` | Yes (C2B) | — | HTTPS URL for C2B confirmation. |
| `B2C_RESULT_URL` | Yes (B2C) | — | HTTPS URL for B2C results. |
| `B2C_TIMEOUT_URL` | Yes (B2C) | — | HTTPS URL for B2C timeouts. |
| `TRANSACTION_MODEL` | Yes | — | e.g. `"myapp.MpesaTransaction"` |
| `CALLBACK_LOG_MODEL` | Yes | — | e.g. `"myapp.MpesaCallbackLog"` |
| `TOKEN_CACHE_ALIAS` | No | `"default"` | Django cache backend alias for OAuth token. |
| `TOKEN_CACHE_TTL_BUFFER` | No | `60` | Seconds subtracted from token TTL before caching. |
| `REQUEST_TIMEOUT` | No | `30` | Outbound HTTP timeout in seconds. |
| `MAX_RETRIES` | No | `3` | Max retries on Daraja 5xx errors. |
| `RETRY_BACKOFF_FACTOR` | No | `0.5` | Exponential backoff factor between retries. |
| `VERIFY_CALLBACK_SOURCE_IP` | No | `True` | Enforce Safaricom IP allowlist on callbacks. |
| `CALLBACK_IP_ALLOWLIST` | No | Safaricom IPs | List of allowed callback source IPs. |
| `TRUST_FORWARDED_FOR` | No | `False` | Trust `X-Forwarded-For` header (behind a proxy). |
| `FORWARDED_FOR_TRUSTED_PROXIES` | No | `[]` | IPs of trusted proxy servers. |
| `USE_CELERY` | No | `True` | Process callbacks async via Celery. `False` = synchronous. |
| `CELERY_TASK_MAX_RETRIES` | No | `5` | Max Celery task retries on failure. |
| `CELERY_TASK_RETRY_BACKOFF` | No | `True` | Exponential backoff on Celery retries. |

## Callable credentials

Any credential setting accepts a callable (lambda or function). This lets you source secrets from environment variables, AWS Secrets Manager, or any vault without hardcoding them:

```python
MPESA = {
    "CONSUMER_KEY": lambda: os.environ["MPESA_CONSUMER_KEY"],
    "CONSUMER_SECRET": lambda: os.environ["MPESA_CONSUMER_SECRET"],
    # Plain string also works (not recommended for secrets)
    "SHORTCODE": "174379",
}
```

## Validate on deploy

```bash
python manage.py mpesa_check_config
```

Exits with code 1 if any required setting is missing or misconfigured.

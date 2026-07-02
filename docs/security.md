# Security

## Credentials

Never hardcode credentials. Use callables to source them from environment variables or a secrets manager:

```python
MPESA = {
    "CONSUMER_KEY": lambda: os.environ["MPESA_CONSUMER_KEY"],
    "CONSUMER_SECRET": lambda: os.environ["MPESA_CONSUMER_SECRET"],
    "PASSKEY": lambda: os.environ["MPESA_PASSKEY"],
}
```

## Security credential for B2C / Reversal

The `SECURITY_CREDENTIAL` is your initiator password encrypted with Safaricom's RSA public certificate. **Never** send the plaintext password to Daraja.

To generate it:

1. Download Safaricom's certificate from the [Daraja portal](https://developer.safaricom.co.ke).
2. Encrypt your initiator password:
   ```bash
   echo -n "your_initiator_password" | openssl rsautl -encrypt \
     -pubin -inkey safaricom_cert.cer -pkcs | base64
   ```
3. Store the base64 output as `SECURITY_CREDENTIAL` in your settings.

Use the sandbox certificate for sandbox, production certificate for production — they are different.

## IP allowlist

Safaricom sends callbacks from a published set of IP addresses. The library enforces this by default:

```python
MPESA = {
    "VERIFY_CALLBACK_SOURCE_IP": True,  # default — always on in production
    "CALLBACK_IP_ALLOWLIST": [
        "196.201.214.200", "196.201.214.206", "196.201.213.114",
        # ... full list is the default
    ],
}
```

Disable only for local development:

```python
# For local dev with ngrok etc.
MPESA = {"VERIFY_CALLBACK_SOURCE_IP": False}
```

If you're behind a reverse proxy (Cloudflare, Nginx, Caddy), enable `X-Forwarded-For` trust:

```python
MPESA = {
    "TRUST_FORWARDED_FOR": True,
    "FORWARDED_FOR_TRUSTED_PROXIES": ["your.proxy.ip"],
}
```

## HTTPS requirement

All callback URLs must use `https://` in production. The `mpesa_check_config` command enforces this:

```bash
python manage.py mpesa_check_config
# [FAIL] STK_CALLBACK_URL uses HTTPS: must use HTTPS in production
```

## Sensitive data in logs

The library redacts sensitive fields (`Password`, `SecurityCredential`, `Passkey`) from all DEBUG log output. Phone numbers in callback payloads are stored in the database but logged only at DEBUG level.

## Pre-production checklist

- [ ] All credentials sourced from env vars or secrets manager
- [ ] `SECURITY_CREDENTIAL` is the encrypted credential, not the plaintext password
- [ ] All callback URLs use `https://`
- [ ] `VERIFY_CALLBACK_SOURCE_IP: True`
- [ ] `DEBUG: False` in production Django settings
- [ ] Rate limiting on callback endpoints at the reverse-proxy layer
- [ ] `pip-audit` passes with no high-severity findings
- [ ] `python manage.py mpesa_check_config` exits 0

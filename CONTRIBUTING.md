# Contributing to django-mpesa

## Setup

```bash
git clone https://github.com/mainfinity/django-mpesa.git
cd django-mpesa
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Running tests

```bash
pytest --cov=django_mpesa --cov-report=term-missing
pytest tests/test_idempotency.py -v  # concurrency tests
```

## Idempotency rule

Any PR touching `tasks.py` must update `tests/test_idempotency.py`.

## Code style

```bash
ruff check django_mpesa/
ruff format django_mpesa/
```

## PR checklist

- [ ] Tests pass with coverage >= 90%
- [ ] No ruff errors
- [ ] New public APIs have docstrings
- [ ] CHANGELOG.md updated under [Unreleased]
- [ ] If tasks.py changed, idempotency test updated

## Sandbox credentials

Register at https://developer.safaricom.co.ke for free sandbox credentials.
Use ngrok to expose local callback URLs. Never commit credentials.

# Contributing to mainfinity-django-mpesa

Thank you for your interest in contributing. This document covers everything you need to get set up and submit a quality PR.

## Setup

```bash
git clone https://github.com/Wachiradanito/django-mpesa.git
cd django-mpesa
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Running tests

```bash
# All tests with coverage
pytest --cov=django_mpesa --cov-report=term-missing

# Single file
pytest tests/test_validators.py -v

# Concurrency / idempotency tests (uses real DB transactions, slower)
pytest tests/test_idempotency.py -v
```

The suite must pass with zero network access — no real Daraja calls are made.

## Idempotency rule

Any PR touching `tasks.py` must update `tests/test_idempotency.py`.

## Code style

```bash
ruff check django_mpesa/
ruff format django_mpesa/
```

CI fails on lint errors.

## PR checklist

- [ ] Tests pass with coverage >= 90%
- [ ] No ruff errors
- [ ] New public APIs have docstrings
- [ ] If you touched `tasks.py`, `tests/test_idempotency.py` is updated
- [ ] `CHANGELOG.md` has an entry under [Unreleased]

## Sandbox credentials

Register at https://developer.safaricom.co.ke for free sandbox credentials.
Use ngrok to expose local callback URLs. Never commit credentials.

## Installation for development

```bash
pip install mainfinity-django-mpesa[dev]
```

# FinTech Ledger

## Project Overview

FinTech Ledger is a multi-account financial ledger service implemented as a REST API. The service provides account management and internal transfers between accounts, with emphasis on transactional consistency, concurrency control, and idempotent request handling.

### Core Stack

| Component | Version / Implementation |
|---|---|
| Language | Python 3.12 |
| Web framework | Django 5.1 |
| API framework | Django REST Framework |
| Database | PostgreSQL 16 |
| Authentication | JWT (`djangorestframework-simplejwt`) |
| API schema | OpenAPI 3 via `drf-spectacular` |
| Containerization | Docker, Docker Compose |
| Test runner | `pytest`, `pytest-django` |

## Architecture & Design Decisions

### Directory Layout

```text
.
├── Dockerfile
├── docker-compose.yml
├── manage.py
├── pytest.ini
├── requirements.txt
├── config/
│   ├── settings.py          # Django/DRF/JWT/Spectacular configuration
│   ├── urls.py              # Root URL routing
│   ├── asgi.py
│   └── wsgi.py
└── ledger/
    ├── models.py            # Account and Transaction data models
    ├── serializers.py       # Request/response serialization and validation
    ├── services.py          # Transfer business logic and invariants
    ├── views.py             # DRF viewsets and HTTP orchestration
    ├── urls.py              # Router registration for ledger endpoints
    ├── admin.py             # Django Admin configuration
    ├── migrations/
    │   └── 0001_initial.py
    └── tests/
        └── test_transfers.py
```

### Service Layer Separation

Business invariants for transfers are implemented in `ledger/services.py` (`execute_transfer`), not in views or serializers. Views are responsible for HTTP concerns: request parsing, authentication/permission enforcement, serializer validation, exception translation, and response formatting. Serializers define input/output structure. This separation keeps domain rules testable and reduces coupling between transport and business logic.

### Concurrency and Data Integrity

- **Atomic execution**: Transfers run inside `@transaction.atomic`, ensuring balance updates and transaction creation commit as a single unit.
- **Pessimistic row locking**: Participating accounts are loaded with `select_for_update()` before mutation. Account IDs are sorted deterministically and queried in that order to reduce deadlock risk when concurrent transfers touch the same account set.
- **Monetary precision**: Monetary fields use `DecimalField(max_digits=14, decimal_places=2)`. Transfer amounts are handled as `Decimal` values; floating-point arithmetic is avoided.
- **Database constraints**: Accounts and transactions use UUID primary keys. `Transaction.idempotency_key` is unique and indexed. Account relationships use `PROTECT` to prevent accidental deletion of referenced records.

### Idempotency Mechanism

Each transfer request includes an `idempotency_key` (max length 64). Before executing a transfer, the service checks for an existing transaction with the same key. If found, the existing transaction is returned without applying balance changes again. The unique database constraint on `idempotency_key` provides an integrity guard at the persistence layer.

## API Reference

### Endpoints

| Method | Path | Auth | Description |
|---|---|---:|---|
| `POST` | `/api/v1/auth/token/` | No | Obtain JWT access and refresh tokens. |
| `POST` | `/api/v1/auth/token/refresh/` | No | Refresh a JWT access token. |
| `GET` | `/api/v1/accounts/` | Yes | List accounts owned by the authenticated user. |
| `POST` | `/api/v1/accounts/` | Yes | Create an account for the authenticated user. |
| `GET` | `/api/v1/accounts/{id}/` | Yes | Retrieve an owned account. |
| `PUT` | `/api/v1/accounts/{id}/` | Yes | Replace an owned account. |
| `PATCH` | `/api/v1/accounts/{id}/` | Yes | Partially update an owned account. |
| `DELETE` | `/api/v1/accounts/{id}/` | Yes | Delete an owned account. |
| `GET` | `/api/v1/transactions/` | Yes | List transactions where the user owns the source or target account. |
| `POST` | `/api/v1/transactions/` | Yes | Execute a transfer between accounts. |
| `GET` | `/api/v1/transactions/{id}/` | Yes | Retrieve a transaction visible to the authenticated user. |
| `GET` | `/api/schema/` | No | OpenAPI schema (drf-spectacular). |
| `GET` | `/api/docs/` | No | Swagger UI. |
| `GET` | `/admin/` | Session | Django Admin interface. |

Notes:
- Ledger endpoints require `Authorization: Bearer <access_token>`.
- Account creation accepts `currency` (defaults to `EUR`). `balance`, `is_active`, and `created_at` are read-only.
- Transaction creation requires `source_account_id`, `target_account_id`, `amount`, and `idempotency_key`.

### Examples

#### Obtain JWT Token

Request:

```bash
curl -X POST http://localhost:8000/api/v1/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "alice",
    "password": "strongpassword123"
  }'
```

Response:

```json
{
  "refresh": "<refresh_token>",
  "access": "<access_token>"
}
```

#### Create an Account

Request:

```bash
curl -X POST http://localhost:8000/api/v1/accounts/ \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "currency": "EUR"
  }'
```

Response:

```json
{
  "id": "2f9d9d8f-6d8e-4f2f-9d2e-8f8f2a6b1c3d",
  "currency": "EUR",
  "balance": "0.00",
  "is_active": true,
  "created_at": "2026-11-24T13:07:00Z"
}
```

#### Execute an Idempotent Transfer

Request:

```bash
curl -X POST http://localhost:8000/api/v1/transactions/ \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "source_account_id": "2f9d9d8f-6d8e-4f2f-9d2e-8f8f2a6b1c3d",
    "target_account_id": "7a1c4b2d-3e4f-5a6b-7c8d-9e0f1a2b3c4d",
    "amount": "150.00",
    "idempotency_key": "tx-001"
  }'
```

Response:

```json
{
  "id": "b6f8c1a2-4d5e-6f70-8123-456789abcdef",
  "idempotency_key": "tx-001",
  "source_account": "2f9d9d8f-6d8e-4f2f-9d2e-8f8f2a6b1c3d",
  "target_account": "7a1c4b2d-3e4f-5a6b-7c8d-9e0f1a2b3c4d",
  "amount": "150.00",
  "status": "COMPLETED",
  "created_at": "2026-11-24T13:10:00Z"
}
```

Repeating the same request with the same `idempotency_key` returns the existing transaction; no additional balance mutation is applied.

## Local Setup & Running (Docker)

### Prerequisites

- Docker Engine
- Docker Compose

### Steps

1. Build and start the services:

   ```bash
   docker compose up --build -d
   ```

   The `web` service runs `python manage.py migrate` before starting the Django development server on `0.0.0.0:8000`.

2. Verify services are running:

   ```bash
   docker compose ps
   ```

3. Create a Django superuser for Admin access:

   ```bash
   docker compose run --rm web python manage.py createsuperuser
   ```

4. Access the interfaces:

   | Interface | URL |
   |---|---|
   | Swagger UI | `http://localhost:8000/api/docs/` |
   | OpenAPI schema | `http://localhost:8000/api/schema/` |
   | Django Admin | `http://localhost:8000/admin/` |

5. Stop the environment:

   ```bash
   docker compose down
   ```

## Testing

The project uses `pytest-django` with `DJANGO_SETTINGS_MODULE=config.settings`.

Run the integration suite:

```bash
docker compose run --rm web pytest -v
```

### Covered Scenarios

| Test | Scenario |
|---|---|
| `test_atomic_transfer_success` | Verifies a successful transfer updates source and target balances atomically. |
| `test_idempotency_prevents_double_charge` | Repeats the same transfer request with the same `idempotency_key`; asserts one persisted transaction and no double debit. |
| `test_insufficient_funds_rejected` | Rejects transfers exceeding available balance and verifies source balance remains unchanged. |
| `test_cannot_debit_another_users_account` | Rejects transfers where the authenticated user does not own the source account and verifies no balance mutation. |

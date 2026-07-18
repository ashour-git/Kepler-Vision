# Kepler Vision API

FastAPI backend implementing Domain-Driven Design with hexagonal architecture.

## Layout

```
src/kepler/
├── main.py                 # Application factory
├── settings.py             # Pydantic settings
├── core/                   # Cross-cutting (no domain)
│   ├── errors.py
│   ├── logging.py
│   ├── telemetry.py
│   ├── ids.py
│   ├── time.py
│   ├── pagination.py
│   └── security/
│       ├── password.py
│       ├── jwt.py
│       └── deps.py
│   └── middleware/
│       ├── request_id.py
│       ├── error_handler.py
│       ├── access_log.py
│       └── security_headers.py
├── api/                    # HTTP boundary
│   ├── deps.py
│   ├── router.py
│   └── v1/
│       ├── auth.py
│       ├── users.py
│       ├── workspaces.py
│       └── api_keys.py
├── domain/                 # Pure Python (no FastAPI/SQLAlchemy)
│   └── identity/
│       ├── entities.py
│       ├── value_objects.py
│       ├── permissions.py
│       ├── services.py
│       └── events.py
├── application/            # Use cases
│   └── identity/
│       ├── commands.py
│       └── queries.py
└── infra/                  # Adapters
    ├── db/
    │   ├── base.py
    │   ├── session.py
    │   ├── uow.py
    │   └── repositories/
    └── cache/
        ├── redis.py
        └── refresh_store.py
```

## Development

```bash
# Install
pip install -e ".[dev]"

# Migrate
alembic upgrade head

# Run
uvicorn kepler.main:app --reload --port 8000

# Test
pytest

# Lint / typecheck
ruff check src tests
mypy src
```

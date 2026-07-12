# Configuration

QuantForg configuration is powered by **Pydantic Settings v2**.

## Sources (highest precedence first)

1. Process environment variables
2. `.env` file in the project root
3. Defaults defined on `Settings`

## Environments

| `APP_ENV` | Behaviour |
|---|---|
| `development` | Debug on, console logs, SQL echo optional |
| `staging` | Production-like with safer defaults |
| `production` | Rejects insecure secrets, debug/reload forbidden, JSON logs |
| `testing` | Used by pytest; separate DB name |

Factories in `core/config/environments.py`:

- `development_settings()`
- `production_settings()`
- `testing_settings()`

## Critical variables

See `.env.example` for the full list. Minimum required for a healthy boot:

```bash
APP_ENV=development
SECRET_KEY=<long-random-string>
POSTGRES_HOST=localhost
POSTGRES_PASSWORD=<password>
REDIS_HOST=localhost
```

## Accessing settings

```python
from core.config import get_settings

settings = get_settings()  # cached singleton
```

In tests, call `get_settings.cache_clear()` after changing environment variables.

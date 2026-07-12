# Deployment

## Container image

```bash
docker build -t quantforg:latest .
```

The multi-stage `Dockerfile` produces a non-root runtime image with:

- Python 3.13 slim
- Poetry-installed virtualenv
- `tini` as PID 1
- Health check against `/api/v1/health`

## Compose (local / staging)

```bash
cp .env.example .env
# Edit secrets
docker compose up -d
```

Services: `api`, `postgres`, `redis`.

## Production checklist

- [ ] Set `APP_ENV=production`
- [ ] Set a strong `SECRET_KEY` (≥ 64 chars, no default markers)
- [ ] Set a strong `POSTGRES_PASSWORD`
- [ ] Set `DEBUG=false` and `RELOAD=false`
- [ ] Set `LOG_JSON=true` / `LOG_FORMAT=json`
- [ ] Restrict `ALLOWED_HOSTS` and `CORS_ORIGINS`
- [ ] Run migrations: `alembic upgrade head`
- [ ] Configure TLS at the reverse proxy / load balancer
- [ ] Ship logs to your aggregation pipeline (JSON lines on stdout)

## Process model

```
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

Workers share nothing; each has its own DI container, DB pool, and Redis pool
created during FastAPI lifespan startup.

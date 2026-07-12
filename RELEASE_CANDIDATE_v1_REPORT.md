# Release Candidate v1 Report

**Candidate:** QuantForg **v1.0.0-rc.1**  
**Date:** 2026-07-12  
**Type:** Release readiness packaging (no new trading features, no AI, no execution enablement)

---

## Executive summary

RC1 packages the completed QuantForg platform through Operations & Observability for staging evaluation. Live execution remains **disabled**. AI is **not** included. Documentation, OpenAPI, changelog, and production checklist are published.

**Recommendation:** Ship RC1 to staging. Defer unrestricted production GA until persistence wiring and lockfile blockers are closed (`PRODUCTION_READINESS_REPORT.md`).

---

## Explicit non-goals (honored)

- No new trading features  
- No AI implementation  
- No execution behavior changes  
- `EXECUTION_ENABLED` remains **false**  

---

## Deliverables checklist

| # | Deliverable | Location | Status |
|---|-------------|----------|--------|
| 1 | Repository audit | Embedded in `PRODUCTION_READINESS_REPORT.md` | Done |
| 2 | Architecture doc | `ARCHITECTURE.md` | Done |
| 3 | Deployment doc | `DEPLOYMENT.md` | Done |
| 4 | Operations doc | `OPERATIONS.md` | Done |
| 5 | Security doc | `SECURITY.md` | Done |
| 6 | Backup / recovery | `BACKUP_RECOVERY.md` | Done |
| 7 | API reference | `API_REFERENCE.md` | Done |
| 8 | OpenAPI | `openapi/openapi.v1.0.0-rc1.json` (+ `openapi/openapi.json`) | Done — **74 paths** |
| 9 | Changelog | `CHANGELOG.md` `[1.0.0-rc.1]` | Done |
| 10 | Production checklist | `PRODUCTION_READINESS_REPORT.md` | Done |
| 11 | This RC report | `RELEASE_CANDIDATE_v1_REPORT.md` | Done |

---

## Version metadata

| Artifact | Value |
|----------|-------|
| Poetry package | `1.0.0rc1` |
| `APP_VERSION` / settings default | `1.0.0-rc.1` |
| `app.__version__` / `core.__version__` | `1.0.0-rc.1` |
| OpenAPI `info.version` | `1.0.0-rc.1` |
| Docker base | `python:3.13-slim-bookworm` |

---

## Module freeze (RC1)

Auth → User Platform → Broker → MT5 → Execution Safety → Portfolio → Risk → Strategy → Backtest → Paper → Walk-Forward → Operations  

All prior `*_REPORT.md` modules preserved. Clean Architecture, Supabase migrations/RLS, CI workflow, and MT5 adapter architecture preserved.

---

## Deployment readiness

| Topic | Documented |
|-------|------------|
| Environment variables | Yes |
| Migrations + reverse downs | Yes |
| Rollback plan | Yes |
| Startup / health checks | Yes |
| Disaster recovery | Yes (`BACKUP_RECOVERY.md`) |

---

## CI

Commands:

```bash
ruff check app core tests
black --check app core tests
mypy app core
pytest
```

| Check | Result |
|-------|--------|
| ruff | green |
| black | green |
| mypy | green |
| pytest | **291 passed**, 2 skipped |
| coverage | ~79.8% (threshold 60%) |
---

## OpenAPI regenerate (maintainers)

```bash
cd QuantForg
.venv/bin/python - <<'PY'
from pathlib import Path
import json
from app.main import create_app
from core.config.settings import Settings
settings = Settings(
    app_env="testing",
    debug=True,
    secret_key="change-me-to-a-long-random-secret-key-at-least-64-chars-for-openapi",
    postgres_password="quantforg_dev_password_change_me",
    app_version="1.0.0-rc.1",
)
spec = create_app(settings=settings).openapi()
spec["info"]["version"] = "1.0.0-rc.1"
Path("openapi/openapi.v1.0.0-rc1.json").write_text(
    json.dumps(spec, indent=2, sort_keys=True) + "\n", encoding="utf-8"
)
PY
```

---

## Stop point

**Release Candidate preparation complete.**  

Do not implement AI.  
Do not enable execution.  
Do not add new trading features beyond this RC packaging.

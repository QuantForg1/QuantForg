# QuantForg Security Changelog

**Release:** Production security hardening & release readiness  
**Date:** 2026-07-13  

---

## Vulnerabilities Fixed

### C-01 — MT5 cross-tenant terminal data leak (Critical)

| | |
|--|--|
| **Severity** | Critical |
| **Description** | Process-global MT5 login allowed User A (still `connected` in DB) to read User B’s account/positions after B reconnected. Empty disconnect called `shutdown()` and tore down another tenant’s session. |
| **Mitigation** | Track `_live_session_ref`; `is_live_session()`; `require_live_mt5_connection()` / `live_connection_meta()` on MT5, portfolio, order validation, execution, risk, and strategy paths. Disconnect no longer shuts down foreign live sessions. |
| **Files** | `app/infrastructure/brokers/mt5/adapter.py`, `app/application/services/mt5_session_guard.py`, `app/application/use_cases/mt5.py`, `portfolio.py`, `mt5_order.py`, `execution_gateway.py`, `execution_safety.py`, `risk_engine.py`, `strategy_runtime.py`, `tests/unit/test_mt5_use_cases.py` |

### H-01 — Broker health / diagnostics IDOR (High)

| | |
|--|--|
| **Severity** | High |
| **Description** | Authenticated users could aggregate health and see other tenants’ `connection_id` / account UUIDs via `/brokers/{id}/health` and `/diagnostics`. |
| **Mitigation** | Health scoped to caller’s broker accounts; diagnostics restricted to owner/admin. |
| **Files** | `app/application/use_cases/broker_health.py`, `app/presentation/routers/brokers.py` |

### H-02 — Internal exception text leakage (High)

| | |
|--|--|
| **Severity** | High |
| **Description** | Unhandled exceptions could echo `str(exc)` to clients when debug was enabled. |
| **Mitigation** | Clients always receive generic `internal_error` / “An unexpected error occurred”; details stay in server logs. |
| **Files** | `app/presentation/middleware/error_handler.py` |

### M-05 — Production Host / CORS wildcards (Medium → Fixed)

| | |
|--|--|
| **Severity** | Medium |
| **Description** | Production defaults / entrypoint forced `ALLOWED_HOSTS=*`; CORS used a broad Railway origin regex in all environments. |
| **Mitigation** | Production strips `*`, derives hosts from `RAILWAY_PUBLIC_DOMAIN` plus Railway probe hosts; `CORS_ALLOWED_ORIGINS` / `CORS_ORIGINS` aliases; entrypoint never forces Host `*`; production CORS regex disabled; `EXECUTION_ENABLED` forced `false` in entrypoint and production settings. |
| **Files** | `core/config/settings.py`, `core/config/environments.py`, `app/main.py`, `docker-entrypoint.sh`, `Dockerfile`, `.env.example`, `tests/unit/test_settings.py` |

---

## Prior Hardening (still in force)

- Ops / metrics owner-admin only  
- Auth rate limiting (30/min/IP)  
- OAuth / password-reset redirect allowlist  
- Avatar upload: size, MIME, magic bytes, no SVG  
- HSTS when HTTPS / `X-Forwarded-Proto`  
- Docs disabled by default in production image  
- Ops tables RLS lockdown migration (repo)  

---

## Remaining Operator Tasks

1. **Apply** Supabase migration `supabase/migrations/20260713100000_operations_rls_lockdown.sql` (reversible via `supabase/migrations/down/20260713100000_operations_rls_lockdown.down.sql`).  
2. Set Railway variables: `ALLOWED_HOSTS` (optional — entrypoint derives from `RAILWAY_PUBLIC_DOMAIN`), `CORS_ALLOWED_ORIGINS` to the real frontend origin(s).  
3. Confirm public domain target **PORT** matches runtime `PORT` (e.g. 8080).  
4. Keep **`EXECUTION_ENABLED=false`** (enforced by image/entrypoint; do not override).  
5. Scale workers/replicas before marketing traffic spikes (P99 rises under 5k concurrent on a single worker).  
6. Confirm Postgres/Redis health on Railway and secret rotation runbooks.  

---

## Verification Artifacts

- `PENETRATION_TEST_REPORT.md`  
- `scripts/penetration_attack_harness.py`  
- `scripts/prod_api_audit_local.py`  
- `scripts/load_test_asgi.py`  

# FINAL PRODUCTION READINESS REPORT — QuantForg

**Date:** 2026-07-13  
**Auditor role:** Principal Software Architect & Security Engineer  
**Target:** Enterprise launch readiness (Stripe / Coinbase / Binance bar)  
**Commit series:** hardening through this report (`75d8f07` + follow-up hardening commit)

---

## Executive verdict

QuantForg is **conditionally production-ready for public launch** of the **non-execution** backend (docs, auth, platform, paper/backtest/risk/strategy with `EXECUTION_ENABLED=false`).

| Gate | Status |
|------|--------|
| Railway deploy + public HTTP | **PASS** |
| Full API functional audit | **74/74 PASS** |
| CI | **300 passed / 2 skipped** |
| Critical security gaps (pre-hardening) | **FIXED in this audit** |
| Live Postgres/Redis health on Railway | **DEGRADED** (operator) |
| Live Supabase signup rate limit | **BLOCKED** (operator) |
| Live MT5 trading | **NOT READY** (mock-only; gated) |

**Overall Production Readiness Score: 78 / 100**

Launch recommendation: **GO for read/auth/platform APIs** after redeploying this hardening commit and applying the Ops RLS migration. **NO-GO for live order execution** until a real MT5 client, pool health, and idempotent execution under load are proven.

---

## Scorecard

| Dimension | Score | Notes |
|-----------|------:|-------|
| **Security** | **82** | Ops/metrics locked down; auth rate limit; redirect allowlist; HSTS; avatar MIME/size; CORS credentials hardened. Remaining: TrustedHost `*`, proxy trust `*`, avatar storage stub. |
| **Performance** | **72** | ASGI load: 0% errors at 100/500/1000 concurrent GETs. P99 ~2s at 1000 on single worker (expected). Needs multi-worker / edge cache for public scale. |
| **Reliability** | **76** | Soft-fail optional deps; tini + foreground uvicorn; health/live probes. Postgres unhealthy in prod remains a reliability risk. |
| **Scalability** | **68** | Single Uvicorn worker; in-memory rate limit & metrics; Redis optional. Horizontal scale needs Redis-backed limits + sticky-free JWT (already). |
| **Maintainability** | **80** | Clear layers, 300 tests, OpenAPI, migrations with downs. Dual Alembic/Supabase story is debt. |
| **Technical Debt** | **28** (lower is better) | Avatar binary not stored; MT5 live stub; incomplete idempotency outside execution; pagination uneven. |

---

## Risk matrix

| Risk | Likelihood | Impact | Residual after hardening | Owner |
|------|------------|--------|--------------------------|-------|
| Unauth ops/audit leak | High → **Low** | Critical | Mitigated (admin auth + RLS lockdown migration) | Eng |
| Auth brute force | Medium | High | Mitigated (app rate limit + Supabase) | Eng |
| Open redirect via OAuth/reset | Medium | High | Mitigated (allowlist) | Eng |
| Avatar upload DoS / SVG | Medium | Medium | Mitigated (stream cap + MIME/magic) | Eng |
| Postgres down in prod | **High** | High | Soft-fail ops; health shows unhealthy | Ops |
| Supabase email rate limit | High | Medium | Status 429 mapped; quota is IdP | Ops |
| Live MT5 accidental send | Low | Critical | `EXECUTION_ENABLED=false` + adapter gate | Eng |
| SIGTERM drop on deploy | Medium → **Low** | Medium | tini ENTRYPOINT + `exec` uvicorn | Eng |

---

## What this audit fixed automatically

### Security
1. **`/api/v1/ops/*` and `/api/v1/metrics`** require **owner/admin** JWT.
2. **`AuthRateLimitMiddleware`** — 30 req/min/IP on login/register/forgot/refresh/oauth callback → 429.
3. **`sanitize_redirect_to`** — OAuth/password-reset redirects allowlisted.
4. **CORS** — never `allow_credentials` with `*`; strip wildcard origins.
5. **HSTS** when `X-Forwarded-Proto: https`.
6. **Avatar upload** — 5MB streamed, allowlisted MIME, PNG/JPEG magic, reject SVG/markup.
7. **Auth error messages** sanitized (no raw IdP text).
8. **Production cannot disable** security middleware via `QF_DISABLED_COMPONENTS`.
9. **Ops RLS lockdown** migration `20260713100000` — drop authenticated open policies; `service_role` only.

### Reliability / Railway
10. **`ENTRYPOINT tini`** + **`exec` uvicorn** (foreground) for graceful SIGTERM.
11. **`DOCS_ENABLED=false`** by default in image/entrypoint.
12. **Railway healthcheck** → `/health/live`.
13. **DB pool_timeout=30**.

### Observability
14. **HTTP metrics** recorded from `RequestContextMiddleware`.
15. **Error bodies** include middleware `request_id` when available.

### Regression safety
16. CI **300 passed**; local API audit **74/74**; load waves **0% errors**.

---

## Load test results (ASGI, single process)

Environment: local TestClient/ASGI transport, `testing` settings, concurrent `asyncio.gather`.

| Concurrency | Path | P50 (ms) | P95 (ms) | P99 (ms) | Error rate |
|------------:|------|---------:|---------:|---------:|-----------:|
| 100 | `/` | 130.5 | 168.5 | 174.8 | 0 |
| 100 | `/health/live` | 398.6 | 414.4 | 417.0 | 0 |
| 100 | `/api/v1/version` | 432.9 | 465.4 | 468.4 | 0 |
| 500 | `/` | 1260.4 | 1354.3 | 1369.1 | 0 |
| 500 | `/health/live` | 2023.6 | 2193.5 | 2205.0 | 0 |
| 1000 | `/` | 1554.7 | 1897.7 | 1918.2 | 0 |
| 1000 | `/health/live` | 1975.7 | 2138.6 | 2157.1 | 0 |
| 1000 | `/api/v1/version` | 1768.1 | 1916.9 | 1931.5 | 0 |

Interpretation: correctness under concurrency is good (no 5xx). Latency at 500–1000 concurrent on **one worker** is not edge-grade; scale with workers/replicas + keep probes on `/health/live`.

Raw: `/tmp/qf_load_test.json` (CI artifact local). Script: `scripts/load_test_asgi.py`.

---

## Phase findings (summary)

### Phase 1 — Security
**Pass after fixes.** JWT/session via Supabase; passwords hashed by IdP; no cookies for API auth; CSRF N/A for Bearer API; parameterized SQL; non-root Docker user; no secrets in image ENV.

**Accepted residual (document, do not blindly change):**
- `ALLOWED_HOSTS=*` / `forwarded_allow_ips=*` behind Railway edge (changing broke deploys historically).
- Avatar binary still metadata-only until Storage upload is wired.

### Phase 2 — Database
Strong FKs/indexes/RLS on domain tables. **Ops RLS was wide open — fixed by migration.** Dual Alembic (noop) vs Supabase migrations remains debt. Pool now has `pool_timeout`.

### Phase 3 — API
Status mapping for 409/429/422 verified. Ops/metrics auth is an intentional contract change for safety. Pagination still inconsistent across list endpoints. Idempotency complete for execution; incomplete for backtest/strategy/risk/walkforward (`request_id` present, uniqueness not enforced).

### Phase 4 — Performance
Startup soft-fails Redis. Metrics now wired. Single worker default. No connection leak found in entrypoint after `exec` change.

### Phase 5 — Load test
Completed at 100 / 500 / 1000 concurrent (see table). Bottleneck: single-process event loop + middleware stack under synthetic gather.

### Phase 6 — MT5
Mock client only; `EXECUTION_ENABLED=false`; connect/validate/disconnect return API errors without crash. Reconnect/heartbeat managers exist for broker connections. Live MetaTrader package path is a stub.

### Phase 7 — Observability
Structlog JSON; request IDs; health/ready/live; metrics collector wired; no distributed tracing (OpenTelemetry) yet.

### Phase 8 — Railway
Dockerfile multi-stage; tini; dynamic `PORT`; healthcheck `/health/live`; docs off. Memory/CPU limits are Railway service settings (operator).

### Phase 9 — Supabase
RLS broadly present; ops lockdown migration added. Apply `20260713100000_operations_rls_lockdown.sql` on the project. Email rate limits are project-side. Storage avatar bucket exists; app must upload bytes.

---

## Blocking issues (must clear before “full” launch)

1. **Redeploy** hardening commit to Railway.  
2. **Apply Ops RLS migration** on Supabase.  
3. **Restore Postgres health** (`DATABASE_URL`, SSL, migrations).  
4. **Clear Supabase email rate limit** (or disable confirm emails in staging).  
5. Keep **`EXECUTION_ENABLED=false`** until live MT5 + load-tested execution idempotency.

## Remaining non-blocking improvements

1. Wire real Supabase Storage for avatars.  
2. Redis-backed rate limits for multi-instance.  
3. Unique `(user_id, request_id)` for backtest/strategy/risk/walkforward.  
4. Shared cursor pagination envelope.  
5. OpenTelemetry tracing.  
6. Narrow Railway CORS regex to known frontends.  
7. Move `httpx2` to dev-only dependencies.  
8. Document Alembic as unused; Supabase as schema SoT.  
9. Scale: `WORKERS>1` or multiple Railway replicas after Redis limits.  
10. OpenAPI `responses` for 401/409/429 on auth routes.

---

## Recommended launch checklist

- [ ] Deploy latest `main` (hardening)  
- [ ] Confirm logs: `tini`/`quantforg_entrypoint`, `startup_complete`, `bind_probe_ok`  
- [ ] `GET /health/live` → 200; `GET /api/v1/ops/dashboard` → 401 without admin  
- [ ] Apply Supabase migration `20260713100000`  
- [ ] Postgres dependency → healthy in `/health` body  
- [ ] Register + login on production after rate-limit window  
- [ ] Confirm `EXECUTION_ENABLED=false`  
- [ ] Confirm `DOCS_ENABLED=false` (or explicitly enable for staging only)

---

## Conclusion

QuantForg meets a **solid SaaS API production bar** for authenticated platform + analytics/simulation endpoints once this hardening is deployed and infra TODOs are cleared. It does **not** yet meet a **brokerage execution** bar (live MT5, multi-region rate limits, full idempotency, proven DB HA).

**Score: 78/100 — Conditional GO** for public non-execution API launch.

# PostgreSQL performance report

**Date:** 2026-07-13  
**Commit:** `7e2d86d2ddd96f90346ecc05efa8d86ae965a5b0`  
**Endpoint:** `GET https://quantforg-production.up.railway.app/health`  
**CI:** success — https://github.com/QuantForg1/QuantForg/actions/runs/29226124522

---

## Root cause

Postgres was healthy but slow because each `/health` probe paid **multiple cross-region round trips** between Railway (edge `jnb1`) and Supabase (`eu-central-1` pooler):

| Cost on every probe (before) | Effect |
|------------------------------|--------|
| `pool_pre_ping=True` | Extra `SELECT 1` RTT on checkout |
| Implicit transaction + reset/`ROLLBACK` on return | Extra RTT when returning the connection |
| Cold pool / new TLS (first request) | Multi-second spike (~4 s observed earlier) |
| No sticky health connection | Full checkout path every time |

Steady-state before fix was ~**940–1100 ms** (≈ 2–3 RTTs). Geography alone is ~**180–220 ms** one-way floor for this topology; anything under ~180 ms is not achievable without co-locating Railway and Supabase.

---

## Fixes applied

Only database performance code (`core/database/session.py`, `core/config/settings.py` + unit test). No API/router/business/auth/MT5/frontend changes.

1. **Sticky AUTOCOMMIT health connection** — reused under a lock; `SELECT 1` only; reconnect-once on failure.
2. **Pool warm at startup** — open 1–2 connections, `SELECT 1`, release (avoids first-request TLS/auth spike).
3. **`pool_pre_ping=False`** — remove per-checkout ping RTT; rely on warm + `pool_recycle=1800` + health reconnect.
4. **`pool_reset_on_return=None`** — skip reset `ROLLBACK` RTT (sessions already commit/rollback).
5. **`pool_use_lifo=True`** — reuse hottest connection first.
6. **`pool_timeout=10`** — fail fast under saturation.
7. **asyncpg `statement_cache_size=0`** on Supabase pooler / port `6543` — PgBouncer-safe.
8. **Timing logs** (no secrets): `pool_acquisition_ms`, `connection_ms`, `query_execution_ms`, `total_health_ms`.

---

## Before vs after latency

### Before (production, post-connectivity fix)

| Metric | Value |
|--------|--------|
| Cold / worst observed | ~**4062 ms** |
| Steady `/health` postgres | ~**940–1100 ms** |

### After (`7e2d86d`, 100 consecutive `/health` requests)

| Metric | Value |
|--------|--------|
| Samples | 100 |
| Postgres healthy | **100 / 100** |
| Overall healthy | **100 / 100** |
| **Average** | **192.9 ms** |
| **p50** | **190.8 ms** |
| **p95** | **209.4 ms** |
| **p99** | **216.8 ms** |
| Min / Max | 180.0 / 217.7 ms |
| Stdev | 8.6 ms |

**Improvement:** ~**5×** vs steady-state (~950 → ~193 ms); ~**20×** vs cold spike (~4000 → ~193 ms).

### Target assessment

| Target | Result |
|--------|--------|
| Ideal 20–100 ms | Not met (cross-region RTT floor) |
| Acceptable **&lt;200 ms** | **Met** (avg **192.9 ms**) |
| Never &gt;1000 ms | **Met** (max **217.7 ms**) |

---

## Production readiness

| Check | Status |
|-------|--------|
| Postgres healthy | Yes |
| Pool reuse / no per-request engine | Yes |
| Startup warm | Yes |
| Leak risk (dispose on shutdown, lock, reconnect) | Mitigated |
| Backward compatible | Yes |
| ruff / black / mypy | Pass on changed files |
| pytest unit | **305 passed** |
| CI on `7e2d86d` | **success** |
| Railway deploy | **success** |

### Remaining operator action (for ideal 20–100 ms)

Co-locate compute and database:

- Move the Railway service to an **EU** region near Supabase `eu-central-1`, **or**
- Use a Supabase project in a region matching Railway `jnb1`.

Application pooling is now optimized; further gains are almost entirely **network geography**.

---

## Verification commands

```bash
# Single probe
curl -sS https://quantforg-production.up.railway.app/health | python3 -m json.tool

# Confirm deploy logs (no passwords):
# database_pool_warmed / database_health_connection_ready / database_health_check_ok
# with pool_acquisition_ms, query_execution_ms, total_health_ms
```

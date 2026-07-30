# Production release — PR #38 + #39 onto Railway `main`

Generated: `2026-07-30T16:58Z`  
Release SHA: `974324a7c7d9ddab608626bfd0635e74369998c2`

## What was done

| Step | Result |
|------|--------|
| Merge PR #39 into production line | **MERGED** (`state=MERGED`, closed `2026-07-30T16:38:03Z`) |
| Merge PR #38 into production line | **MERGED** (same timestamp) |
| Push to `main` | `de63a61` → `974324a` (fast-forward acceptance-evidence + both fixes) |
| Railway deploy | GitHub status **Success** — `quantforg-production.up.railway.app` at `16:58:05Z` |
| Deployed ref | Railway deployment id `8b44341a-…` for SHA `974324a` |

No strategy, Safety, or Risk rule changes — only existing fix commits.

## Post-deploy public probes

| Probe | Result |
|-------|--------|
| `GET /health/live` | 200 |
| `GET /api/v1/health/ready` | 200 |
| `GET /api/v1/version` | `environment=production` (API still does not expose git SHA) |
| Gateway `/health` | `1.1.3`, `connected`, `bridge_available`, `mt5_autotrading_enabled=true`, `dlls_allowed=true` |
| `GET /ite/ops/auto-trading` | **401** `missing_token` (expected without owner bearer) |

## AutoTrading wiring verification (code in deployed SHA)

On `origin/main` @ `974324a`, `build_ite_cycle_market_context`:

- Uses `_read_mt5_autotrading_enabled(...)` (reads gateway `/health` → `mt5.mt5_autotrading_enabled`)
- Returns `mt5_autotrading_enabled=bool(mt5_at)` — **no** hardcoded `False` in the builder return
- Fail-closed only when health is unknown

Railway status Success for that SHA is the process-level deploy proof available without container shell access.

## Env gates (not settable / not readable from this cloud agent)

| Variable | Status |
|----------|--------|
| `EXECUTION_ENABLED` | **Not verified** — Railway CLI unauthorized; ops API 401 |
| `MT5_GATEWAY_CALLER_TOKEN` vs Windows `MT5_GATEWAY_TOKEN` | **Not verified** — after #38, Railway accepts either name; match still required |
| `QUANTFORG_OWNER_TOKEN` | Absent in agent env → cannot poll live cycle |

## Live cycle trace

```text
Market Data → Context → Safety → Signal → Risk → OMS → Gateway → MT5
```

**Not completed** from this agent: authenticated `GET /api/v1/ite/ops/auto-trading` is required for `execution_path_step`, `primary_blocker`, and `rejection_reason`.

## First remaining production gate (after this deploy)

**Operator must confirm Railway env + read one authenticated cycle.**

Until that read:

1. If `EXECUTION_ENABLED` is still false → first gate is **Execution Enabled** (OMS path stays off; no live send).
2. If execution is true but caller token mismatches → gateway **401** on order path (`execution_path_step` toward OMS/Gateway).
3. If both OK → next reject is whatever Safety/Signal/Risk reports in `primary_blocker` (session, spread, etc.) — **not** the old hardcoded AutoTrading lie.

### Operator checklist

```bash
# Railway Variables
EXECUTION_ENABLED=true
MT5_GATEWAY_BASE_URL=<live gateway>
MT5_GATEWAY_CALLER_TOKEN=<same value as Windows MT5_GATEWAY_TOKEN>

# Then:
curl -sS -H "Authorization: Bearer $QUANTFORG_OWNER_TOKEN" \
  https://quantforg-production.up.railway.app/api/v1/ite/ops/auto-trading \
  | jq '{execution_enabled, primary_blocker, failed_reasons, orchestrator}'
```

Capture from the payload (or Railway logs): `execution_path_step`, `primary_blocker`, `rejection_reason` / `abort_reason`.

## Not claimed

- No live MT5 ticket observed
- No live `EXECUTION_ENABLED=true` proof
- No live caller-token match proof
- PAT/OAT remain **NOT ACCEPTED** without full evidence

# Production ops verification — STOPPED at access gate

Generated: `2026-07-30T17:18Z`  
Agent: cloud Production Release Engineer  
`main` tip at verification: `ded3625`  
Railway GitHub status: **Success** — `quantforg-production.up.railway.app`

## Verified live (public)

| Check | Evidence |
|-------|----------|
| Railway deploy | Commit status `QuantForg - QuantForg` = **success** for `ded3625` |
| API `/health/live` | HTTP 200 |
| API `/api/v1/health/ready` | HTTP 200 |
| Gateway | `gateway_version=1.1.3`, `token_configured=true` |
| MT5 | `connected=true`, `session_mode=attached`, `login_status=connected`, `bridge_available=true`, `mt5_autotrading_enabled=true`, `dlls_allowed=true` |
| PR #38 / #39 | MERGED; AutoTrading wiring + caller-token aliases on `main` |

## Task 1 — Railway configuration

| Variable | Live result |
|----------|-------------|
| `EXECUTION_ENABLED` | **UNVERIFIED** |
| `MT5_GATEWAY_CALLER_TOKEN` match to Windows `MT5_GATEWAY_TOKEN` | **UNVERIFIED** |

### Why unverified (runtime evidence)

```text
$ railway whoami
Unauthorized. Please login with `railway login`

$ curl https://quantforg-production.up.railway.app/api/v1/ite/ops/auto-trading
HTTP 401 {"error":{"code":"missing_token","message":"Missing bearer access token"}}

$ printenv | grep -iE 'RAILWAY_TOKEN|QUANTFORG_OWNER|E2E_'
(empty)
```

- No `RAILWAY_TOKEN` / Railway CLI session in this environment.
- No `QUANTFORG_OWNER_TOKEN` / owner email+password / `E2E_*` credentials.
- GitHub Actions secrets/variables: HTTP 403 for this integration token.
- No repository deploy workflow sets Railway env vars (only `ci.yml`).
- Stale PRR JSON (2026-07-23) showed `EXECUTION_ENABLED: false` — **not** accepted as current production proof.

**Cannot fix configuration from this agent without inventing credentials.**

## Task 2–5 — Authenticated pipeline / OMS / MT5 order

**Not executed.** Blocked by the same 401 on `/api/v1/ite/ops/auto-trading`.

Without that payload there is no verified:

- `execution_enabled`
- `primary_blocker`
- `execution_path_step`
- `recent_execution_attempts`
- OMS submission / gateway order_send / broker ack / MT5 ticket

Gateway protected route without token still correctly rejects:

```text
GET https://gateway.quantforg.com/account → 401 Invalid or missing gateway token
```

(Expected; does not prove Railway caller token match.)

## Task 6–7 — Evidence + PAT/OAT re-run

### PAT (re-run `2026-07-30T17:16:12Z`)

- File: `docs/production/reports/v7_1_pat_20260730T171612Z.json` (+ `v7_1_pat_latest.json`)
- `production_accepted`: **false**
- Declaration: **QUANTFORG v7.1 PRODUCTION NOT ACCEPTED**
- Summary: PASS 4 · FAIL 1 · BLOCKED 5
- FAIL: `TEST_9_LONG_RUN` — soak 23.99h & **stale** (last sample age ~46.7h)
- BLOCKED items include harness-only physical restart/reconnect/session tests

### OAT

- Declaration remains **LIVE PRODUCTION NOT ACCEPTED**
- Still FAIL: Remember Me / PC restart evidence; fresh ≥24h soak after reconnect fix
- Note: live MT5 is currently healthy (public `/health`) — that clears the old “MT5 disconnected” ops note, but does **not** clear soak/Remember Me OAT FAILs

## First remaining production blocker (verified)

```text
blocker_id: OPERATOR_CREDENTIALS_REQUIRED
execution_path_step: (unreachable — ops API not authenticated)
primary_blocker: (unknown — no auto-trading snapshot)
rejection_reason: Missing bearer access token (HTTP 401 on /api/v1/ite/ops/auto-trading)
               + Railway CLI Unauthorized (cannot read/set EXECUTION_ENABLED or caller token)
```

This is the **first** gate preventing completion of the remaining production work. No trading-logic change can clear it.

## Exact next action required

Operator (OWNER) must do **one** of:

1. **Preferred:** In Railway dashboard → QuantForg production service → Variables:
   - Set `EXECUTION_ENABLED=true`
   - Set `MT5_GATEWAY_CALLER_TOKEN` (or `MT5_GATEWAY_TOKEN`) = exact Windows `MT5_GATEWAY_TOKEN` (fingerprint preview `QuantF******Qw8Rt5`, length 43)
   - Confirm `MT5_GATEWAY_BASE_URL` points at live gateway
2. Provide to the release agent (env / Cursor secret):
   - `RAILWAY_TOKEN` (or complete `railway login`) **and**
   - `QUANTFORG_OWNER_TOKEN` **or** `QUANTFORG_OWNER_EMAIL` + `QUANTFORG_OWNER_PASSWORD`
3. Then re-run:

```bash
curl -sS -H "Authorization: Bearer $QUANTFORG_OWNER_TOKEN" \
  https://quantforg-production.up.railway.app/api/v1/ite/ops/auto-trading \
  | jq '{execution_enabled, primary_blocker, blocking_category, failed_reasons, ops_mode, orchestrator, recent_execution_attempts}'
```

Capture first reject fields if still blocked: `execution_path_step`, `primary_blocker`, `rejection_reason` / `abort_reason`.

## Explicitly not claimed

- Production fully operational
- Live order / MT5 ticket
- `EXECUTION_ENABLED=true` on Railway
- Caller token match
- PAT ACCEPTED
- OAT ACCEPTED
- Release complete

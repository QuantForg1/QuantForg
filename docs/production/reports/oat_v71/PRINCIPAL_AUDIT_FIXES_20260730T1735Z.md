# Principal production audit — fixable defects + credential stop

Generated: `2026-07-30T17:35Z`  
Branch: `cursor/prod-principal-audit-bc83`

## Live public state (runtime)

| Check | Result |
|-------|--------|
| Railway API `/health/live` | 200 |
| Railway `/ready` | 200 |
| Railway deploy status | Success (`ded3625` tip pre-this-PR) |
| Gateway | `1.1.3`, connected, bridge, AutoTrading, DLLs |
| `/ite/ops/auto-trading` | **401** `missing_token` |
| Railway CLI | Unauthorized |
| Owner / Railway tokens in agent env | **absent** |

## Implementation fixes landed (this PR)

No strategy, risk threshold, Safety policy, or position-sizing changes.

| ID | Defect | Fix |
|----|--------|-----|
| BUG-1 | Flaky `live_probes=False` overwrote proven context connectivity → false `SAFETY_BLOCKED` | OR kwargs with probes; log when ignoring probe False |
| BUG-4 | Stale enrich AutoTrading/account flags beat fresher `ctx` | Prefer context via `_cycle_flag_prefer_context` |
| BUG-2 | `EXECUTION_ENABLED=true` with URL but empty caller token stayed True in settings while adapter used Mock | Production coerce requires URL **and** caller token |
| BUG-5 | Equity fallback enabled trading when `trade_mode=disabled` | Fallback only for empty/`unknown` mode |
| LOG | Early Safety block lacked `execution_path_step` | Structured `execution_path_step` FAIL on Safety |
| GW | Reconnect held `_lock` across MT5 initialize/login | Release lock before `_try_reconnect` |
| GW | `order_send` / cancel unbounded | `call_mt5_bounded` ≥15s |
| GW | `terminal_info` 200ms omit AutoTrading under load | Meta budget 0.5–1.0s |
| PERF | New httpx client per gateway request | Persistent client + close(); read timeout cap 30s |
| TYPE | `eq` shadowed Decimal vs quality store | Rename to `quality` / `equity` |

Gateway package version bumped to **1.1.4** (Windows redeploy required for GW fixes).

Unit tests: `tests/unit/test_prod_principal_wiring_fixes.py` + prior suites — 79 passed in targeted run.

## Still blocked (operator credentials)

Cannot verify or set:

- `EXECUTION_ENABLED=true` on Railway
- Caller token == Windows `MT5_GATEWAY_TOKEN`
- Authenticated pipeline / OMS / MT5 ticket
- `primary_blocker` / live `execution_path_step` from production process

## PAT / OAT

Re-run after commit; expect **NOT ACCEPTED** until soak freshness + owner ops auth + Remember Me evidence.

## Exact operator actions

1. Merge/deploy this PR to Railway `main` (API fixes).
2. Redeploy Windows gateway to **1.1.4**.
3. Railway Variables: `EXECUTION_ENABLED=true`, `MT5_GATEWAY_CALLER_TOKEN` = Windows token, `MT5_GATEWAY_BASE_URL` correct.
4. Provide `QUANTFORG_OWNER_TOKEN` (or email/password) **or** paste authenticated `/ite/ops/auto-trading` JSON.
5. Fresh ≥24h soak sync + Remember Me Step 4 for OAT.
